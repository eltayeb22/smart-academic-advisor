import csv
import io
import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from config import DEFAULT_MODEL, GRADE_POINTS
from utils.transcript_parser import (
    CourseCatalog,
    CourseRecord,
    RegisteredCourseRecord,
    StudentRecord,
)

VALID_GRADES = set(GRADE_POINTS.keys()) | {"N/A", "NA", ""}

COURSE_CODE_REGEX = re.compile(
    r"\b(?:\d{2}-\d{2}-\d{5}|\d{9}|[A-Za-z]{2,6}\d{1,4})\b"
)
SEMESTER_REGEX = re.compile(
    r"\b(?:Fall|Spring|Summer)\s+\d{4}(?:/\d{4})?\b", re.IGNORECASE
)
GRADE_TOKEN_REGEX = re.compile(
    r"^(?:A\+|A-|A|B\+|B-|B|C\+|C-|C|D\+|D|\(F\)|F|Abs|ABS|N/A|NA)$",
    re.IGNORECASE,
)


def normalize_grade(raw: str) -> str:
    """Normalizes a letter grade string to match the official bylaws grading scale."""
    g = str(raw or "").strip()
    if not g:
        return "N/A"
    upper = g.upper()
    if upper == "ABS":
        return "Abs"
    if upper == "(F)":
        return "(F)"
    if upper in {"N/A", "NA", "-"}:
        return "N/A"
    if upper == "A+":
        return "A"
    return upper if upper in GRADE_POINTS else "N/A"


def export_student_record_json(record: StudentRecord) -> str:
    """Serializes the student record to pretty-printed UTF-8 JSON."""
    return json.dumps(record.model_dump(), ensure_ascii=False, indent=2)


def export_courses_csv(record: StudentRecord) -> str:
    """Exports completed and registered courses as a UTF-8 CSV (Excel compatible)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["course_code", "course_title", "credit_hours", "semester", "grade", "status"]
    )
    for c in record.completed_courses:
        writer.writerow(
            [
                c.course_code,
                c.course_title,
                int(c.credit_hours),
                c.semester,
                c.grade,
                "Complete",
            ]
        )
    for r in record.registered_courses:
        writer.writerow(
            [
                r.course_code,
                r.course_title,
                int(r.credit_hours),
                r.semester,
                "N/A",
                "Registered",
            ]
        )
    return "\ufeff" + buffer.getvalue()


def parse_uploaded_json(file_bytes: bytes) -> StudentRecord:
    """Parses and validates an uploaded student_record.json file."""
    text = _decode_bytes(file_bytes)
    data = json.loads(text)
    record = StudentRecord(**data)
    record.recalculate_academic_metrics()
    return record


def parse_uploaded_csv(
    file_bytes: bytes, catalog: Optional[CourseCatalog] = None
) -> Tuple[List[CourseRecord], List[RegisteredCourseRecord]]:
    """
    Parses an uploaded CSV transcript (English or Arabic headers) into
    completed courses and currently registered courses.
    """
    text = _decode_bytes(file_bytes)
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("CSV file has no header row.")

    col_map = _map_csv_columns(reader.fieldnames)
    if "course_code" not in col_map:
        raise ValueError(
            "CSV must include a course code column (e.g., course_code, code, رمز المقرر)."
        )

    completed: List[CourseRecord] = []
    registered: List[RegisteredCourseRecord] = []

    for row in reader:
        code = str(row.get(col_map["course_code"], "") or "").strip()
        if not code:
            continue

        catalog_course = catalog.get_course(code) if catalog else None

        title = str(row.get(col_map.get("course_title", ""), "") or "").strip()
        if not title:
            title = catalog_course.name if catalog_course else code

        raw_hrs = str(row.get(col_map.get("credit_hours", ""), "") or "").strip()
        if raw_hrs.isdigit():
            hrs = int(raw_hrs)
        elif catalog_course is not None:
            hrs = int(catalog_course.credit_hours)
        else:
            hrs = 3

        semester = str(row.get(col_map.get("semester", ""), "") or "").strip() or "Unknown"
        raw_grade = str(row.get(col_map.get("grade", ""), "") or "").strip()
        raw_status = str(row.get(col_map.get("status", ""), "") or "").strip().lower()

        grade = normalize_grade(raw_grade)
        is_registered = (
            "register" in raw_status
            or "مسجل" in raw_status
            or "current" in raw_status
            or (grade == "N/A" and "complete" not in raw_status)
        )

        if is_registered:
            registered.append(
                RegisteredCourseRecord(
                    course_code=code,
                    course_title=title,
                    credit_hours=hrs,
                    semester=semester,
                    status="Registered",
                )
            )
        else:
            rec = CourseRecord(
                course_code=code,
                course_title=title,
                credit_hours=hrs,
                grade=grade if grade != "N/A" else "F",
                semester=semester,
            )
            rec.points = rec.calculate_points()
            rec.passed = rec.check_passed()
            completed.append(rec)

    return completed, registered


def parse_pasted_portal_text(
    raw_text: str, catalog: Optional[CourseCatalog] = None
) -> Tuple[List[CourseRecord], List[RegisteredCourseRecord]]:
    """
    Parses raw text copied and pasted directly from a university SIS portal table
    (tab-separated or space/newline-separated rows).
    """
    completed: List[CourseRecord] = []
    registered: List[RegisteredCourseRecord] = []

    if not raw_text or not raw_text.strip():
        return completed, registered

    # Group lines into logical entries starting with a course code or row number + course code
    raw_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    merged_rows: List[str] = []

    for line in raw_lines:
        # Skip obvious header/footer lines
        lower = line.lower()
        if any(
            skip in lower
            for skip in ["showing ", "displaying ", "previous", "s#\t", "course\tsemester"]
        ):
            continue

        if COURSE_CODE_REGEX.search(line):
            merged_rows.append(line)
        elif merged_rows:
            merged_rows[-1] = f"{merged_rows[-1]}\t{line}"

    for row_text in merged_rows:
        code_match = COURSE_CODE_REGEX.search(row_text)
        if not code_match:
            continue
        code = code_match.group(0).strip()
        # Normalize 9-digit Alexandria code like 020000001 -> 02-00-00001 if present in catalog
        if re.fullmatch(r"\d{9}", code):
            hyphenated = f"{code[:2]}-{code[2:4]}-{code[4:]}"
            if catalog and catalog.get_course(hyphenated):
                code = hyphenated

        catalog_course = catalog.get_course(code) if catalog else None

        # Extract semester
        sem_match = SEMESTER_REGEX.search(row_text)
        semester = sem_match.group(0).strip() if sem_match else "Unknown"

        # Tokenize by tabs or multiple spaces
        tokens = [t.strip() for t in re.split(r"\t+|\s{2,}", row_text) if t.strip()]
        flat_tokens = [t.strip() for t in re.split(r"[\t\s]+", row_text) if t.strip()]

        # Status detection
        row_lower = row_text.lower()
        is_registered = "registered" in row_lower or "مسجل" in row_lower

        # Grade detection (scan from the right)
        detected_grade = "N/A"
        for tok in reversed(flat_tokens):
            if GRADE_TOKEN_REGEX.match(tok):
                detected_grade = normalize_grade(tok)
                break

        # Credit hours detection (look for single digit 0-6 after semester or in tokens)
        hrs: Optional[int] = None
        after_sem = row_text[sem_match.end() :] if sem_match else row_text[code_match.end() :]
        for tok in re.split(r"[\t\s]+", after_sem.strip()):
            if re.fullmatch(r"[0-6]", tok):
                hrs = int(tok)
                break
        if hrs is None:
            hrs = int(catalog_course.credit_hours) if catalog_course else 3

        # Title extraction
        if catalog_course:
            title = catalog_course.name
        else:
            # Try to grab text between code and semester
            start_idx = code_match.end()
            end_idx = sem_match.start() if sem_match else len(row_text)
            candidate_title = re.sub(r"[\t\s]+", " ", row_text[start_idx:end_idx]).strip(" -|")
            title = candidate_title if len(candidate_title) >= 2 else code

        if is_registered or (detected_grade == "N/A" and "complete" not in row_lower):
            registered.append(
                RegisteredCourseRecord(
                    course_code=code,
                    course_title=title,
                    credit_hours=hrs,
                    semester=semester,
                    status="Registered",
                )
            )
        else:
            rec = CourseRecord(
                course_code=code,
                course_title=title,
                credit_hours=hrs,
                grade=detected_grade if detected_grade != "N/A" else "F",
                semester=semester,
            )
            rec.points = rec.calculate_points()
            rec.passed = rec.check_passed()
            completed.append(rec)

    return completed, registered


def parse_transcript_with_gemini(
    file_bytes: bytes,
    mime_type: str,
    api_key: str,
    model_name: Optional[str] = "gemini-3.8-flash",
    catalog: Optional[CourseCatalog] = None,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Uses Google Gemini multimodal structured output to extract student metadata,
    completed courses, and registered courses from an uploaded transcript PDF or image.
    Includes automatic retry with backoff and fallback model chain on 503/429 errors.
    """
    if not api_key:
        raise ValueError("A valid Google Gemini API Key is required for AI transcript extraction.")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    extraction_prompt = """
You are a precise university transcript parser. Extract ALL courses from the attached transcript document/image into strict JSON with this exact schema:
{
  "student_name": "string or empty if not shown",
  "student_id": "string or empty if not shown",
  "major": "string or empty if not shown",
  "completed_courses": [
    {
      "course_code": "string",
      "course_title": "string",
      "credit_hours": 3,
      "semester": "e.g. Fall 2024/2025",
      "grade": "one of A, A-, B+, B, B-, C+, C, C-, D+, D, F, (F), Abs"
    }
  ],
  "registered_courses": [
    {
      "course_code": "string",
      "course_title": "string",
      "credit_hours": 3,
      "semester": "e.g. Fall 2026/2027",
      "status": "Registered"
    }
  ]
}
Rules:
1. Keep every attempt of repeated courses as separate entries in completed_courses (oldest attempt first, latest attempt last).
2. Courses with Status 'Registered' or Grade 'N/A' belong in registered_courses.
3. Return ONLY valid JSON matching the schema above.
"""

    candidate_models = []
    for m in [model_name or "gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.5-flash"]:
        if m and m not in candidate_models:
            candidate_models.append(m)

    last_error = None
    raw_json_text = None
    model_used = candidate_models[0]

    part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)

    for current_model in candidate_models:
        for attempt in range(1, max_retries + 1):
            try:
                response = client.models.generate_content(
                    model=current_model,
                    contents=[part, extraction_prompt],
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        response_mime_type="application/json",
                    ),
                )
                raw_json_text = response.text
                if raw_json_text:
                    model_used = current_model
                    break
            except Exception as e:
                last_error = e
                err_lower = str(e).lower()
                is_transient = any(
                    tag in err_lower
                    for tag in ("503", "unavailable", "429", "resourceexhausted", "overloaded", "timeout")
                )
                if is_transient and attempt < max_retries:
                    time.sleep(0.8 * attempt)
                    continue
                break
        if raw_json_text:
            break

    if not raw_json_text:
        raise RuntimeError(f"Failed to extract transcript via Gemini: {last_error}")

    # Clean potential markdown fences
    cleaned = raw_json_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.DOTALL).strip()

    parsed = json.loads(cleaned)

    completed_records: List[CourseRecord] = []
    for item in parsed.get("completed_courses", []):
        code = str(item.get("course_code", "")).strip()
        if not code:
            continue
        cat_match = catalog.get_course(code) if catalog else None
        hrs = int(item.get("credit_hours", cat_match.credit_hours if cat_match else 3))
        grade = normalize_grade(item.get("grade", "F"))
        if grade == "N/A":
            grade = "F"
        rec = CourseRecord(
            course_code=code,
            course_title=str(item.get("course_title") or (cat_match.name if cat_match else code)).strip(),
            credit_hours=hrs,
            grade=grade,
            semester=str(item.get("semester", "Unknown")).strip(),
        )
        rec.points = rec.calculate_points()
        rec.passed = rec.check_passed()
        completed_records.append(rec)

    registered_records: List[RegisteredCourseRecord] = []
    for item in parsed.get("registered_courses", []):
        code = str(item.get("course_code", "")).strip()
        if not code:
            continue
        cat_match = catalog.get_course(code) if catalog else None
        hrs = int(item.get("credit_hours", cat_match.credit_hours if cat_match else 3))
        registered_records.append(
            RegisteredCourseRecord(
                course_code=code,
                course_title=str(item.get("course_title") or (cat_match.name if cat_match else code)).strip(),
                credit_hours=hrs,
                semester=str(item.get("semester", "Current")).strip(),
                status="Registered",
            )
        )

    return {
        "student_name": str(parsed.get("student_name", "") or "").strip(),
        "student_id": str(parsed.get("student_id", "") or "").strip(),
        "major": str(parsed.get("major", "") or "").strip(),
        "completed_courses": completed_records,
        "registered_courses": registered_records,
        "model_used": model_used,
    }


def build_student_record_from_extracted(extracted: Dict[str, Any]) -> StudentRecord:
    """Converts extracted transcript dict into a fully calculated StudentRecord."""
    record = StudentRecord(
        student_id=extracted.get("student_id") or "",
        student_name=extracted.get("student_name") or "Student",
        major=extracted.get("major") or "Data Sciences & Analytics",
        academic_level=1,
        current_gpa=0.0,
        total_completed_credits=0,
        total_quality_points=0.0,
        academic_standing="Good Standing",
        completed_courses=extracted.get("completed_courses", []),
        registered_courses=extracted.get("registered_courses", []),
    )
    record.recalculate_academic_metrics()
    # Infer academic level from completed credits (35 credits per level in 140-credit program)
    credits = record.total_completed_credits
    if credits >= 105:
        record.academic_level = 4
    elif credits >= 70:
        record.academic_level = 3
    elif credits >= 35:
        record.academic_level = 2
    else:
        record.academic_level = 1

    if not record.completed_courses:
        record.academic_standing = "New Student"
    elif record.current_gpa < 2.0:
        record.academic_standing = "Academic Probation"
    else:
        record.academic_standing = "Good Standing"
    return record


def _decode_bytes(file_bytes: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1256", "latin-1"):
        try:
            return file_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return file_bytes.decode("utf-8", errors="replace")


def _map_csv_columns(fieldnames: List[str]) -> Dict[str, str]:
    """Maps English or Arabic CSV header variations to canonical keys."""
    aliases = {
        "course_code": {"course_code", "code", "course code", "رمز المقرر", "كود المادة", "الكود"},
        "course_title": {"course_title", "title", "name", "course_name", "course", "اسم المقرر", "اسم المادة"},
        "credit_hours": {"credit_hours", "credits", "hrs", "hours", "الساعات", "عدد الساعات"},
        "semester": {"semester", "term", "الفصل الدراسي", "السمستر"},
        "grade": {"grade", "letter_grade", "التقدير", "الدرجة"},
        "status": {"status", "الحالة"},
    }
    mapped: Dict[str, str] = {}
    for raw_name in fieldnames:
        normalized = raw_name.strip().lower()
        for canonical, opts in aliases.items():
            if normalized in opts and canonical not in mapped:
                mapped[canonical] = raw_name
                break
    return mapped
