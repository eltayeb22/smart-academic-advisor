"use client";

import { useState, useEffect } from "react";
import { Calculator, Loader2, Plus, Trash2, TrendingDown, TrendingUp } from "lucide-react";
import { simulateGpa } from "@/lib/api";
import {
  GRADE_OPTIONS,
  PASSING_GRADE_OPTIONS,
  getActiveFailedCodes,
} from "@/lib/grading";
import type {
  CourseItem,
  ExpectedCourseInput,
  RepeatCourseInput,
  SimulateGPAResponse,
  StudentRecord,
} from "@/lib/types";

interface GpaSimulatorProps {
  student: StudentRecord;
  courses: CourseItem[];
}

export default function GpaSimulator({ student, courses }: GpaSimulatorProps) {
  const failedCodes = getActiveFailedCodes(student);
  const [selectedRepeats, setSelectedRepeats] = useState<Record<string, boolean>>({});
  const [repeatGrades, setRepeatGrades] = useState<Record<string, string>>({});

  const [simCourses, setSimCourses] = useState<ExpectedCourseInput[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SimulateGPAResponse | null>(null);

  useEffect(() => {
    if (student.registered_courses.length > 0) {
      setSimCourses(
        student.registered_courses.map((r) => ({
          course_code: `${r.course_code} - ${r.course_title}`,
          credit_hours: r.credit_hours,
          expected_grade: "B",
        }))
      );
    } else if (simCourses.length === 0) {
      setSimCourses([
        { course_code: "Course 1", credit_hours: 3, expected_grade: "A" },
        { course_code: "Course 2", credit_hours: 3, expected_grade: "B+" },
        { course_code: "Course 3", credit_hours: 3, expected_grade: "B" },
        { course_code: "Course 4", credit_hours: 3, expected_grade: "B+" },
      ]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [student.registered_courses]);

  const handleAddSimRow = () => {
    setSimCourses((prev) => [
      ...prev,
      { course_code: `Course ${prev.length + 1}`, credit_hours: 3, expected_grade: "B" },
    ]);
  };

  const handleCalculate = async () => {
    setLoading(true);
    setError(null);
    try {
      const repeats: RepeatCourseInput[] = failedCodes
        .filter((code) => selectedRepeats[code])
        .map((code) => {
          const catMatch = courses.find((c) => c.code.toUpperCase() === code.toUpperCase());
          return {
            course_code: code,
            credit_hours: catMatch && catMatch.credit_hours > 0 ? catMatch.credit_hours : 3,
            old_grade: "F",
            new_grade: repeatGrades[code] || "A",
          };
        });

      const res = await simulateGpa({
        student_record: student,
        new_courses: simCourses,
        repeat_courses: repeats,
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر حساب المعدل المتوقع.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        {/* Left: Repeated Failed Courses */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 lg:col-span-4">
          <h3 className="text-sm font-bold text-white">1. إعادة المقررات الراسبة</h3>
          <p className="mt-1 text-xs text-slate-400">
            عند إعادة مقرر راسب (F)، يتم استبدال درجته القديمة بالتقدير الجديد وفق قواعد اللائحة.
          </p>

          {failedCodes.length === 0 ? (
            <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-xs text-slate-400">
              لا توجد مقررات راسبة نشطة في سجلك الحالي.
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              {failedCodes.map((code) => {
                const cat = courses.find((c) => c.code.toUpperCase() === code.toUpperCase());
                const checked = Boolean(selectedRepeats[code]);
                return (
                  <div
                    key={code}
                    className="rounded-xl border border-slate-800 bg-slate-950/70 p-3 space-y-2"
                  >
                    <label className="flex cursor-pointer items-center gap-2 text-xs font-medium text-slate-200">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(e) =>
                          setSelectedRepeats((prev) => ({ ...prev, [code]: e.target.checked }))
                        }
                        className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-sky-500"
                      />
                      <span>
                        {code} — {cat ? cat.name : code}
                      </span>
                    </label>
                    {checked && (
                      <div className="flex items-center justify-between pt-1">
                        <span className="text-[11px] text-slate-400">التقدير المتوقع:</span>
                        <select
                          value={repeatGrades[code] || "A"}
                          onChange={(e) =>
                            setRepeatGrades((prev) => ({ ...prev, [code]: e.target.value }))
                          }
                          className="rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-1 text-xs font-semibold text-white"
                        >
                          {PASSING_GRADE_OPTIONS.map((g) => (
                            <option key={g} value={g}>
                              {g}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right: Expected Semester Courses */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 lg:col-span-8">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-white">
                2. تقديرات المقررات المتوقعة للفصل ({simCourses.length} مقررات)
              </h3>
              <p className="mt-1 text-xs text-slate-400">
                {student.registered_courses.length > 0
                  ? "تم تحميل مقرراتك المسجلة للفصل الحالي تلقائياً — عدّل التقديرات المتوقعة."
                  : "أضف أو عدّل المقررات وساعاتها وتقديراتها المتوقعة لمحاكاة معدلك التراكمي."}
              </p>
            </div>
            <button
              type="button"
              onClick={handleAddSimRow}
              className="inline-flex items-center gap-1 rounded-xl border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-medium text-sky-300 hover:border-sky-500"
            >
              <Plus className="h-3.5 w-3.5" />
              إضافة مقرر
            </button>
          </div>

          <div className="mt-4 space-y-2.5">
            {simCourses.map((item, idx) => (
              <div
                key={idx}
                className="grid grid-cols-12 items-center gap-2 rounded-xl border border-slate-800 bg-slate-950/60 p-2.5"
              >
                <input
                  type="text"
                  value={item.course_code}
                  onChange={(e) =>
                    setSimCourses((prev) =>
                      prev.map((c, i) => (i === idx ? { ...c, course_code: e.target.value } : c))
                    )
                  }
                  className="col-span-6 rounded-lg border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs text-white focus:border-sky-500 focus:outline-none"
                />
                <input
                  type="number"
                  min={1}
                  max={6}
                  value={item.credit_hours}
                  onChange={(e) =>
                    setSimCourses((prev) =>
                      prev.map((c, i) =>
                        i === idx
                          ? { ...c, credit_hours: Math.max(1, Math.min(6, Number(e.target.value))) }
                          : c
                      )
                    )
                  }
                  className="col-span-2 rounded-lg border border-slate-800 bg-slate-900 px-2 py-1.5 text-center text-xs text-white focus:border-sky-500 focus:outline-none"
                />
                <select
                  value={item.expected_grade}
                  onChange={(e) =>
                    setSimCourses((prev) =>
                      prev.map((c, i) =>
                        i === idx ? { ...c, expected_grade: e.target.value } : c
                      )
                    )
                  }
                  className="col-span-3 rounded-lg border border-slate-800 bg-slate-900 px-2.5 py-1.5 text-xs font-semibold text-white focus:border-sky-500 focus:outline-none"
                >
                  {GRADE_OPTIONS.map((g) => (
                    <option key={g} value={g}>
                      {g}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => setSimCourses((prev) => prev.filter((_, i) => i !== idx))}
                  className="col-span-1 flex justify-center rounded-lg p-1.5 text-slate-400 hover:bg-rose-500/10 hover:text-rose-400"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>

          <button
            type="button"
            disabled={loading || simCourses.length === 0}
            onClick={handleCalculate}
            className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-sky-600 px-4 py-3 text-sm font-bold text-white shadow-lg shadow-sky-600/20 transition hover:bg-sky-500 disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Calculator className="h-4 w-4" />
            )}
            احسب المعدل المتوقع والوضع الأكاديمي الآن
          </button>

          {error && (
            <div className="mt-3 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-2.5 text-xs text-rose-300">
              {error}
            </div>
          )}
        </div>
      </div>

      {/* Results Banner */}
      {result && (
        <div className="rounded-2xl border border-sky-500/30 bg-gradient-to-br from-slate-900 to-slate-950 p-6 shadow-xl">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-4">
            <h3 className="text-base font-bold text-sky-300">نتائج المحاكاة الرقمية الدقيقة</h3>
            <span className="rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-1 text-xs font-semibold text-sky-300">
              {result.gpa_projection.status_evaluation}
            </span>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
              <div className="text-xs text-slate-400">المعدل التراكمي الحالي</div>
              <div className="mt-1.5 text-2xl font-bold text-slate-200">
                {result.gpa_projection.current_gpa.toFixed(4)}
              </div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
              <div className="text-xs text-slate-400">معدل الفصل المتوقع</div>
              <div className="mt-1.5 text-2xl font-bold text-indigo-400">
                {result.gpa_projection.semester_gpa.toFixed(4)}
              </div>
            </div>
            <div className="rounded-xl border border-sky-500/40 bg-sky-500/10 p-4">
              <div className="text-xs text-sky-200">المعدل التراكمي الجديد</div>
              <div className="mt-1.5 flex items-center gap-2">
                <span className="text-2xl font-extrabold text-white">
                  {result.gpa_projection.projected_gpa.toFixed(4)}
                </span>
                <span
                  className={`inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-xs font-bold ${
                    result.gpa_projection.gpa_difference >= 0
                      ? "bg-emerald-500/20 text-emerald-300"
                      : "bg-rose-500/20 text-rose-300"
                  }`}
                >
                  {result.gpa_projection.gpa_difference >= 0 ? (
                    <TrendingUp className="h-3 w-3" />
                  ) : (
                    <TrendingDown className="h-3 w-3" />
                  )}
                  {result.gpa_projection.gpa_difference >= 0 ? "+" : ""}
                  {result.gpa_projection.gpa_difference.toFixed(4)}
                </span>
              </div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
              <div className="text-xs text-slate-400">العبء المسموح بعد الفصل</div>
              <div className="mt-1.5 text-2xl font-bold text-emerald-400">
                {result.projected_academic_standing.allowed_max_credits} ساعة
              </div>
            </div>
          </div>

          <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-xs text-slate-300 space-y-1">
            <div>
              <strong className="text-white">الوضع الأكاديمي المتوقع:</strong>{" "}
              {result.projected_academic_standing.academic_standing}
            </div>
            <div>
              <strong className="text-white">مرتبة الشرف:</strong>{" "}
              {result.projected_academic_standing.honors_note}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
