import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import STUDENT_RECORD_PATH, COURSE_CATALOG_PATH, BYLAWS_FILE_PATH, get_student_record_path
from utils.transcript_parser import load_student_record, load_course_catalog
from utils.transcript_importer import (
    export_courses_csv,
    export_student_record_json,
    parse_pasted_portal_text,
    parse_uploaded_csv,
    parse_uploaded_json,
)
from core.tools import calculate_projected_gpa, get_eligible_courses, analyze_academic_standing
from core.rag_engine import search_college_bylaws

def test_system():
    print("--- 1. Testing Student Record & Catalog Loading ---")
    student = load_student_record(STUDENT_RECORD_PATH)
    catalog = load_course_catalog(COURSE_CATALOG_PATH)
    print(f"Student: {student.student_name} | ID: {student.student_id} | Current GPA: {student.current_gpa}")
    print(f"Courses Completed: {len(student.completed_courses)}")
    print(f"Catalog Total Courses: {len(catalog.courses)}")
    assert len(student.completed_courses) > 0
    assert len(catalog.courses) > 0

    print("\n--- 2. Testing Academic Standing Analysis ---")
    standing = analyze_academic_standing()
    print(f"Standing: {standing['academic_standing']}")
    print(f"Max Credits: {standing['allowed_max_credits']}")
    print(f"Honors Note: {standing['honors_note']}")
    assert standing['allowed_max_credits'] == 18  # since GPA is between 2.0 and 3.0

    print("\n--- 3. Testing Eligible Courses (Prerequisites check) ---")
    eligibility = get_eligible_courses()
    print(f"Eligible courses count: {eligibility['eligible_courses_count']}")
    print(f"Urgent retakes: {[u['course_code'] for u in eligibility['urgent_retakes']]}")
    # Verify 02-24-00107 (Discrete Structures) is in urgent retakes because student got F
    assert any(u['course_code'] == '02-24-00107' for u in eligibility['urgent_retakes'])
    
    # Verify blocked courses
    blocked_codes = [b['code'] for b in eligibility['blocked_courses']]
    print(f"Blocked courses count: {len(blocked_codes)}")
    print(f"Sample Blocked courses: {blocked_codes[:5]}")

    print("\n--- 4. Testing Projected GPA Calculator ---")
    res = calculate_projected_gpa(
        new_courses=[
            {"course_code": "02-24-00203", "credit_hours": 3, "expected_grade": "A"},
            {"course_code": "02-24-00304", "credit_hours": 3, "expected_grade": "A"},
            {"course_code": "02-24-01301", "credit_hours": 3, "expected_grade": "B+"},
            {"course_code": "POM100", "credit_hours": 2, "expected_grade": "A"}
        ],
        repeat_courses=[
            {"course_code": "02-24-00107", "credit_hours": 3, "old_grade": "F", "new_grade": "B+"}
        ]
    )
    print(f"Current GPA: {res['current_gpa']}")
    print(f"Projected GPA: {res['projected_gpa']}")
    print(f"GPA Delta: {res['gpa_difference']:+}")
    print(f"Semester GPA: {res['semester_gpa']}")
    assert res['projected_gpa'] > res['current_gpa']

    print("\n--- 5. Testing Bylaws RAG Search ---")
    query_result = search_college_bylaws("مرتبة الشرف والرسوب")
    print(f"Bylaws Excerpt:\n{query_result[:300]}...")
    assert "مرتبة الشرف" in query_result

    print("\n--- 6. Testing Transcript Import / Export & Portal Paste Parser ---")
    csv_text = export_courses_csv(student)
    csv_comp, csv_reg = parse_uploaded_csv(csv_text.encode("utf-8"), catalog=catalog)
    assert len(csv_comp) == len(student.completed_courses)
    assert len(csv_reg) == len(student.registered_courses)

    json_text = export_student_record_json(student)
    reloaded = parse_uploaded_json(json_text.encode("utf-8"))
    assert reloaded.student_id == student.student_id
    assert len(reloaded.completed_courses) == len(student.completed_courses)

    sample_paste = """
    1\t02-24-00101\tLinear Algebra\tFall 2023/2024\t3\tB+\tComplete
    2\t02-24-00107\tDiscrete Structures\tSpring 2023/2024\t3\tF\tComplete
    3\t02-24-00203\tNumerical Computations\tFall 2026/2027\t3\tN/A\tRegistered
    """
    p_comp, p_reg = parse_pasted_portal_text(sample_paste, catalog=catalog)
    assert len(p_comp) == 2 and p_comp[0].grade == "B+" and p_comp[1].grade == "F"
    assert len(p_reg) == 1 and p_reg[0].course_code == "02-24-00203"
    print(f"CSV round-trip: {len(csv_comp)} completed, {len(csv_reg)} registered | Paste parser: OK")

    print("\nALL CORE LOGIC TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_system()
