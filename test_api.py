import sys
from pathlib import Path
from unittest.mock import patch

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient

from api.index import app
from utils.transcript_parser import CourseRecord, RegisteredCourseRecord, StudentRecord

client = TestClient(app)


def test_api_endpoints():
    print("--- 1. Testing GET /api/health & CORS ---")
    resp = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
    assert resp.status_code == 200, resp.text
    health = resp.json()
    print("Health:", health)
    assert health["status"] == "ok"
    assert health["courses_loaded"] >= 50
    assert health["bylaws_loaded"] is True
    assert "access-control-allow-origin" in resp.headers

    print("\n--- 2. Testing GET /api/courses (with Prerequisite Names) ---")
    resp = client.get("/api/courses")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_courses"] == health["courses_loaded"]
    courses_with_prereqs = [c for c in data["courses"] if c["prerequisites"]]
    assert len(courses_with_prereqs) > 0
    sample = courses_with_prereqs[0]
    print(f"Sample course: {sample['code']} | Prereq codes: {sample['prerequisites']} | Prereq names: {sample['prerequisite_names']}")
    assert len(sample["prerequisite_names"]) == len(sample["prerequisites"])
    assert sample["prerequisite_names"][0] != sample["prerequisites"][0]

    # Test filters
    resp_lvl = client.get("/api/courses", params={"level": 1})
    assert resp_lvl.status_code == 200
    assert all(c["level"] == 1 for c in resp_lvl.json()["courses"])

    print("\n--- 3. Testing POST /api/simulate-gpa ---")
    sim_payload = {
        "student_record": {
            "student_id": "2024000101",
            "student_name": "Test Student",
            "major": "Data Sciences & Analytics",
            "completed_courses": [
                {
                    "course_code": "02-24-00101",
                    "course_title": "Linear Algebra",
                    "credit_hours": 3,
                    "grade": "B",
                    "semester": "Fall 2023/2024",
                },
                {
                    "course_code": "02-24-00107",
                    "course_title": "Discrete Structures",
                    "credit_hours": 3,
                    "grade": "F",
                    "semester": "Spring 2023/2024",
                },
            ],
            "registered_courses": [],
        },
        "new_courses": [
            {"course_code": "02-24-00103", "credit_hours": 3, "expected_grade": "A"},
            {"course_code": "02-24-00105", "credit_hours": 3, "expected_grade": "B+"},
        ],
        "repeat_courses": [
            {"course_code": "02-24-00107", "credit_hours": 3, "old_grade": "F", "new_grade": "A"}
        ],
    }
    resp = client.post("/api/simulate-gpa", json=sim_payload)
    assert resp.status_code == 200, resp.text
    sim_data = resp.json()
    print(
        f"Current GPA: {sim_data['gpa_projection']['current_gpa']} -> "
        f"Projected GPA: {sim_data['gpa_projection']['projected_gpa']} | "
        f"Standing: {sim_data['projected_academic_standing']['academic_standing']}"
    )
    assert sim_data["gpa_projection"]["projected_gpa"] > sim_data["gpa_projection"]["current_gpa"]

    # Invalid grade check
    bad_resp = client.post(
        "/api/simulate-gpa",
        json={
            "student_record": {},
            "new_courses": [{"course_code": "CS101", "credit_hours": 3, "expected_grade": "Z"}],
        },
    )
    assert bad_resp.status_code == 422

    print("\n--- 4. Testing POST /api/parse-transcript (Validation & Mocked Gemini) ---")
    bad_file = client.post(
        "/api/parse-transcript",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert bad_file.status_code in (400, 503)

    mock_extracted = {
        "student_name": "Sample Student",
        "student_id": "2024000999",
        "major": "Data Sciences & Analytics",
        "completed_courses": [
            CourseRecord(
                course_code="02-24-00101",
                course_title="Linear Algebra",
                credit_hours=3,
                grade="A",
                semester="Fall 2024/2025",
            )
        ],
        "registered_courses": [
            RegisteredCourseRecord(
                course_code="02-24-00203",
                course_title="Numerical Computations",
                credit_hours=3,
                semester="Spring 2024/2025",
            )
        ],
        "model_used": "gemini-3.8-flash",
    }
    with patch("api.index._get_server_gemini_key", return_value="test-key"), patch(
        "api.index.parse_transcript_with_gemini", return_value=mock_extracted
    ):
        ok_parse = client.post(
            "/api/parse-transcript",
            files={"file": ("transcript.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert ok_parse.status_code == 200, ok_parse.text
        parsed_student = StudentRecord(**ok_parse.json())
        assert parsed_student.total_completed_credits == 3
        assert parsed_student.current_gpa == 4.0
        print(f"Parsed StudentRecord: {parsed_student.student_name} | GPA: {parsed_student.current_gpa}")

    print("\n--- 5. Testing POST /api/chat (Mocked Advisor Agent) ---")
    with patch("api.index._get_server_gemini_key", return_value="test-key"), patch(
        "api.index.AcademicAdvisorAgent"
    ) as MockAgent:
        MockAgent.return_value.send_message.return_value = {
            "response": "معدلك التراكمي ممتاز ومؤهل لتسجيل 18 ساعة.",
            "model_used": "gemini-3.5-flash-lite",
        }
        chat_resp = client.post(
            "/api/chat",
            json={
                "message": "كم ساعة أقدر أسجل السمستر الجاي؟",
                "student_record": sim_payload["student_record"],
                "history": [{"role": "user", "content": "مرحباً"}],
            },
        )
        assert chat_resp.status_code == 200, chat_resp.text
        chat_data = chat_resp.json()
        print("Chat Response:", chat_data)
        assert chat_data["model_used"] == "gemini-3.5-flash-lite"
        assert "18" in chat_data["response"]

    print("\nALL FASTAPI ENDPOINT TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    test_api_endpoints()
