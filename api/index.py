import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is on sys.path for both local uvicorn and Vercel serverless runtimes
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import (
    BYLAWS_FILE_PATH,
    COURSE_CATALOG_PATH,
    DEFAULT_MODEL,
    GEMINI_API_KEY,
    GRADE_POINTS,
)
from core.advisor_agent import AcademicAdvisorAgent
from core.tools import (
    analyze_academic_standing,
    calculate_projected_gpa,
    student_record_context,
)
from utils.transcript_importer import (
    build_student_record_from_extracted,
    parse_transcript_with_gemini,
)
from utils.transcript_parser import (
    CourseCatalog,
    CourseRecord,
    RegisteredCourseRecord,
    StudentRecord,
    load_course_catalog,
)


def _get_server_gemini_key() -> str:
    """Reads GEMINI_API_KEY exclusively from server environment variables."""
    return (os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY or "").strip()


def _load_catalog() -> CourseCatalog:
    return load_course_catalog(COURSE_CATALOG_PATH)


# ----------------- FastAPI Application & CORS -----------------
app = FastAPI(
    title="Smart Academic Advisor API",
    description="Vercel-ready FastAPI backend wrapping Gemini Function Calling, Bylaws RAG, and deterministic GPA calculations.",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

_raw_origins = os.getenv("ALLOWED_ORIGINS", "*").strip()
ALLOWED_ORIGINS = (
    ["*"]
    if _raw_origins == "*"
    else [o.strip() for o in _raw_origins.split(",") if o.strip()]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=(ALLOWED_ORIGINS != ["*"]),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------- Pydantic Request / Response Schemas -----------------
class HealthResponse(BaseModel):
    status: str = "ok"
    courses_loaded: int
    bylaws_loaded: bool
    gemini_configured: bool
    default_chat_model: str


class PrerequisiteDetail(BaseModel):
    code: str
    name: str


class CourseItemResponse(BaseModel):
    code: str
    name: str
    credit_hours: int
    level: int
    department: str
    category: str
    description: str = ""
    prerequisites: List[str] = Field(default_factory=list)
    prerequisite_names: List[str] = Field(default_factory=list)
    prerequisites_details: List[PrerequisiteDetail] = Field(default_factory=list)


class CoursesListResponse(BaseModel):
    total_courses: int
    courses: List[CourseItemResponse]


class StudentRecordPayload(BaseModel):
    """Flexible student record payload with defaults so new/empty students work seamlessly."""
    student_id: str = ""
    student_name: str = "Student"
    major: str = "Data Sciences & Analytics"
    academic_level: int = Field(default=1, ge=1, le=5)
    current_gpa: float = Field(default=0.0, ge=0.0, le=4.0)
    total_completed_credits: int = Field(default=0, ge=0)
    total_quality_points: float = Field(default=0.0, ge=0.0)
    academic_standing: str = "Good Standing"
    completed_courses: List[CourseRecord] = Field(default_factory=list)
    registered_courses: List[RegisteredCourseRecord] = Field(default_factory=list)

    def to_student_record(self) -> StudentRecord:
        record = StudentRecord(**self.model_dump())
        if record.completed_courses:
            record.recalculate_academic_metrics()
        return record


class ExpectedCourseInput(BaseModel):
    course_code: str = Field(..., min_length=1)
    credit_hours: int = Field(..., ge=0, le=6)
    expected_grade: str = Field(..., min_length=1)


class RepeatCourseInput(BaseModel):
    course_code: str = Field(..., min_length=1)
    credit_hours: int = Field(default=3, ge=0, le=6)
    old_grade: str = Field(default="F")
    new_grade: str = Field(..., min_length=1)


class SimulateGPARequest(BaseModel):
    student_record: StudentRecordPayload = Field(default_factory=StudentRecordPayload)
    new_courses: List[ExpectedCourseInput] = Field(default_factory=list)
    repeat_courses: List[RepeatCourseInput] = Field(default_factory=list)


class SimulateGPAResponse(BaseModel):
    gpa_projection: Dict[str, Any]
    academic_standing: Dict[str, Any]
    projected_academic_standing: Dict[str, Any]


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|model)$")
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Student question for the AI Academic Advisor.")
    student_record: Optional[StudentRecordPayload] = None
    history: List[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    response: str
    model_used: str


# ----------------- Endpoints -----------------
@app.get("/api/health", response_model=HealthResponse, tags=["System"])
def health_check() -> HealthResponse:
    """Checks API health, loaded curriculum course count, bylaws availability, and server API key state."""
    catalog = _load_catalog()
    return HealthResponse(
        status="ok",
        courses_loaded=len(catalog.courses),
        bylaws_loaded=BYLAWS_FILE_PATH.exists(),
        gemini_configured=bool(_get_server_gemini_key()),
        default_chat_model=DEFAULT_MODEL,
    )


@app.get("/api/courses", response_model=CoursesListResponse, tags=["Curriculum"])
def list_courses(
    level: Optional[int] = Query(default=None, ge=1, le=4, description="Filter by academic level (1-4)"),
    category: Optional[str] = Query(default=None, description="Filter by category substring"),
    search: Optional[str] = Query(default=None, description="Search by course code or title"),
) -> CoursesListResponse:
    """Returns all faculty courses with full prerequisite course names resolved from the catalog."""
    catalog = _load_catalog()
    code_to_name = {c.code.upper(): c.name for c in catalog.courses}

    results: List[CourseItemResponse] = []
    search_lower = search.strip().lower() if search else None
    cat_lower = category.strip().lower() if category else None

    for course in catalog.courses:
        if level is not None and course.level != level:
            continue
        if cat_lower and cat_lower not in course.category.lower():
            continue
        if search_lower and (
            search_lower not in course.code.lower()
            and search_lower not in course.name.lower()
        ):
            continue

        prereq_details = [
            PrerequisiteDetail(
                code=p_code,
                name=code_to_name.get(p_code.upper(), p_code),
            )
            for p_code in course.prerequisites
        ]
        results.append(
            CourseItemResponse(
                code=course.code,
                name=course.name,
                credit_hours=course.credit_hours,
                level=course.level,
                department=course.department,
                category=course.category,
                description=course.description or "",
                prerequisites=course.prerequisites,
                prerequisite_names=[p.name for p in prereq_details],
                prerequisites_details=prereq_details,
            )
        )

    return CoursesListResponse(total_courses=len(results), courses=results)


@app.post("/api/simulate-gpa", response_model=SimulateGPAResponse, tags=["GPA & Standing"])
def simulate_gpa(payload: SimulateGPARequest) -> SimulateGPAResponse:
    """
    Calculates projected semester & cumulative GPA and academic standing immediately
    by delegating directly to core.tools without duplicating business logic.
    """
    # Validate grades against official bylaws grading scale
    for nc in payload.new_courses:
        if nc.expected_grade.strip().upper() not in {k.upper() for k in GRADE_POINTS}:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid expected_grade '{nc.expected_grade}' for course '{nc.course_code}'.",
            )
    for rc in payload.repeat_courses:
        if rc.new_grade.strip().upper() not in {k.upper() for k in GRADE_POINTS}:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid new_grade '{rc.new_grade}' for repeated course '{rc.course_code}'.",
            )

    record = payload.student_record.to_student_record()

    with student_record_context(record):
        current_standing = analyze_academic_standing()
        projection = calculate_projected_gpa(
            new_courses=[c.model_dump() for c in payload.new_courses],
            repeat_courses=[r.model_dump() for r in payload.repeat_courses],
        )

    # Compute projected standing after applying the simulated semester
    projected_record = record.model_copy(deep=True)
    for rc in payload.repeat_courses:
        projected_record.completed_courses.append(
            CourseRecord(
                course_code=rc.course_code,
                course_title=rc.course_code,
                credit_hours=rc.credit_hours,
                grade=rc.new_grade,
                semester="Projected",
            )
        )
    for nc in payload.new_courses:
        projected_record.completed_courses.append(
            CourseRecord(
                course_code=nc.course_code,
                course_title=nc.course_code,
                credit_hours=nc.credit_hours,
                grade=nc.expected_grade,
                semester="Projected",
            )
        )
    if projected_record.completed_courses:
        projected_record.recalculate_academic_metrics()

    with student_record_context(projected_record):
        projected_standing = analyze_academic_standing()

    return SimulateGPAResponse(
        gpa_projection=projection,
        academic_standing=current_standing,
        projected_academic_standing=projected_standing,
    )


ALLOWED_TRANSCRIPT_MIMES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
}
EXT_TO_MIME = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
MAX_TRANSCRIPT_BYTES = 10 * 1024 * 1024  # 10 MB


@app.post("/api/parse-transcript", response_model=StudentRecord, tags=["Transcript"])
async def parse_transcript(file: UploadFile = File(...)) -> StudentRecord:
    """
    Accepts an uploaded transcript image or PDF, parses it via gemini-3.8-flash
    (with automatic Retry & Fallback), and returns a validated StudentRecord JSON.
    """
    server_api_key = _get_server_gemini_key()
    if not server_api_key:
        raise HTTPException(
            status_code=503,
            detail="Server GEMINI_API_KEY is not configured in environment variables.",
        )

    ext = Path(file.filename or "").suffix.lower()
    mime_type = (file.content_type or "").lower()
    if mime_type not in ALLOWED_TRANSCRIPT_MIMES:
        mime_type = EXT_TO_MIME.get(ext, "")
    if mime_type not in ALLOWED_TRANSCRIPT_MIMES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Please upload a PDF or image (PNG, JPG, WEBP).",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(file_bytes) > MAX_TRANSCRIPT_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds the 10 MB limit.")

    try:
        catalog = _load_catalog()
        extracted = parse_transcript_with_gemini(
            file_bytes=file_bytes,
            mime_type=mime_type,
            api_key=server_api_key,
            model_name="gemini-3.8-flash",
            catalog=catalog,
            max_retries=3,
        )
        return build_student_record_from_extracted(extracted)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to parse transcript via Gemini: {exc}",
        ) from exc


@app.post("/api/chat", response_model=ChatResponse, tags=["AI Advisor"])
def advisor_chat(payload: ChatRequest) -> ChatResponse:
    """
    Forwards the student's question and current record to AcademicAdvisorAgent
    using server-side GEMINI_API_KEY, college bylaws RAG, and deterministic tools.
    """
    server_api_key = _get_server_gemini_key()
    if not server_api_key:
        raise HTTPException(
            status_code=503,
            detail="Server GEMINI_API_KEY is not configured in environment variables.",
        )

    record = payload.student_record.to_student_record() if payload.student_record else None
    history_dicts = [m.model_dump() for m in payload.history]

    try:
        agent = AcademicAdvisorAgent(
            api_key=server_api_key,
            model_name=DEFAULT_MODEL,
            student_record=record,
            initial_history=history_dicts,
        )
        result = agent.send_message(payload.message)
        return ChatResponse(
            response=result.get("response", ""),
            model_used=result.get("model_used", DEFAULT_MODEL),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Advisor agent error: {exc}",
        ) from exc
