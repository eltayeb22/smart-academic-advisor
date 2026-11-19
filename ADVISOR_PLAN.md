# 🎓 Smart Academic Advisor — Architectural Blueprint & Implementation Plan

## 1. Project Overview
**Smart Academic Advisor** is an intelligent academic advising assistant built with Python, the **`google-genai`** SDK, and **Streamlit**.

Its core design separates **semantic reasoning** from **deterministic computation**:
1. **Bylaws Semantic Retrieval (RAG)**: Indexes and searches college credit-hour regulation PDFs and course descriptions.
2. **Deterministic Tool Execution (Function Calling)**: Executes exact GPA math, course repetition replacement rules, prerequisite graph checks, and credit-load limits in Python rather than leaving arithmetic to the LLM.
3. **Personalized Advising**: Reads a structured Pydantic-validated student transcript JSON to deliver tailored recommendations and interactive What-If simulations.

---

## 2. Tech Stack

| Component | Technology | Responsibility |
| :--- | :--- | :--- |
| **Language** | Python 3.10+ | Core runtime |
| **LLM SDK** | `google-genai` | Gemini Flash / Flash-Lite models with native Python tool calling |
| **Frontend UI** | `streamlit` | Interactive dashboard, editable transcript table, What-If GPA simulator, and AI chat |
| **RAG / Parsing** | `pypdf` + `chromadb` | PDF bylaws extraction, chunking, and article retrieval |
| **Data Modeling** | `pydantic` | Strict schema validation for transcripts and course catalogs |
| **Configuration** | `python-dotenv` | Environment variable management |

---

## 3. Implementation Roadmap

### Phase 1: Foundation & Data Schemas
- [x] Define architectural blueprint (`ADVISOR_PLAN.md`) and dependencies (`requirements.txt`).
- [x] Implement Pydantic schemas in `utils/transcript_parser.py` (`CourseRecord`, `RegisteredCourseRecord`, `StudentRecord`, `CourseCatalog`).
- [x] Extract full curriculum courses, credit hours, and prerequisites into `data/course_catalog.json` and `data/courses.json`.
- [x] Provide privacy-safe anonymized sample data (`data/student_record.example.json`) with local gitignored override (`data/student_record.json`).

### Phase 2: Deterministic Academic Tools (`core/tools.py`)
- [x] **`calculate_projected_gpa`**: Exact GPA computation under official 4.0 grading scale with course-retake replacement support.
- [x] **`get_eligible_courses`**: Prerequisite dependency solver, active-retake prioritization, and exclusion of currently registered courses.
- [x] **`analyze_academic_standing`**: Academic standing classification, credit-hour caps, honors eligibility, and 140-credit graduation tracking.

### Phase 3: Bylaws RAG Engine (`core/rag_engine.py`)
- [x] PDF & text extraction (`utils/pdf_loader.py`) with article-centered excerpt windowing.
- [x] Semantic vector store integration with fast keyword fallback.

### Phase 4: Gemini Agent & Reliability (`core/advisor_agent.py`)
- [x] Native Python Function Calling integration via `google-genai`.
- [x] Direct student-context injection for instant responses on current status and semester credit totals.
- [x] Zero-delay multi-model failover chain (`gemini-3.5-flash-lite` → `gemini-3.5-flash` → `gemini-3.8-flash`).

### Phase 5: Streamlit Dashboard (`app.py`)
- [x] KPI overview cards (CGPA, completed credits, active failed courses, current registered load).
- [x] AI Advisor Chat with quick-action prompts.
- [x] Editable Transcript table (`st.data_editor`) with automatic grade-point & GPA recalculation.
- [x] Deterministic What-If GPA Simulator pre-populated with current semester courses.
- [x] Searchable Course Catalog & Prerequisites tab.

### Phase 6: Verification & Future Enhancements
- [x] Automated unit test suite (`test_core.py`).
- [ ] Export personalized multi-semester graduation roadmap to PDF.
- [ ] Multi-student profile uploader & automatic SIS transcript parser.
