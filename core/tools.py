from typing import List, Dict, Optional, Any
import json
from pathlib import Path
from config import (
    GRADE_POINTS,
    PROBATION_GPA_THRESHOLD,
    MIN_CREDIT_HOURS_PER_SEMESTER,
    NORMAL_MAX_CREDIT_HOURS,
    HONOR_MAX_CREDIT_HOURS,
    PROBATION_MAX_CREDIT_HOURS,
    TOTAL_GRADUATION_CREDITS,
    STUDENT_RECORD_PATH,
    COURSE_CATALOG_PATH,
    get_student_record_path
)
from utils.transcript_parser import load_student_record, load_course_catalog, StudentRecord, CourseCatalog

def _get_active_student() -> StudentRecord:
    """Helper to load the current active student record."""
    return load_student_record(get_student_record_path())

def _get_active_catalog() -> CourseCatalog:
    """Helper to load the active course catalog."""
    return load_course_catalog(COURSE_CATALOG_PATH)

def calculate_projected_gpa(
    new_courses: List[Dict[str, Any]],
    repeat_courses: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    يحسب المعدل التراكمي المتوقع (Projected GPA) بدقة متناهية بناءً على التقديرات المتوقعة لمقررات الفصل القادم أو المقررات المعادة.
    
    Args:
        new_courses: قائمة بالمقررات الجديدة وتقديراتها المتوقعة.
                     مثال: [{"course_code": "CS301", "credit_hours": 3, "expected_grade": "A"}, {"course_code": "CS302", "credit_hours": 3, "expected_grade": "B+"}]
        repeat_courses: قائمة بالمقررات المعادة لاستبدال درجات سابقة (خصوصاً الرسوب F أو لتحسين المعدل).
                     مثال: [{"course_code": "CS205", "credit_hours": 3, "old_grade": "F", "new_grade": "B+"}]
                     
    Returns:
        قاموس يحتوي على المعدل الحالي، المعدل المتوقع، معدل الفصل، وفارق التغير في الساعات والنقاط.
    """
    student = _get_active_student()
    repeat_courses = repeat_courses or []

    # Repetition rules: Calculate baseline using latest attempt for each unique course
    unique_courses = student.get_latest_unique_courses()
    attempted_credits_before = sum(c.credit_hours for c in unique_courses.values())
    total_quality_points = sum(
        (c.points if c.points is not None else c.calculate_points())
        for c in unique_courses.values()
    )

    current_gpa = student.current_gpa if student.current_gpa > 0 else (
        round(total_quality_points / attempted_credits_before, 4) if attempted_credits_before > 0 else 0.0
    )

    # Process repeats: remove old points and add new points for repeated course slots
    adjusted_quality_points = total_quality_points
    adjusted_attempted_credits = attempted_credits_before

    repeat_details = []
    for r in repeat_courses:
        code = r.get("course_code", "").upper()
        old_grade = r.get("old_grade", "F").upper()
        new_grade = r.get("new_grade", "A").upper()
        credit = int(r.get("credit_hours", 3))

        old_points = GRADE_POINTS.get(old_grade, 0.0) * credit
        new_points = GRADE_POINTS.get(new_grade, 0.0) * credit

        # If the course was already counted in attempted credits, credits count doesn't double
        adjusted_quality_points = adjusted_quality_points - old_points + new_points
        repeat_details.append({
            "course_code": code,
            "old_grade": old_grade,
            "new_grade": new_grade,
            "points_diff": round(new_points - old_points, 4)
        })

    # Process new / registered courses
    sem_quality_points = 0.0
    sem_credits = 0
    new_details = []

    for nc in new_courses:
        code = nc.get("course_code", "").upper()
        credit = int(nc.get("credit_hours", 3))
        grade = nc.get("expected_grade", "B").upper()
        pt_rate = GRADE_POINTS.get(grade, 0.0)
        course_pts = pt_rate * credit

        sem_quality_points += course_pts
        sem_credits += credit
        new_details.append({
            "course_code": code,
            "credit_hours": credit,
            "grade": grade,
            "points": round(course_pts, 4)
        })

    total_quality_points_after = adjusted_quality_points + sem_quality_points
    total_attempted_credits_after = adjusted_attempted_credits + sem_credits

    projected_gpa = round(total_quality_points_after / total_attempted_credits_after, 4) if total_attempted_credits_after > 0 else 0.0
    semester_gpa = round(sem_quality_points / sem_credits, 4) if sem_credits > 0 else 0.0
    gpa_diff = round(projected_gpa - current_gpa, 4)

    return {
        "student_name": student.student_name,
        "current_gpa": current_gpa,
        "projected_gpa": projected_gpa,
        "gpa_difference": gpa_diff,
        "semester_gpa": semester_gpa,
        "semester_credit_hours": sem_credits,
        "total_attempted_credits_before": attempted_credits_before,
        "total_attempted_credits_after": total_attempted_credits_after,
        "new_courses_analyzed": new_details,
        "repeats_analyzed": repeat_details,
        "status_evaluation": (
            f"سيرتفع المعدل بمقدار +{gpa_diff}" if gpa_diff > 0
            else f"سينخفض المعدل بمقدار {gpa_diff}" if gpa_diff < 0
            else "سيبقى المعدل كما هو دون تغيير"
        )
    }

def get_eligible_courses(target_semester_only: bool = True) -> Dict[str, Any]:
    """
    يتحقق من سجل الطالب مقارنة بدليل المقررات ويستخرج المواد المؤهلة بفلترة ذكية سريعة في بايثون:
    1. المقررات الموصى بإعادتها فوراً كأولوية قصوى (الرسوب F).
    2. أفضل مقررات مقترحة للفصل القادم (15-18 ساعة) حسب المستوى الأكاديمي والمتطلبات.
    3. تقليل حجم البيانات المرجعة لتسريع استجابة النموذج وتفادي الضغط على السيرفر.
    
    Args:
        target_semester_only: عند تفعيلها يتم إرجاع جدول مقترح مقتضب للفصل القادم بدلاً من كامل الكتالوج.
    """
    student = _get_active_student()
    catalog = _get_active_catalog()

    passed_codes = set(student.get_passed_course_codes())
    failed_codes = set(student.get_failed_course_codes())
    registered_codes = {r.course_code for r in student.registered_courses}

    urgent_retakes = []
    for f_code in failed_codes:
        course = catalog.get_course(f_code)
        urgent_retakes.append({
            "course_code": f_code,
            "course_name": course.name if course else f_code,
            "credit_hours": course.credit_hours if course else 3,
            "reason": "مقرر رسب فيه الطالب سابقاً ويجب إعادته فوراً لفتح المتطلبات ورفع المعدل"
        })

    eligible_courses = []
    blocked_courses = []

    for course in catalog.courses:
        if course.code in passed_codes:
            continue

        if course.code in registered_codes:
            continue

        if course.code in failed_codes:
            eligible_courses.append({
                "code": course.code,
                "name": course.name,
                "credit_hours": course.credit_hours,
                "department": course.department,
                "category": course.category,
                "level": course.level,
                "status": "مقرر للإعادة (Repeat Failed Course)",
                "prerequisites": course.prerequisites
            })
            continue

        missing_prereqs = [p for p in course.prerequisites if p not in passed_codes]

        if not missing_prereqs:
            eligible_courses.append({
                "code": course.code,
                "name": course.name,
                "credit_hours": course.credit_hours,
                "department": course.department,
                "category": course.category,
                "level": course.level,
                "status": "متاح للتسجيل (Eligible)",
                "prerequisites": course.prerequisites
            })
        else:
            blocked_courses.append({
                "code": course.code,
                "name": course.name,
                "credit_hours": course.credit_hours,
                "missing_prerequisites": missing_prereqs
            })

    # Fast Python Pre-filtering for LLM context minimization
    if target_semester_only:
        target_level = student.academic_level

        # Filter: Core mandatory courses of current/lower level first (up to 5)
        core_recs = [
            c for c in eligible_courses
            if "إجباري" in c.get("category", "") and c.get("level", 1) <= target_level
        ][:5]

        # Top 2 elective choices
        elec_recs = [
            c for c in eligible_courses
            if "اختياري" in c.get("category", "")
        ][:2]

        top_schedule = core_recs + elec_recs

        return {
            "student_name": student.student_name,
            "academic_level": target_level,
            "eligible_courses_count": len(eligible_courses),
            "urgent_retakes": urgent_retakes,
            "recommended_schedule": [
                {"code": c["code"], "name": c["name"], "credits": c["credit_hours"], "type": c["category"]}
                for c in top_schedule
            ],
            "total_recommended_credits": sum(u["credit_hours"] for u in urgent_retakes) + sum(c["credit_hours"] for c in top_schedule[:4]),
            "blocked_courses": blocked_courses[:3],
            "filter_note": "تمت فلترة المواد مسبقاً في بايثون لاقتراح أفضل 5-6 مواد للفصل القادم دون تضخيم السياق."
        }

    return {
        "student_name": student.student_name,
        "completed_passed_credits": student.total_completed_credits,
        "eligible_courses_count": len(eligible_courses),
        "urgent_retakes": urgent_retakes,
        "eligible_courses": eligible_courses,
        "blocked_courses": blocked_courses
    }

def analyze_academic_standing() -> Dict[str, Any]:
    """
    يحلل الوضع الأكاديمي الحالي للطالب:
    - الحد الأدنى والأقصى للعبء الدراسي المسموح بالتسجيل فيه للفصل القادم.
    - حالة الإنذار الأكاديمي (Academic Probation) إن وجدت.
    - أهلية مرتبة الشرف (Honors Degree).
    - نسبة إنجاز متطلبات التخرج (132 ساعة).
    
    Returns:
        تقرير بالحالة الأكاديمية والحدود المسموح بها للساعات والتوصيات الإرشادية.
    """
    student = _get_active_student()
    gpa = student.current_gpa
    completed_credits = student.total_completed_credits
    has_any_courses = len(student.completed_courses) > 0

    is_probation = has_any_courses and (gpa < PROBATION_GPA_THRESHOLD)
    has_f_grades = len(student.get_failed_course_codes()) > 0

    # Determine credit limits based on college bylaws
    if not has_any_courses:
        max_credits = NORMAL_MAX_CREDIT_HOURS
        min_credits = MIN_CREDIT_HOURS_PER_SEMESTER
        standing_desc = "طالب مستجد / سجل جديد (لا توجد درجات مسجلة بعد)"
        guidance = "ابدأ بإضافة مقرراتك المنجزة أو المسجلة من تبويب (السجل الأكاديمي) ليتم حساب معدلك واقتراح خطتك بدقة."
    elif is_probation:
        max_credits = PROBATION_MAX_CREDIT_HOURS
        min_credits = MIN_CREDIT_HOURS_PER_SEMESTER
        standing_desc = "تحت الإنذار الأكاديمي (Academic Probation) - المعدل أقل من 2.00"
        guidance = "يجب التركيز على إعادة المقررات التي حصلت فيها على درجات متدنية لتفادي استمرار الإنذار وفصلك."
    elif gpa >= 3.00:
        max_credits = HONOR_MAX_CREDIT_HOURS
        min_credits = MIN_CREDIT_HOURS_PER_SEMESTER
        standing_desc = "حالة أكاديمية متميزة (Good Standing with Honors eligibility)"
        guidance = "معدلك يؤهلك لتسجيل عبء دراسي استثنائي يصل إلى 21 ساعة معتمدة إذا أردت تسريع التخرج."
    else:
        max_credits = NORMAL_MAX_CREDIT_HOURS
        min_credits = MIN_CREDIT_HOURS_PER_SEMESTER
        standing_desc = "حالة أكاديمية جيدة (Good Standing)"
        guidance = "العبء الدراسي المعتاد هو من 12 إلى 18 ساعة معتمدة."

    # Honors eligibility: GPA >= 3.50 (or new student with no grades yet) and NO F grades
    if not has_any_courses:
        honors_eligible = True
        honors_reason = "لم يتم إدخال درجات بعد؛ حافظ على معدل 3.666 فأكثر دون رسوب للتأهل لمرتبة الشرف"
    else:
        honors_eligible = (gpa >= 3.50) and (not has_f_grades)
        honors_reason = "مؤهل لمرتبة الشرف" if honors_eligible else (
            "غير مؤهل لمرتبة الشرف بسبب وجود رسوب سابق (درجة F)" if has_f_grades
            else "المعدل الحالي أقل من 3.50 المشترط لمرتبة الشرف"
        )

    remaining_credits = max(0, TOTAL_GRADUATION_CREDITS - completed_credits)
    progress_percentage = round((completed_credits / TOTAL_GRADUATION_CREDITS) * 100, 1)

    return {
        "student_id": student.student_id,
        "student_name": student.student_name,
        "current_gpa": gpa,
        "completed_credits": completed_credits,
        "remaining_credits_for_graduation": remaining_credits,
        "graduation_progress_pct": progress_percentage,
        "academic_standing": standing_desc,
        "is_under_probation": is_probation,
        "allowed_min_credits": min_credits,
        "allowed_max_credits": max_credits,
        "honors_degree_eligible": honors_eligible,
        "honors_note": honors_reason,
        "advisor_guidance": guidance
    }

# Export list of callable functions for the GenAI agent
ADVISOR_TOOLS = [
    calculate_projected_gpa,
    get_eligible_courses,
    analyze_academic_standing
]
