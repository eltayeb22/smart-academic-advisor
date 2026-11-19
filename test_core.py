import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import COURSE_CATALOG_PATH, EXAMPLE_STUDENT_RECORD_PATH, get_student_record_path
from utils.transcript_parser import (
    CourseRecord,
    RegisteredCourseRecord,
    StudentRecord,
    load_course_catalog,
    load_student_record,
)
from utils.transcript_importer import (
    export_courses_csv,
    export_student_record_json,
    parse_pasted_portal_text,
    parse_uploaded_csv,
    parse_uploaded_json,
)
from core.tools import (
    analyze_academic_standing,
    calculate_projected_gpa,
    get_eligible_courses,
)
from core.rag_engine import search_college_bylaws


def test_system():
    print("--- 1. Testing Student Record & Catalog Loading ---")
    student = load_student_record(get_student_record_path())
    starter = load_student_record(EXAMPLE_STUDENT_RECORD_PATH)
    catalog = load_course_catalog(COURSE_CATALOG_PATH)
    print(f"Active Student: {student.student_name} | Completed: {len(student.completed_courses)} | GPA: {student.current_gpa}")
    print(f"Starter Template Completed: {len(starter.completed_courses)} (empty by design)")
    print(f"Catalog Total Courses: {len(catalog.courses)}")
    assert len(starter.completed_courses) == 0
    assert len(starter.registered_courses) == 0
    assert len(catalog.courses) > 0

    print("\n--- 2. Testing Academic Standing Analysis ---")
    standing = analyze_academic_standing()
    print(f"Standing: {standing['academic_standing']}")
    print(f"Max Credits: {standing['allowed_max_credits']}")
    print(f"Honors Note: {standing['honors_note']}")
    assert standing["allowed_max_credits"] in (14, 18, 21)
    if len(student.completed_courses) == 0:
        assert standing["is_under_probation"] is False
        assert standing["allowed_max_credits"] == 18

    print("\n--- 3. Testing Eligible Courses (Prerequisites check) ---")
    eligibility = get_eligible_courses()
    print(f"Eligible courses count: {eligibility['eligible_courses_count']}")
    print(f"Urgent retakes: {[u['course_code'] for u in eligibility['urgent_retakes']]}")
    print(f"Blocked courses count: {len(eligibility['blocked_courses'])}")
    assert eligibility["eligible_courses_count"] > 0

    print("\n--- 4. Testing Projected GPA Calculator ---")
    res = calculate_projected_gpa(
        new_courses=[
            {"course_code": "02-24-00101", "credit_hours": 3, "expected_grade": "A"},
            {"course_code": "02-24-00102", "credit_hours": 3, "expected_grade": "A"},
            {"course_code": "02-24-00103", "credit_hours": 3, "expected_grade": "B+"},
            {"course_code": "02-24-00105", "credit_hours": 3, "expected_grade": "A"},
        ]
    )
    print(f"Current GPA: {res['current_gpa']}")
    print(f"Projected GPA: {res['projected_gpa']}")
    print(f"Semester GPA: {res['semester_gpa']}")
    assert res["projected_gpa"] >= 3.5

    print("\n--- 5. Testing Bylaws RAG Search ---")
    query_result = search_college_bylaws("مرتبة الشرف والرسوب")
    print(f"Bylaws Excerpt:\n{query_result[:250]}...")
    assert "مرتبة الشرف" in query_result

    print("\n--- 6. Testing Transcript Import / Export & Portal Paste Parser ---")
    sample_record = StudentRecord(
        student_id="2024000101",
        student_name="Test Student",
        major="Data Sciences & Analytics",
        current_gpa=0.0,
        total_completed_credits=0,
        total_quality_points=0.0,
        completed_courses=[
            CourseRecord(course_code="02-24-00101", course_title="Linear Algebra", credit_hours=3, grade="B+", semester="Fall 2023/2024"),
            CourseRecord(course_code="02-24-00102", course_title="Calculus", credit_hours=3, grade="F", semester="Fall 2023/2024"),
            CourseRecord(course_code="02-24-00102", course_title="Calculus", credit_hours=3, grade="B", semester="Spring 2023/2024"),
            CourseRecord(course_code="02-24-00107", course_title="Discrete Structures", credit_hours=3, grade="F", semester="Spring 2023/2024"),
        ],
        registered_courses=[
            RegisteredCourseRecord(course_code="02-24-00203", course_title="Numerical Computations", credit_hours=3, semester="Fall 2026/2027")
        ],
    )
    sample_record.recalculate_academic_metrics()
    assert sample_record.total_completed_credits == 6
    assert sample_record.get_failed_course_codes() == ["02-24-00107"]

    csv_text = export_courses_csv(sample_record)
    csv_comp, csv_reg = parse_uploaded_csv(csv_text.encode("utf-8"), catalog=catalog)
    assert len(csv_comp) == 4 and len(csv_reg) == 1

    json_text = export_student_record_json(sample_record)
    reloaded = parse_uploaded_json(json_text.encode("utf-8"))
    assert reloaded.student_id == "2024000101"
    assert reloaded.total_completed_credits == 6

    sample_paste = """
    1\t02-24-00101\tLinear Algebra\tFall 2023/2024\t3\tB+\tComplete
    2\t02-24-00107\tDiscrete Structures\tSpring 2023/2024\t3\tF\tComplete
    3\t02-24-00203\tNumerical Computations\tFall 2026/2027\t3\tN/A\tRegistered
    """
    p_comp, p_reg = parse_pasted_portal_text(sample_paste, catalog=catalog)
    assert len(p_comp) == 2 and p_comp[0].grade == "B+" and p_comp[1].grade == "F"
    assert len(p_reg) == 1 and p_reg[0].course_code == "02-24-00203"
    print("CSV/JSON round-trip, repetition math, and portal paste parser: OK")

    print("\nALL CORE LOGIC TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    test_system()
