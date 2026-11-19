from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import json
from pathlib import Path
from config import GRADE_POINTS

class CourseRecord(BaseModel):
    course_code: str
    course_title: str
    credit_hours: int
    grade: str
    semester: str
    points: Optional[float] = None
    passed: Optional[bool] = None

    def calculate_points(self) -> float:
        grade_upper = self.grade.upper().strip()
        pt = GRADE_POINTS.get(grade_upper, 0.0)
        return round(pt * self.credit_hours, 4)

    def check_passed(self) -> bool:
        return self.grade.upper().strip() not in ["F", "(F)", "FW", "ABS", "N/A"]

class RegisteredCourseRecord(BaseModel):
    course_code: str
    course_title: str
    credit_hours: int
    semester: str = "Fall 2026/2027"
    status: str = "Registered"

class StudentRecord(BaseModel):
    student_id: str
    student_name: str
    major: str
    academic_level: int = 3
    current_gpa: float = Field(ge=0.0, le=4.0)
    total_completed_credits: int = Field(ge=0)
    total_quality_points: float = Field(ge=0.0)
    academic_standing: str = "Good Standing"
    completed_courses: List[CourseRecord] = []
    registered_courses: List[RegisteredCourseRecord] = []

    def recalculate_academic_metrics(self):
        """
        Automatically recalculates points for every course, pass/fail status,
        total earned credits, and cumulative GPA strictly following Alexandria University Bylaws.
        """
        for c in self.completed_courses:
            c.points = c.calculate_points()
            c.passed = c.check_passed()

        unique = self.get_latest_unique_courses()
        passed_courses = [c for c in unique.values() if c.passed]
        self.total_completed_credits = sum(c.credit_hours for c in passed_courses)

        total_attempted_credits = sum(c.credit_hours for c in unique.values())
        total_pts = sum(c.points for c in unique.values())
        self.total_quality_points = round(total_pts, 4)
        self.current_gpa = round(total_pts / total_attempted_credits, 4) if total_attempted_credits > 0 else 0.0

    def calculate_total_completed_credits(self) -> int:
        """Dynamically sums the credit hours of all successfully passed unique courses."""
        unique = self.get_latest_unique_courses()
        return sum(
            c.credit_hours for c in unique.values() 
            if (c.passed if c.passed is not None else c.check_passed())
        )

    def get_latest_unique_courses(self) -> Dict[str, CourseRecord]:
        """
        Returns a dictionary mapping each course_code to its latest attempt,
        following the college bylaws repetition rules.
        """
        unique_map: Dict[str, CourseRecord] = {}
        for c in self.completed_courses:
            unique_map[c.course_code] = c
        return unique_map

    def get_passed_course_codes(self) -> List[str]:
        """Returns course codes that the student has passed in any attempt."""
        passed_codes = set()
        for c in self.completed_courses:
            is_passed = c.passed if c.passed is not None else c.check_passed()
            if is_passed:
                passed_codes.add(c.course_code)
        return list(passed_codes)

    def get_failed_course_codes(self) -> List[str]:
        """
        Returns course codes currently failed and NOT yet cleared by a successful repeat.
        """
        passed = set(self.get_passed_course_codes())
        failed = set()
        for c in self.completed_courses:
            is_passed = c.passed if c.passed is not None else c.check_passed()
            if not is_passed and c.course_code not in passed:
                failed.add(c.course_code)
        return list(failed)

class CourseInfo(BaseModel):
    code: str
    name: str
    credit_hours: int
    prerequisites: List[str] = []
    department: str = "General"
    category: str = "Required"
    level: int = 1
    description: Optional[str] = ""

class CourseCatalog(BaseModel):
    courses: List[CourseInfo] = []

    def get_course(self, code: str) -> Optional[CourseInfo]:
        for c in self.courses:
            if c.code.upper() == code.upper():
                return c
        return None

def load_student_record(file_path: Path) -> StudentRecord:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    record = StudentRecord(**data)
    for c in record.completed_courses:
        c.points = c.calculate_points()
        c.passed = c.check_passed()
    return record

def save_student_record(record: StudentRecord, file_path: Path):
    """Saves the student record back to JSON."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(record.model_dump(), f, ensure_ascii=False, indent=2)

def load_course_catalog(file_path: Path) -> CourseCatalog:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return CourseCatalog(**data)
