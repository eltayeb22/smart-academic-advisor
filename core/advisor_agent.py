import os
import time
from typing import List, Dict, Any, Optional
from config import DEFAULT_MODEL, FALLBACK_MODEL, GEMINI_API_KEY, get_student_record_path
from utils.transcript_parser import StudentRecord, load_student_record
from core.tools import (
    _get_active_student,
    calculate_projected_gpa,
    get_eligible_courses,
    analyze_academic_standing,
    student_record_context,
)
from core.rag_engine import search_college_bylaws

def build_advisor_system_instruction(student: Optional[StudentRecord] = None) -> str:
    """Builds a contextualized, compact system instruction with live student data."""
    try:
        student = student if student is not None else _get_active_student()
        reg_courses_str = ", ".join([f"{c.course_code} {c.course_title} ({c.credit_hours}س)" for c in student.registered_courses]) or "لا توجد مواد مسجلة حالياً"
        reg_hours = sum(c.credit_hours for c in student.registered_courses)
        failed_str = ", ".join(student.get_failed_course_codes()) or "لا توجد"
        record_note = (
            "تنبيه: سجل الطالب فارغ حالياً ولم يُدخل درجاته بعد. وجّهه لإضافة مقرراته أو استيرادها من تبويب (السجل الأكاديمي) إذا سأل عن حسابات تخص درجاته السابقة."
            if len(student.completed_courses) == 0 and len(student.registered_courses) == 0
            else f"عند اجتياز مواده المسجلة حالياً ({reg_hours} ساعة)، ستصبح ساعاته المنجزة = {student.total_completed_credits} + {reg_hours} = {student.total_completed_credits + reg_hours} ساعة معتمدة."
        )
        
        return f"""
أنت "المرشد الأكاديمي الذكي (Smart Academic Advisor)".
بيانات الطالب الأكاديمية المسجلة حالياً:
- اسم الطالب: {student.student_name}
- الرقم الجامعي: {student.student_id or "غير محدد"}
- التخصص: {student.major}
- المعدل التراكمي الحالي (CGPA): {student.current_gpa:.4f}
- الساعات المنجزة بنجاح حتى الآن: {student.total_completed_credits} ساعة معتمدة
- إجمالي ساعات التخرج المطلوبة: 140 ساعة معتمدة
- المقررات المسجلة حالياً في هذا الفصل ({reg_hours} ساعة معتمدة): [{reg_courses_str}]
- المقررات الراسبة حالياً وتتطلب إعادة: [{failed_str}]
- ملاحظة الحالة: {record_note}

قواعد الإرشاد والردود الفورية:
1. استخدم calculate_projected_gpa لحساب ومحاكاة الـ GPA بدقة رقمية ولا تخمن أبداً.
2. استخدم get_eligible_courses لاقتراح جدول الفصل القادم (المواد مفلترة مسبقاً في بايثون).
3. استعن بـ search_college_bylaws عند السؤال عن نصوص اللائحة والإنذارات والتخرج.
4. أسلوبك: سريع، مباشر، مختصر، مرتب، وباللغة العربية الفصحى.
"""
    except Exception:
        return """أنت المرشد الأكاديمي الذكي. ساعد الطالب باحترافية وسرعة ودقة."""

class AcademicAdvisorAgent:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        student_record: Optional[StudentRecord] = None,
        initial_history: Optional[List[Dict[str, str]]] = None,
    ):
        self.api_key = api_key or GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
        self.primary_model = model_name or DEFAULT_MODEL
        self.fallback_model = FALLBACK_MODEL or "gemini-3.5-flash-lite"
        self.active_model = self.primary_model
        self.student_record = student_record
        
        self.client = None
        self.chat = None
        self.history: List[Dict[str, str]] = list(initial_history) if initial_history else []
        
        self._initialize_client(self.active_model)

    def _initialize_client(self, model: str):
        """Initializes the google-genai client and session with tools."""
        if not self.api_key:
            return

        try:
            from google import genai
            from google.genai import types

            self.client = genai.Client(api_key=self.api_key)

            tools = [
                calculate_projected_gpa,
                get_eligible_courses,
                analyze_academic_standing,
                search_college_bylaws
            ]

            config = types.GenerateContentConfig(
                system_instruction=build_advisor_system_instruction(self.student_record),
                tools=tools,
                temperature=0.2
            )

            chat_history = []
            for msg in self.history:
                role = "model" if msg.get("role") in ("assistant", "model") else "user"
                text = str(msg.get("content", "") or "").strip()
                if text:
                    chat_history.append(
                        types.Content(role=role, parts=[types.Part.from_text(text=text)])
                    )

            self.active_model = model
            self.chat = self.client.chats.create(
                model=model,
                config=config,
                history=chat_history or None,
            )
        except Exception as e:
            print(f"Error initializing GenAI Client for model {model}: {e}")
            self.client = None
            self.chat = None

    def send_message(self, user_message: str) -> Dict[str, Any]:
        """
        Sends a message with immediate zero-latency fallback if primary model is unavailable.
        """
        if not self.client or not self.chat:
            return {
                "response": "⚠️ الرجاء إدخال مفتاح Google Gemini API Key صالح أولاً لتفعيل المرشد الأكاديمي.",
                "tools_used": [],
                "model_used": self.active_model
            }

        # Build candidate chain avoiding obsolete/deprecated models
        candidate_models = [self.primary_model]
        for m in ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash"]:
            if m not in candidate_models:
                candidate_models.append(m)

        last_error = None
        with student_record_context(self.student_record):
            for current_model in candidate_models:
                if current_model != self.active_model:
                    print(f"🔄 Switching model immediately to: {current_model}")
                    self._initialize_client(current_model)

                try:
                    response = self.chat.send_message(user_message)
                    answer_text = response.text if hasattr(response, "text") and response.text else "لم يتم الحصول على رد."

                    self.history.append({"role": "user", "content": user_message})
                    self.history.append({"role": "assistant", "content": answer_text})

                    notice = ""
                    if current_model != self.primary_model:
                        notice = f"\n\n*(⚡ تم الرد بواسطة الموديل فائق السرعة `{current_model}` لتفادي الضغط)*"

                    return {
                        "response": answer_text + notice,
                        "tools_used": [],
                        "model_used": current_model
                    }

                except Exception as e:
                    last_error = e
                    print(f"⚠️ فشل النموذج {current_model}: {e}. جاري التبديل للموديل التالي فوراً...")
                    continue

        return {
            "response": f"⚠️ تعذر إتمام الاستجابة بسبب ضغط سيرفرات Google. تفاصيل الخطأ: {str(last_error)}",
            "tools_used": [],
            "model_used": self.active_model
        }
