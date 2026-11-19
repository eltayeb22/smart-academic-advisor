"use client";

import { useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  GraduationCap,
  Pencil,
  Server,
  Sparkles,
  User,
  X,
} from "lucide-react";
import type { HealthResponse, StudentRecord } from "@/lib/types";
import { getActiveFailedCodes } from "@/lib/grading";

interface HeaderKPIsProps {
  student: StudentRecord;
  health: HealthResponse | null;
  apiError: string | null;
  onUpdateProfile: (patch: Partial<StudentRecord>) => void;
}

export default function HeaderKPIs({
  student,
  health,
  apiError,
  onUpdateProfile,
}: HeaderKPIsProps) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(student.student_name);
  const [sid, setSid] = useState(student.student_id);
  const [major, setMajor] = useState(student.major);
  const [level, setLevel] = useState(student.academic_level);

  const hasCompleted = student.completed_courses.length > 0;
  const failedCodes = getActiveFailedCodes(student);
  const regCredits = student.registered_courses.reduce((sum, r) => sum + r.credit_hours, 0);
  const progressPct = Math.min(100, Math.round((student.total_completed_credits / 140) * 100));

  const openEditor = () => {
    setName(student.student_name);
    setSid(student.student_id);
    setMajor(student.major);
    setLevel(student.academic_level);
    setEditing(true);
  };

  const saveProfile = () => {
    onUpdateProfile({
      student_name: name.trim() || "طالب جديد",
      student_id: sid.trim(),
      major: major.trim() || "Data Sciences & Analytics",
      academic_level: Number(level) || 1,
    });
    setEditing(false);
  };

  return (
    <header className="space-y-5">
      {/* Top Bar */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-3.5">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500 to-indigo-600 shadow-lg shadow-sky-500/20">
            <GraduationCap className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight text-white md:text-3xl">
              Smart Academic Advisor
              <span className="mr-2 text-lg font-semibold text-sky-400">
                | المرشد الأكاديمي الذكي
              </span>
            </h1>
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-400">
              <span className="inline-flex items-center gap-1.5 text-slate-200 font-medium">
                <User className="h-3.5 w-3.5 text-sky-400" />
                {student.student_name}
              </span>
              <span>•</span>
              <span>
                الرقم الجامعي:{" "}
                <code className="rounded bg-slate-800 px-1.5 py-0.5 text-xs text-sky-300">
                  {student.student_id || "غير محدد"}
                </code>
              </span>
              <span>•</span>
              <span>التخصص: {student.major}</span>
              <span>•</span>
              <span>المستوى: {student.academic_level}</span>
              <button
                type="button"
                onClick={openEditor}
                className="inline-flex items-center gap-1 rounded-md border border-slate-700 bg-slate-800/80 px-2 py-0.5 text-xs text-sky-300 transition hover:border-sky-500 hover:bg-slate-800"
              >
                <Pencil className="h-3 w-3" />
                تعديل البيانات
              </button>
            </div>
          </div>
        </div>

        {/* Backend Health Pill */}
        <div className="flex items-center gap-2 self-start md:self-auto">
          {health ? (
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3.5 py-1.5 text-xs font-medium text-emerald-300">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <Server className="h-3.5 w-3.5" />
              <span>متصل بالنظام</span>
            </div>
          ) : apiError ? (
            <div className="inline-flex items-center gap-2 rounded-full border border-rose-500/30 bg-rose-500/10 px-3.5 py-1.5 text-xs font-medium text-rose-300">
              <AlertTriangle className="h-3.5 w-3.5" />
              <span>تعذر الاتصال بالـ API</span>
            </div>
          ) : (
            <div className="inline-flex items-center gap-2 rounded-full border border-slate-700 bg-slate-800/70 px-3.5 py-1.5 text-xs text-slate-400">
              <Sparkles className="h-3.5 w-3.5 animate-spin" />
              <span>جاري فحص السيرفر...</span>
            </div>
          )}
        </div>
      </div>

      {/* Inline Profile Editor */}
      {editing && (
        <div className="rounded-2xl border border-sky-500/30 bg-slate-900/95 p-4 shadow-xl">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-bold text-sky-300">تعديل بيانات الطالب (تُحفظ محلياً في متصفحك)</h3>
            <button
              type="button"
              onClick={() => setEditing(false)}
              className="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <label className="mb-1 block text-xs text-slate-400">اسم الطالب</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-sky-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">الرقم الجامعي</label>
              <input
                type="text"
                value={sid}
                onChange={(e) => setSid(e.target.value)}
                placeholder="مثال: 2401246443"
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-sky-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">التخصص</label>
              <input
                type="text"
                value={major}
                onChange={(e) => setMajor(e.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-sky-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">المستوى الأكاديمي</label>
              <select
                value={level}
                onChange={(e) => setLevel(Number(e.target.value))}
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-sky-500 focus:outline-none"
              >
                {[1, 2, 3, 4].map((lv) => (
                  <option key={lv} value={lv}>
                    المستوى {lv}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="mt-3 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setEditing(false)}
              className="rounded-lg border border-slate-700 px-4 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-800"
            >
              إلغاء
            </button>
            <button
              type="button"
              onClick={saveProfile}
              className="rounded-lg bg-sky-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-sky-500"
            >
              حفظ البيانات
            </button>
          </div>
        </div>
      )}

      {/* 4 KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Card 1: CGPA */}
        <div className="rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 to-slate-950 p-5 shadow-lg">
          <div className="text-xs font-medium text-slate-400">المعدل التراكمي الحالي (CGPA)</div>
          <div className="mt-2 text-3xl font-extrabold text-sky-400">
            {hasCompleted ? student.current_gpa.toFixed(4) : "—"}
          </div>
          <div className="mt-1 text-xs text-slate-500">
            إجمالي النقاط: {student.total_quality_points.toFixed(3)}
          </div>
        </div>

        {/* Card 2: Completed Credits */}
        <div className="rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 to-slate-950 p-5 shadow-lg">
          <div className="text-xs font-medium text-slate-400">الساعات المنجزة بنجاح</div>
          <div className="mt-2 flex items-baseline gap-1.5">
            <span className="text-3xl font-extrabold text-white">
              {student.total_completed_credits}
            </span>
            <span className="text-sm font-medium text-slate-500">/ 140 ساعة</span>
          </div>
          <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
            <div
              className="h-full rounded-full bg-gradient-to-l from-sky-400 to-indigo-500 transition-all duration-300"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>

        {/* Card 3: Academic Standing */}
        <div className="rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 to-slate-950 p-5 shadow-lg">
          <div className="text-xs font-medium text-slate-400">الحالة الأكاديمية</div>
          <div className="mt-2 flex items-center gap-2">
            {!hasCompleted ? (
              <>
                <BookOpen className="h-5 w-5 text-sky-400" />
                <span className="text-lg font-bold text-sky-300">سجل فارغ (أضف موادك)</span>
              </>
            ) : failedCodes.length > 0 ? (
              <>
                <AlertTriangle className="h-5 w-5 text-rose-400" />
                <span className="text-lg font-bold text-rose-400">
                  رسوب نشط ({failedCodes.length} مواد)
                </span>
              </>
            ) : (
              <>
                <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                <span className="text-lg font-bold text-emerald-400">سجل منتظم</span>
              </>
            )}
          </div>
          <div className="mt-1 text-xs text-slate-500">
            {!hasCompleted
              ? "الحد المعتاد للتسجيل: 18 ساعة"
              : student.current_gpa < 2.0
              ? "إنذار أكاديمي • الحد الأقصى 14 ساعة"
              : student.current_gpa >= 3.0
              ? "متميز • الحد الأقصى 21 ساعة"
              : "جيد • الحد الأقصى 18 ساعة"}
          </div>
        </div>

        {/* Card 4: Registered Credits */}
        <div className="rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 to-slate-950 p-5 shadow-lg">
          <div className="text-xs font-medium text-slate-400">ساعات الفصل المسجلة حالياً</div>
          <div className="mt-2 flex items-baseline gap-1.5">
            <span className="text-3xl font-extrabold text-indigo-400">{regCredits}</span>
            <span className="text-sm font-medium text-slate-500">ساعة معتمدة</span>
          </div>
          <div className="mt-1 text-xs text-slate-500">
            عدد المقررات المسجلة: {student.registered_courses.length} مقرر
          </div>
        </div>
      </div>
    </header>
  );
}
