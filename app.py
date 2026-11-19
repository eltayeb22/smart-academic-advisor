import streamlit as st
import pandas as pd
import json
import os
from pathlib import Path

# Local imports
from config import (
    LOCAL_STUDENT_RECORD_PATH,
    COURSE_CATALOG_PATH,
    BYLAWS_FILE_PATH,
    DEFAULT_MODEL,
    GEMINI_API_KEY,
    get_student_record_path
)
from utils.transcript_parser import (
    CourseRecord,
    RegisteredCourseRecord,
    load_student_record,
    load_course_catalog,
    save_student_record
)
from utils.transcript_importer import (
    export_courses_csv,
    export_student_record_json,
    parse_pasted_portal_text,
    parse_transcript_with_gemini,
    parse_uploaded_csv,
    parse_uploaded_json,
)
from core.tools import (
    calculate_projected_gpa,
    get_eligible_courses,
    analyze_academic_standing
)
from core.rag_engine import get_rag_engine
from core.advisor_agent import AcademicAdvisorAgent

# Page configuration
st.set_page_config(
    page_title="Smart Academic Advisor | المرشد الأكاديمي الذكي",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling for Arabic RTL & modern clean interface
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
    
    html, body, [class*="css"], div, span, p, h1, h2, h3, h4, h5, h6 {
        font-family: 'Cairo', sans-serif !important;
    }
    
    .stAlert {
        border-radius: 10px;
    }
    .metric-card {
        background: linear-gradient(135deg, #1e293b, #0f172a);
        color: white;
        padding: 1.2rem;
        border-radius: 12px;
        border: 1px solid #334155;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        text-align: center;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #38bdf8;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #94a3b8;
    }
    .quick-btn {
        margin: 4px;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- Session State Initialization -----------------
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "مرحباً بك! أنا **مرشدك الأكاديمي الذكي 🎓**.\nأنا هنا لمساعدتك في تخطيط مسيرتك الدراسية، اقتراح أفضل جدول دراسي بناءً على شجرة المتطلبات السابقة، ومحاكاة معدلك التراكمي (GPA) بدقة حسابية وفقاً للائحة الكلية.\n\nكيف يمكنني مساعدتك اليوم؟"
        }
    ]

if "api_key" not in st.session_state:
    st.session_state.api_key = os.getenv("GEMINI_API_KEY", "")

if "model_name" not in st.session_state:
    st.session_state.model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

# Load active data
ACTIVE_STUDENT_PATH = get_student_record_path()
try:
    student = load_student_record(ACTIVE_STUDENT_PATH)
    catalog = load_course_catalog(COURSE_CATALOG_PATH)
except Exception as e:
    st.error(f"خطأ في تحميل ملفات البيانات: {e}")
    st.stop()

# ----------------- Sidebar -----------------
with st.sidebar:
    st.image("https://img.icons8.com/isometric/100/graduation-cap.png", width=70)
    st.title("إعدادات المرشد الذكي")

    api_key_input = st.text_input(
        "مفتاح Google Gemini API:",
        value=st.session_state.api_key,
        type="password",
        help="يمكنك الحصول عليه مجاناً من Google AI Studio"
    )
    if api_key_input:
        st.session_state.api_key = api_key_input

    model_options = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash"]
    selected_model = st.selectbox(
        "نموذج Gemini المستخدم:",
        options=model_options,
        index=0 if st.session_state.model_name not in model_options else model_options.index(st.session_state.model_name)
    )
    st.session_state.model_name = selected_model

    st.divider()
    with st.expander("👤 تعديل بيانات الطالب والساعات", expanded=False):
        new_sid = st.text_input("الرقم الجامعي (Student ID):", value=student.student_id)
        new_sname = st.text_input("اسم الطالب:", value=student.student_name)
        
        dynamic_credits = student.calculate_total_completed_credits()
        new_credits = st.number_input(
            "الساعات المنجزة بنجاح:", 
            min_value=0, 
            max_value=200, 
            value=student.total_completed_credits,
            help=f"مجموع الساعات للمواد الناجحة حالياً في السجل: {dynamic_credits} ساعة"
        )
        
        if st.button("💾 حفظ البيانات الأكاديمية", use_container_width=True):
            student.student_id = str(new_sid).strip()
            student.student_name = str(new_sname).strip()
            student.total_completed_credits = int(new_credits)
            save_student_record(student, LOCAL_STUDENT_RECORD_PATH)
            st.success("تم حفظ البيانات بنجاح!")
            st.rerun()

    st.divider()
    st.subheader("📄 لائحة الكلية (Bylaws)")
    uploaded_pdf = st.file_uploader(
        "رفع لائحة جديدة (PDF أو TXT):",
        type=["pdf", "txt"],
        help="سيتم استخراج المواد والقواعد الأكاديمية تلقائياً للـ RAG"
    )

    if uploaded_pdf is not None:
        save_path = BYLAWS_FILE_PATH.parent / uploaded_pdf.name
        with open(save_path, "wb") as f:
            f.write(uploaded_pdf.getbuffer())
        # Re-initialize RAG engine
        rag = get_rag_engine()
        rag.bylaws_path = save_path
        rag._initialize_knowledge_base()
        st.success(f"تم تحديث اللائحة من: {uploaded_pdf.name}")

    st.divider()
    st.caption("نظام الإرشاد الأكاديمي الذكي v1.0\nمبني بـ Python & google-genai")

# ----------------- Main Layout Tabs -----------------
st.title("🎓 Smart Academic Advisor | المرشد الأكاديمي الذكي")
st.markdown(f"**مرحباً بك يا {student.student_name}** | الرقم الجامعي: `{student.student_id}` | التخصص: `{student.major}` | المستوى: `{student.academic_level}`")

# Overview KPI Cards
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{student.current_gpa:.4f}</div>
        <div class="metric-label">المعدل التراكمي الحالي (CGPA)</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{student.total_completed_credits} / 140</div>
        <div class="metric-label">الساعات المنجزة بنجاح</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    failed_courses = student.get_failed_course_codes()
    has_f = len(failed_courses) > 0
    standing_color = "#f43f5e" if has_f else "#10b981"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value" style="color: {standing_color}; font-size: 1.4rem; padding-top: 0.4rem;">
            {f"رسوب نشط ({len(failed_courses)} مواد)" if has_f else "سجل منتظم"}
        </div>
        <div class="metric-label">حالة الرسوب الحالية</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    reg_credits = sum(r.credit_hours for r in student.registered_courses)
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{reg_credits} ساعة</div>
        <div class="metric-label">ساعات مسجلة (Fall 2026/2027)</div>
    </div>
    """, unsafe_allow_html=True)

st.write("")

# Tabs
tab_chat, tab_transcript, tab_simulator, tab_catalog = st.tabs([
    "💬 محادثة المرشد الذكي (AI Chat)",
    "📊 السجل الأكاديمي (Transcript)",
    "🧮 محاكي الـ GPA الفوري (What-If Calculator)",
    "📚 دليل المقررات والمتطلبات (Courses & Prereqs)"
])

# ----------------- TAB 1: Chat -----------------
with tab_chat:
    st.markdown("##### 💡 استفسارات سريعة مقترحة:")
    q_col1, q_col2, q_col3, q_col4 = st.columns(4)
    
    prompt_to_send = None
    if q_col1.button("📋 اقترح لي مواد الفصل القادم", use_container_width=True):
        prompt_to_send = "ما هي المقررات التي تنصحني بتسجيلها في الفصل القادم بناءً على المتطلبات السابقة وموقفي الأكاديمي في اللائحة؟"
    if q_col2.button("⚠️ ما موقفي من مرتبة الشرف؟", use_container_width=True):
        prompt_to_send = "هل أنا مؤهل للحصول على مرتبة الشرف عند التخرج وفقاً للائحة الكلية وسجلي الحالي؟"
    if q_col3.button("🧮 احسب معدلي لو أعدت OS وجبت A", use_container_width=True):
        prompt_to_send = "لو أعدت مادة نظم التشغيل (02-24-00307) وحصلت فيها على A، وسجلت معها 4 مواد جديدة 12 ساعة وحصلت على B+، كم سيصبح معدلي التراكمي بدقة؟"
    if q_col4.button("📜 ما هي شروط الإنذار والعبء؟", use_container_width=True):
        prompt_to_send = "ما هي قواعد الإنذار الأكاديمي والحد الأقصى للساعات المسموح بها في لائحة الكلية؟"

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Handle input from user or quick buttons
    user_input = st.chat_input("اكتب استفسارك هنا للمرشد الأكاديمي...")
    final_input = prompt_to_send or user_input

    if final_input:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": final_input})
        with st.chat_message("user"):
            st.markdown(final_input)

        # Generate response using Agent
        with st.chat_message("assistant"):
            with st.spinner("جاري استشارة اللائحة وفحص السجل والأدوات..."):
                agent = AcademicAdvisorAgent(
                    api_key=st.session_state.api_key,
                    model_name=st.session_state.model_name
                )
                result = agent.send_message(final_input)
                assistant_text = result["response"]
                st.markdown(assistant_text)

        st.session_state.messages.append({"role": "assistant", "content": assistant_text})

# ----------------- TAB 2: Transcript -----------------
with tab_transcript:
    st.subheader("📊 السجل الأكاديمي المفصل (Official Transcript Record)")
    grade_options = ["A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "F", "(F)", "Abs"]

    # --- 1. Import / Export Panel ---
    with st.expander("📥 استيراد أو تصدير كشف الدرجات (Import / Export Transcript)", expanded=False):
        imp_tab_file, imp_tab_paste, imp_tab_ai, imp_tab_export = st.tabs([
            "📄 رفع ملف (CSV / JSON)",
            "📋 لصق من موقع الكلية",
            "🖼️ استخراج ذكي (PDF / صورة)",
            "⬇️ تحميل نسخة / قالب"
        ])

        with imp_tab_file:
            st.caption("ارفع ملف `student_record.json` كامل أو ملف `CSV` يحتوي على أعمدة: `course_code, course_title, credit_hours, semester, grade, status`.")
            uploaded_tr = st.file_uploader(
                "اختر ملف كشف الدرجات (JSON أو CSV):",
                type=["json", "csv"],
                key="transcript_file_uploader"
            )
            import_mode_file = st.radio(
                "طريقة الاستيراد:",
                ["استبدال السجل الحالي بالكامل", "إضافة ودمج مع السجل الحالي"],
                horizontal=True,
                key="import_mode_file"
            )
            if uploaded_tr is not None and st.button("✅ تطبيق واستيراد الملف", type="primary", key="btn_apply_file"):
                try:
                    raw_bytes = uploaded_tr.getvalue()
                    if uploaded_tr.name.lower().endswith(".json"):
                        parsed_rec = parse_uploaded_json(raw_bytes)
                        if import_mode_file == "استبدال السجل الحالي بالكامل":
                            student = parsed_rec
                        else:
                            student.completed_courses.extend(parsed_rec.completed_courses)
                            student.registered_courses.extend(parsed_rec.registered_courses)
                            student.recalculate_academic_metrics()
                    else:
                        comp_list, reg_list = parse_uploaded_csv(raw_bytes, catalog=catalog)
                        if import_mode_file == "استبدال السجل الحالي بالكامل":
                            student.completed_courses = comp_list
                            student.registered_courses = reg_list
                        else:
                            student.completed_courses.extend(comp_list)
                            student.registered_courses.extend(reg_list)
                        student.recalculate_academic_metrics()

                    save_student_record(student, LOCAL_STUDENT_RECORD_PATH)
                    st.success(f"تم استيراد كشف الدرجات بنجاح! (مكتمل: {len(student.completed_courses)} | مسجل: {len(student.registered_courses)} | GPA: {student.current_gpa:.4f})")
                    st.rerun()
                except Exception as ex:
                    st.error(f"تعذر قراءة الملف: {ex}")

        with imp_tab_paste:
            st.caption("حدد جدول المواد من بوابة الجامعة بالماوس (Ctrl+C) والصقه هنا مباشرة (Ctrl+V)، وسيتم استخراج الكود والسمستر والساعات والتقدير تلقائياً.")
            pasted_text = st.text_area(
                "الصق نص كشف الدرجات هنا:",
                height=160,
                placeholder="مثال:\n02-24-00101\tLinear Algebra\tFall 2023/2024\t3\tB\tComplete\n02-24-00203\tNumerical Computations\tFall 2026/2027\t3\tN/A\tRegistered",
                key="pasted_portal_text"
            )
            import_mode_paste = st.radio(
                "طريقة الحفظ:",
                ["استبدال السجل الحالي بالكامل", "إضافة ودمج مع السجل الحالي"],
                horizontal=True,
                key="import_mode_paste"
            )
            if st.button("🔎 استخراج وحفظ النص الملصق", type="primary", key="btn_apply_paste"):
                comp_list, reg_list = parse_pasted_portal_text(pasted_text, catalog=catalog)
                if not comp_list and not reg_list:
                    st.warning("لم يتم التعرف على أي مقررات في النص. تأكد من وجود كود المادة (مثل 02-24-00101) في كل صف.")
                else:
                    if import_mode_paste == "استبدال السجل الحالي بالكامل":
                        student.completed_courses = comp_list
                        student.registered_courses = reg_list
                    else:
                        student.completed_courses.extend(comp_list)
                        student.registered_courses.extend(reg_list)
                    student.recalculate_academic_metrics()
                    save_student_record(student, LOCAL_STUDENT_RECORD_PATH)
                    st.success(f"تم استخراج وحفظ {len(comp_list)} سجل مكتمل و {len(reg_list)} مقرر مسجل بنجاح!")
                    st.rerun()

        with imp_tab_ai:
            st.caption("ارفع ملف PDF رسمي أو لقطة شاشة واضحة ومكبرة لكشف الدرجات، وسيستخدم النظام Gemini لاستخراج جميع المقررات والتقديرات تلقائياً.")
            uploaded_media = st.file_uploader(
                "ارفع كشف الدرجات (PDF / PNG / JPG):",
                type=["pdf", "png", "jpg", "jpeg"],
                key="transcript_ai_uploader"
            )
            if uploaded_media is not None and st.button("🤖 استخراج الدرجات بالذكاء الاصطناعي", type="primary", key="btn_ai_extract"):
                if not st.session_state.api_key:
                    st.error("يرجى إدخال مفتاح Google Gemini API في الشريط الجانبي أولاً.")
                else:
                    with st.spinner("جاري قراءة كشف الدرجات واستخراج المقررات عبر Gemini..."):
                        try:
                            mime_map = {
                                ".pdf": "application/pdf",
                                ".png": "image/png",
                                ".jpg": "image/jpeg",
                                ".jpeg": "image/jpeg",
                            }
                            ext = Path(uploaded_media.name).suffix.lower()
                            extracted = parse_transcript_with_gemini(
                                file_bytes=uploaded_media.getvalue(),
                                mime_type=mime_map.get(ext, "application/octet-stream"),
                                api_key=st.session_state.api_key,
                                model_name=st.session_state.model_name,
                                catalog=catalog,
                            )
                            st.session_state["ai_extracted_transcript"] = extracted
                            st.success(
                                f"تم استخراج {len(extracted['completed_courses'])} سجل مكتمل و {len(extracted['registered_courses'])} مقرر مسجل. راجع النتيجة أدناه ثم اضغط اعتماد وحفظ."
                            )
                        except Exception as ex:
                            st.error(f"فشل الاستخراج عبر الذكاء الاصطناعي: {ex}")

            if "ai_extracted_transcript" in st.session_state:
                ext_data = st.session_state["ai_extracted_transcript"]
                if ext_data["completed_courses"]:
                    st.write("**المقررات المكتملة المستخرجة (معاينة):**")
                    st.dataframe(
                        pd.DataFrame([
                            {
                                "الكود": c.course_code,
                                "المقرر": c.course_title,
                                "الساعات": c.credit_hours,
                                "الفصل": c.semester,
                                "التقدير": c.grade,
                            }
                            for c in ext_data["completed_courses"]
                        ]),
                        use_container_width=True,
                        hide_index=True,
                    )
                if st.button("💾 اعتماد وحفظ البيانات المستخرجة في السجل", type="primary", key="btn_confirm_ai"):
                    if ext_data.get("student_name"):
                        student.student_name = ext_data["student_name"]
                    if ext_data.get("student_id"):
                        student.student_id = ext_data["student_id"]
                    if ext_data.get("major"):
                        student.major = ext_data["major"]
                    student.completed_courses = ext_data["completed_courses"]
                    student.registered_courses = ext_data["registered_courses"]
                    student.recalculate_academic_metrics()
                    save_student_record(student, LOCAL_STUDENT_RECORD_PATH)
                    del st.session_state["ai_extracted_transcript"]
                    st.success("تم حفظ السجل المستخرج بنجاح!")
                    st.rerun()

        with imp_tab_export:
            st.caption("حمّل نسخة احتياطية من سجلك الحالي أو استخدم ملف CSV كقالب جاهز لتعبئة درجاتك في Excel ثم إعادة رفعه.")
            dl_col1, dl_col2 = st.columns(2)
            with dl_col1:
                st.download_button(
                    label="⬇️ تحميل كشف الدرجات (CSV / Excel)",
                    data=export_courses_csv(student).encode("utf-8"),
                    file_name="student_transcript.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with dl_col2:
                st.download_button(
                    label="⬇️ تحميل السجل الكامل (JSON)",
                    data=export_student_record_json(student).encode("utf-8"),
                    file_name="student_record.json",
                    mime="application/json",
                    use_container_width=True,
                )

    # --- 2. Quick Add Course from Catalog ---
    with st.expander("➕ إضافة مقرر جديد بسرعة من دليل الكلية", expanded=False):
        catalog_options = [f"{c.code} | {c.name} ({c.credit_hours} س)" for c in catalog.courses]
        catalog_options.append("مقرر مخصص (إدخال يدوي)")
        selected_cat_opt = st.selectbox("اختر المقرر:", options=catalog_options, key="quick_add_course_select")

        if selected_cat_opt == "مقرر مخصص (إدخال يدوي)":
            qa_c1, qa_c2, qa_c3 = st.columns([1.2, 2.3, 0.8])
            qa_code = qa_c1.text_input("رمز المقرر:", placeholder="CS101", key="qa_custom_code")
            qa_title = qa_c2.text_input("اسم المقرر:", placeholder="Course Title", key="qa_custom_title")
            qa_hrs = qa_c3.number_input("الساعات:", min_value=0, max_value=6, value=3, key="qa_custom_hrs")
        else:
            sel_code = selected_cat_opt.split(" | ")[0].strip()
            sel_course = catalog.get_course(sel_code)
            qa_code = sel_course.code
            qa_title = sel_course.name
            qa_hrs = sel_course.credit_hours

        qa_r1, qa_r2, qa_r3 = st.columns([1.2, 1, 1])
        qa_status = qa_r1.selectbox("الحالة:", ["مكتمل (Complete)", "مسجل حالياً (Registered)"], key="qa_status")
        qa_sem = qa_r2.text_input("الفصل الدراسي:", value="Fall 2026/2027", key="qa_sem")
        qa_grade = qa_r3.selectbox(
            "التقدير:",
            options=grade_options,
            disabled=(qa_status == "مسجل حالياً (Registered)"),
            key="qa_grade"
        )

        if st.button("➕ إضافة المقرر وحفظ السجل", use_container_width=True, key="btn_quick_add"):
            if not qa_code.strip():
                st.warning("يرجى إدخال رمز المقرر.")
            else:
                if qa_status == "مسجل حالياً (Registered)":
                    student.registered_courses.append(
                        RegisteredCourseRecord(
                            course_code=qa_code.strip(),
                            course_title=qa_title.strip() or qa_code.strip(),
                            credit_hours=int(qa_hrs),
                            semester=qa_sem.strip() or "Fall 2026/2027",
                            status="Registered",
                        )
                    )
                else:
                    new_rec = CourseRecord(
                        course_code=qa_code.strip(),
                        course_title=qa_title.strip() or qa_code.strip(),
                        credit_hours=int(qa_hrs),
                        grade=qa_grade,
                        semester=qa_sem.strip() or "Fall 2026/2027",
                    )
                    new_rec.points = new_rec.calculate_points()
                    new_rec.passed = new_rec.check_passed()
                    student.completed_courses.append(new_rec)
                    student.recalculate_academic_metrics()

                save_student_record(student, LOCAL_STUDENT_RECORD_PATH)
                st.success(f"تمت إضافة المقرر {qa_code} وحفظ السجل بنجاح!")
                st.rerun()

    # --- 3. Editable Completed Courses Table ---
    st.info("💡 **يمكنك تعديل أي تقدير أو ساعة، أو إضافة صف جديد أسفل الجدول، أو حذف صف بتحديده ثم الضغط على Delete — ثم اضغط 'حفظ التعديلات' لإعادة احتساب النقاط والـ GPA فوراً.**")

    courses_data = []
    for c in student.completed_courses:
        courses_data.append({
            "رمز المقرر": c.course_code,
            "اسم المقرر": c.course_title,
            "الساعات": int(c.credit_hours),
            "الفصل الدراسي": c.semester,
            "التقدير": c.grade,
            "النقاط": round(c.calculate_points(), 3),
            "الحالة": "✅ ناجح" if c.passed else "❌ راسب (F)"
        })

    df_transcript = pd.DataFrame(courses_data) if courses_data else pd.DataFrame(
        columns=["رمز المقرر", "اسم المقرر", "الساعات", "الفصل الدراسي", "التقدير", "النقاط", "الحالة"]
    )

    edited_df = st.data_editor(
        df_transcript,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        key="transcript_data_editor",
        column_config={
            "رمز المقرر": st.column_config.TextColumn(required=True),
            "اسم المقرر": st.column_config.TextColumn(required=True),
            "الساعات": st.column_config.NumberColumn(min_value=0, max_value=6, step=1, default=3, required=True),
            "الفصل الدراسي": st.column_config.TextColumn(default="Fall 2026/2027"),
            "التقدير": st.column_config.SelectboxColumn(options=grade_options, default="B", required=True),
            "النقاط": st.column_config.NumberColumn(disabled=True, format="%.3f"),
            "الحالة": st.column_config.TextColumn(disabled=True)
        }
    )

    if st.button("💾 حفظ التعديلات وإعادة حساب النقاط والـ GPA فوراً", type="primary", use_container_width=True):
        updated_courses = []
        for _, row in edited_df.iterrows():
            code = str(row.get("رمز المقرر", "") or "").strip()
            if not code:
                continue
            title = str(row.get("اسم المقرر", "") or "").strip() or code
            hrs = int(row["الساعات"]) if pd.notna(row.get("الساعات")) else 3
            sem = str(row.get("الفصل الدراسي", "") or "Unknown").strip()
            grade = str(row.get("التقدير", "F") or "F").strip()
            updated_courses.append(
                CourseRecord(
                    course_code=code,
                    course_title=title,
                    credit_hours=hrs,
                    grade=grade,
                    semester=sem,
                )
            )

        student.completed_courses = updated_courses
        student.recalculate_academic_metrics()
        save_student_record(student, LOCAL_STUDENT_RECORD_PATH)
        st.success(f"✅ تم تحديث السجل بنجاح! الساعات المنجزة: {student.total_completed_credits} | النقاط الإجمالية: {student.total_quality_points:.3f} | الـ GPA الجديد: {student.current_gpa:.4f}")
        st.rerun()

    failed_courses = student.get_failed_course_codes()
    if failed_courses:
        st.warning(f"⚠️ **تنبيه أكاديمي:** المقررات الراسبة النشطة وغير المعادة بعد: `{', '.join(failed_courses)}`. تنص اللائحة على ضرورة إعادة تسجيل هذه المقررات لفتح المتطلبات المعتمدة عليها.")

    st.divider()

    # --- 4. Editable Current Semester Registered Courses + Complete Semester ---
    st.subheader("📝 المقررات المسجلة للفصل الحالي (Current Registered Courses)")
    reg_data = [
        {
            "رمز المقرر": r.course_code,
            "اسم المقرر": r.course_title,
            "الساعات": int(r.credit_hours),
            "الفصل الدراسي": r.semester,
            "الحالة": r.status
        }
        for r in student.registered_courses
    ]
    df_reg = pd.DataFrame(reg_data) if reg_data else pd.DataFrame(
        columns=["رمز المقرر", "اسم المقرر", "الساعات", "الفصل الدراسي", "الحالة"]
    )
    edited_reg_df = st.data_editor(
        df_reg,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        key="registered_courses_editor",
        column_config={
            "رمز المقرر": st.column_config.TextColumn(required=True),
            "اسم المقرر": st.column_config.TextColumn(required=True),
            "الساعات": st.column_config.NumberColumn(min_value=0, max_value=6, step=1, default=3, required=True),
            "الفصل الدراسي": st.column_config.TextColumn(default="Fall 2026/2027"),
            "الحالة": st.column_config.TextColumn(default="Registered", disabled=True),
        }
    )

    if st.button("💾 حفظ قائمة المقررات المسجلة", use_container_width=True, key="btn_save_registered"):
        updated_reg = []
        for _, row in edited_reg_df.iterrows():
            code = str(row.get("رمز المقرر", "") or "").strip()
            if not code:
                continue
            updated_reg.append(
                RegisteredCourseRecord(
                    course_code=code,
                    course_title=str(row.get("اسم المقرر", "") or code).strip(),
                    credit_hours=int(row["الساعات"]) if pd.notna(row.get("الساعات")) else 3,
                    semester=str(row.get("الفصل الدراسي", "") or "Fall 2026/2027").strip(),
                    status="Registered",
                )
            )
        student.registered_courses = updated_reg
        save_student_record(student, LOCAL_STUDENT_RECORD_PATH)
        st.success(f"تم حفظ المقررات المسجلة بنجاح ({len(updated_reg)} مقرر)!")
        st.rerun()

    if student.registered_courses:
        with st.expander("🎓 إنهاء الفصل الحالي ونقل المقررات المسجلة بدرجاتها للسجل", expanded=False):
            st.caption("عند صدور نتائج هذا الفصل، أدخل تقديرك الفعلي لكل مادة واضغط على الزر لنقلها تلقائياً إلى السجل المكتمل وتحديث الـ GPA.")
            final_grades_map = {}
            for idx, r in enumerate(student.registered_courses):
                fc1, fc2 = st.columns([3, 1.2])
                fc1.markdown(f"**{r.course_code}** — {r.course_title} ({r.credit_hours} ساعات)")
                final_grades_map[idx] = fc2.selectbox(
                    "التقدير النهائي:",
                    options=grade_options,
                    index=3,
                    key=f"finalize_grade_{idx}",
                    label_visibility="collapsed"
                )
            if st.button("✅ ترحيل نتائج الفصل إلى السجل المكتمل", type="primary", use_container_width=True, key="btn_finalize_sem"):
                for idx, r in enumerate(student.registered_courses):
                    student.completed_courses.append(
                        CourseRecord(
                            course_code=r.course_code,
                            course_title=r.course_title,
                            credit_hours=r.credit_hours,
                            grade=final_grades_map[idx],
                            semester=r.semester,
                        )
                    )
                student.registered_courses = []
                student.recalculate_academic_metrics()
                save_student_record(student, LOCAL_STUDENT_RECORD_PATH)
                st.success(f"تم ترحيل درجات الفصل بنجاح! الساعات المنجزة الآن: {student.total_completed_credits} | الـ GPA الجديد: {student.current_gpa:.4f}")
                st.rerun()

# ----------------- TAB 3: What-If GPA Simulator -----------------
with tab_simulator:
    st.subheader("🧮 محاكي المعدل التراكمي الفوري (Deterministic What-If Simulator)")
    st.write("تم تحميل المواد الـ 6 المسجلة للفصل الحالي (Fall 2026/2027) تلقائياً. اختر تقديراتك المتوقعة لمعرفة المعدل الناتج بدقة رقمية.")

    sim_col1, sim_col2 = st.columns([1, 2])

    with sim_col1:
        st.markdown("#### 1. إعادة المقررات الراسبة (Repeated Courses)")
        failed_codes = student.get_failed_course_codes()
        repeat_selected = []
        if failed_codes:
            for f_code in failed_codes:
                f_course = catalog.get_course(f_code)
                f_name = f_course.name if f_course else f_code
                cr = f_course.credit_hours if (f_course and f_course.credit_hours > 0) else 3
                do_rep = st.checkbox(f"إعادة مقرر: {f_name} ({f_code})", value=False, key=f"sim_chk_{f_code}")
                if do_rep:
                    rep_g = st.selectbox(f"التقدير المتوقع لـ {f_code}:", ["A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D"], index=0, key=f"sim_sel_{f_code}")
                    repeat_selected.append({
                        "course_code": f_code,
                        "credit_hours": cr,
                        "old_grade": "F",
                        "new_grade": rep_g
                    })
        else:
            st.info("لا توجد مقررات مسجل فيها رسوب نشط.")

    with sim_col2:
        st.markdown("#### 2. تقديرات المواد المسجلة للفصل الحالي (Fall 2026/2027 - 17 ساعة)")
        sim_new_courses = []
        if student.registered_courses:
            for i, reg in enumerate(student.registered_courses):
                c_col_name, c_col_hr, c_col_gr = st.columns([3, 1, 1.2])
                with c_col_name:
                    st.text_input("المقرر:", value=f"{reg.course_code} - {reg.course_title}", disabled=True, key=f"reg_lbl_{i}")
                with c_col_hr:
                    st.text_input("الساعات:", value=f"{reg.credit_hours} س", disabled=True, key=f"reg_hr_{i}")
                with c_col_gr:
                    c_gr = st.selectbox("التقدير المتوقع:", ["A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "F"], index=3, key=f"reg_gr_{i}")
                sim_new_courses.append({
                    "course_code": reg.course_code,
                    "credit_hours": reg.credit_hours,
                    "expected_grade": c_gr
                })

    if st.button("احسب المعدل المتوقع الآن", type="primary"):
        calc_result = calculate_projected_gpa(new_courses=sim_new_courses, repeat_courses=repeat_selected)

        st.success("تم الحساب الرياضي بنجاح وفقاً لقواعد اللائحة الأكاديمية!")
        res_col1, res_col2, res_col3, res_col4 = st.columns(4)
        res_col1.metric("المعدل الحالي", f"{calc_result['current_gpa']:.4f}")
        res_col2.metric("معدل الفصل المتوقع", f"{calc_result['semester_gpa']:.4f}")
        res_col3.metric(
            "المعدل التراكمي الجديد",
            f"{calc_result['projected_gpa']:.4f}",
            delta=f"{calc_result['gpa_difference']:+.4f}"
        )
        res_col4.metric("إجمالي الساعات بعد الفصل", f"{calc_result['total_attempted_credits_after']} ساعة")

# ----------------- TAB 4: Courses & Prerequisites -----------------
with tab_catalog:
    st.subheader("📚 شجرة المقررات والمتطلبات الأكاديمية (Curriculum & Prerequisites)")
    
    eligibility_info = get_eligible_courses(target_semester_only=False)
    
    st.markdown("### 🟢 المقررات المتاحة للتسجيل فوراً (استوفت الشروط):")
    eligible_df = pd.DataFrame([
        {
            "رمز المقرر": c["code"],
            "اسم المقرر": c["name"],
            "الساعات": c["credit_hours"],
            "المستوى": c["level"],
            "القسم": c["department"],
            "المتطلبات السابقة": ", ".join(c["prerequisites"]) if c["prerequisites"] else "بدون متطلب",
            "ملاحظة": c["status"]
        }
        for c in eligibility_info["eligible_courses"]
    ])
    st.dataframe(eligible_df, use_container_width=True, hide_index=True)

    st.markdown("### 🔒 المقررات المغلقة حالياً (بانتظار اجتياز المتطلب السابق):")
    blocked_df = pd.DataFrame([
        {
            "رمز المقرر": c["code"],
            "اسم المقرر": c["name"],
            "الساعات": c["credit_hours"],
            "المتطلب السابق غير المكتمل": ", ".join(c["missing_prerequisites"])
        }
        for c in eligibility_info["blocked_courses"]
    ])
    st.dataframe(blocked_df, use_container_width=True, hide_index=True)
