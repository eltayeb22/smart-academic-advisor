import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Base directories
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Default File Paths
LOCAL_STUDENT_RECORD_PATH = DATA_DIR / "student_record.json"
EXAMPLE_STUDENT_RECORD_PATH = DATA_DIR / "student_record.example.json"

def get_student_record_path() -> Path:
    """Returns the user's private local transcript if present, otherwise the sample demo record."""
    return LOCAL_STUDENT_RECORD_PATH if LOCAL_STUDENT_RECORD_PATH.exists() else EXAMPLE_STUDENT_RECORD_PATH

STUDENT_RECORD_PATH = get_student_record_path()
COURSE_CATALOG_PATH = DATA_DIR / "course_catalog.json"
_pdf_bylaws = DATA_DIR / "لائحة كلية الحاسبات وعلوم البيانات.pdf"
BYLAWS_FILE_PATH = _pdf_bylaws if _pdf_bylaws.exists() else (DATA_DIR / "college_bylaws.txt")
CHROMA_PERSIST_DIR = DATA_DIR / "chroma_db"

# Gemini API Configurations
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash")

# Alexandria University 4.0 GPA Grading Scale (Article 9 of Bylaws)
GRADE_POINTS = {
    "A": 4.000,
    "A-": 3.666,
    "B+": 3.333,
    "B": 3.000,
    "B-": 2.666,
    "C+": 2.333,
    "C": 2.000,
    "C-": 1.666,
    "D+": 1.333,
    "D": 1.000,
    "F": 0.000,
    "(F)": 0.000,
    "Abs": 0.000,
    "ABS": 0.000,
    "A+": 4.000,  # Alias
}

# Academic Regulations Rules
PROBATION_GPA_THRESHOLD = 2.00
MIN_CREDIT_HOURS_PER_SEMESTER = 12
NORMAL_MAX_CREDIT_HOURS = 18
HONOR_MAX_CREDIT_HOURS = 21       # If GPA >= 3.0
PROBATION_MAX_CREDIT_HOURS = 14     # If GPA < 2.0
TOTAL_GRADUATION_CREDITS = 140
