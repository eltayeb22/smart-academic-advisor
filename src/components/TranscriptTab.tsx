"use client";

import { useEffect, useState } from "react";
import {
  CheckCircle2,
  FileUp,
  GraduationCap,
  Loader2,
  Plus,
  RotateCcw,
  Trash2,
  Upload,
} from "lucide-react";
import { parseTranscriptFile } from "@/lib/api";
import {
  GRADE_OPTIONS,
  calculateCoursePoints,
  createEmptyStudentRecord,
  isPassingGrade,
  recalculateStudentRecord,
} from "@/lib/grading";
import type {
  CourseItem,
  CourseRecord,
  RegisteredCourseRecord,
  StudentRecord,
} from "@/lib/types";

interface TranscriptTabProps {
  student: StudentRecord;
  courses: CourseItem[];
  onChangeStudent: (updated: StudentRecord) => void;
}

export default function TranscriptTab({
  student,
  courses,
  onChangeStudent,
}: TranscriptTabProps) {
  // Quick add state
  const [selectedCode, setSelectedCode] = useState<string>(courses[0]?.code ?? "CUSTOM");
  const [customCode, setCustomCode] = useState("");
  const [customTitle, setCustomTitle] = useState("");
  const [customCredits, setCustomCredits] = useState(3);
  const [addStatus, setAddStatus] = useState<"Complete" | "Registered">("Complete");
  const [addSemester, setAddSemester] = useState("Fall 2026/2027");
  const [addGrade, setAddGrade] = useState("B+");

  useEffect(() => {
    if (courses.length > 0 && selectedCode === "CUSTOM" && !customCode) {
      setSelectedCode(courses[0].code);
    }
  }, [courses, selectedCode, customCode]);

  // AI OCR upload state
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  // Finalize semester grades map
  const [finalizeOpen, setFinalizeOpen] = useState(false);
  const [finalGrades, setFinalGrades] = useState<Record<number, string>>({});

  const handleAddCourse = () => {
    let code = "";
    let title = "";
    let creditHours = 3;

    if (selectedCode === "CUSTOM" || !courses.length) {
      code = customCode.trim();
      title = customTitle.trim() || code;
      creditHours = Number(customCredits) || 3;
    } else {
      const found = courses.find((c) => c.code === selectedCode);
      if (!found) return;
      code = found.code;
      title = found.name;
      creditHours = found.credit_hours;
    }

    if (!code) return;

    if (addStatus === "Registered") {
      const nextReg: RegisteredCourseRecord = {
        course_code: code,
        course_title: title,
        credit_hours: creditHours,
        semester: addSemester.trim() || "Current",
        status: "Registered",
      };
      onChangeStudent({
        ...student,
        registered_courses: [...student.registered_courses, nextReg],
      });
    } else {
      const nextCompleted: CourseRecord = {
        course_code: code,
        course_title: title,
        credit_hours: creditHours,
        grade: addGrade,
        semester: addSemester.trim() || "Unknown",
      };
      onChangeStudent(
        recalculateStudentRecord({
          ...student,
          completed_courses: [...student.completed_courses, nextCompleted],
        })
      );
    }

    if (selectedCode === "CUSTOM") {
      setCustomCode("");
      setCustomTitle("");
    }
  };

  const handleUpdateCompleted = (
    idx: number,
    patch: Partial<CourseRecord>
  ) => {
    const next = student.completed_courses.map((c, i) =>
      i === idx ? { ...c, ...patch } : c
    );
    onChangeStudent(
      recalculateStudentRecord({
        ...student,
        completed_courses: next,
      })
    );
  };

  const handleDeleteCompleted = (idx: number) => {
    const next = student.completed_courses.filter((_, i) => i !== idx);
    onChangeStudent(
      recalculateStudentRecord({
        ...student,
        completed_courses: next,
      })
    );
  };

  const handleDeleteRegistered = (idx: number) => {
    const next = student.registered_courses.filter((_, i) => i !== idx);
    onChangeStudent({
      ...student,
      registered_courses: next,
    });
  };

  const handleUploadTranscript = async (file: File | undefined) => {
    if (!file) return;
    setUploading(true);
    setUploadMsg(null);
    try {
      const parsed = await parseTranscriptFile(file);
      const merged: StudentRecord = recalculateStudentRecord({
        ...student,
        student_name:
          parsed.student_name && parsed.student_name !== "Student"
            ? parsed.student_name
            : student.student_name,
        student_id: parsed.student_id || student.student_id,
        major: parsed.major || student.major,
        academic_level: parsed.academic_level || student.academic_level,
        completed_courses: parsed.completed_courses,
        registered_courses: parsed.registered_courses,
      });
      onChangeStudent(merged);
      setUploadMsg({
        type: "ok",
        text: `تم استخراج ${parsed.completed_courses.length} مقرر مكتمل و ${parsed.registered_courses.length} مقرر مسجل بنجاح وتحديث المعدل التراكمي تلقائياً!`,
      });
    } catch (err) {
      setUploadMsg({
        type: "err",
        text: err instanceof Error ? err.message : "فشل تحليل ملف كشف الدرجات.",
      });
    } finally {
      setUploading(false);
    }
  };

  const handleFinalizeSemester = () => {
    const moved: CourseRecord[] = student.registered_courses.map((r, idx) => ({
      course_code: r.course_code,
      course_title: r.course_title,
      credit_hours: r.credit_hours,
      semester: r.semester,
      grade: finalGrades[idx] || "B",
    }));
    onChangeStudent(
      recalculateStudentRecord({
        ...student,
        completed_courses: [...student.completed_courses, ...moved],
        registered_courses: [],
      })
    );
    setFinalGrades({});
    setFinalizeOpen(false);
  };

  const handleResetAll = () => {
    onChangeStudent({
      ...createEmptyStudentRecord(),
      student_name: student.student_name,
      student_id: student.student_id,
      major: student.major,
      academic_level: student.academic_level,
    });
  };

  return (
    <div className="space-y-6">
      {/* Row 1: AI Upload + Quick Add */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* Upload PDF/Image Card */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 lg:col-span-5">
          <div className="flex items-center gap-2 text-sm font-bold text-white">
            <FileUp className="h-4 w-4 text-sky-400" />
            استيراد تلقائي من كشف الدرجات (PDF أو صورة)
          </div>
          <p className="mt-1 text-xs text-slate-400">
            ارفع صورة واضحة أو PDF لكشف درجاتك ليقوم Gemini باستخراج المواد والتقديرات وحساب النقاط
            وفق اللائحة تلقائياً.
          </p>

          <label className="mt-4 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-700 bg-slate-950/60 px-4 py-6 text-center transition hover:border-sky-500/70 hover:bg-slate-900">
            {uploading ? (
              <div className="flex flex-col items-center gap-2 text-sky-300">
                <Loader2 className="h-6 w-6 animate-spin" />
                <span className="text-xs font-medium">جاري تحليل كشف الدرجات عبر Gemini...</span>
              </div>
            ) : (
              <>
                <Upload className="h-6 w-6 text-sky-400" />
                <span className="mt-2 text-xs font-semibold text-slate-200">
                  اضغط لاختيار ملف (PDF, PNG, JPG)
                </span>
                <span className="mt-1 text-[11px] text-slate-500">الحد الأقصى 10 ميجابايت</span>
              </>
            )}
            <input
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.webp"
              disabled={uploading}
              className="hidden"
              onChange={(e) => {
                handleUploadTranscript(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
          </label>

          {uploadMsg && (
            <div
              className={`mt-3 rounded-xl px-3 py-2 text-xs ${
                uploadMsg.type === "ok"
                  ? "border border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                  : "border border-rose-500/30 bg-rose-500/10 text-rose-300"
              }`}
            >
              {uploadMsg.text}
            </div>
          )}
        </div>

        {/* Quick Add Course Card */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 lg:col-span-7">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-bold text-white">
              <Plus className="h-4 w-4 text-emerald-400" />
              إضافة مقرر من دليل الكلية مباشرة
            </div>
            {(student.completed_courses.length > 0 || student.registered_courses.length > 0) && (
              <button
                type="button"
                onClick={handleResetAll}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-700 px-2.5 py-1 text-xs text-slate-300 hover:border-rose-500/50 hover:text-rose-300"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                تفريغ الجدول
              </button>
            )}
          </div>

          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <label className="mb-1 block text-xs text-slate-400">اختر المقرر</label>
              <select
                value={selectedCode}
                onChange={(e) => setSelectedCode(e.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-sky-500 focus:outline-none"
              >
                {courses.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.code} — {c.name} ({c.credit_hours} ساعات)
                  </option>
                ))}
                <option value="CUSTOM">+ مقرر مخصص (إدخال يدوي)</option>
              </select>
            </div>

            {(selectedCode === "CUSTOM" || !courses.length) && (
              <>
                <div>
                  <label className="mb-1 block text-xs text-slate-400">رمز المقرر</label>
                  <input
                    type="text"
                    value={customCode}
                    onChange={(e) => setCustomCode(e.target.value)}
                    placeholder="مثال: CS101"
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-sky-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-400">اسم المقرر</label>
                  <input
                    type="text"
                    value={customTitle}
                    onChange={(e) => setCustomTitle(e.target.value)}
                    placeholder="مثال: برمجة متقدمة"
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-sky-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-400">عدد الساعات</label>
                  <input
                    type="number"
                    min={0}
                    max={6}
                    value={customCredits}
                    onChange={(e) => setCustomCredits(Number(e.target.value))}
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-sky-500 focus:outline-none"
                  />
                </div>
              </>
            )}

            <div>
              <label className="mb-1 block text-xs text-slate-400">الحالة</label>
              <select
                value={addStatus}
                onChange={(e) => setAddStatus(e.target.value as "Complete" | "Registered")}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-sky-500 focus:outline-none"
              >
                <option value="Complete">مكتمل بدرجة (Complete)</option>
                <option value="Registered">مسجل للفصل الحالي (Registered)</option>
              </select>
            </div>

            <div>
              <label className="mb-1 block text-xs text-slate-400">الفصل الدراسي</label>
              <input
                type="text"
                value={addSemester}
                onChange={(e) => setAddSemester(e.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-sky-500 focus:outline-none"
              />
            </div>

            {addStatus === "Complete" && (
              <div>
                <label className="mb-1 block text-xs text-slate-400">التقدير (وفق المادة 9)</label>
                <select
                  value={addGrade}
                  onChange={(e) => setAddGrade(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-sky-500 focus:outline-none"
                >
                  {GRADE_OPTIONS.map((g) => (
                    <option key={g} value={g}>
                      {g}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          <button
            type="button"
            onClick={handleAddCourse}
            className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-500"
          >
            <Plus className="h-4 w-4" />
            إضافة المقرر وحساب النقاط تلقائياً
          </button>
        </div>
      </div>

      {/* Row 2: Completed Courses Editable Table */}
      <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/60">
        <div className="flex items-center justify-between border-b border-slate-800 px-5 py-3.5">
          <h3 className="text-sm font-bold text-white">
            المقررات المكتملة ({student.completed_courses.length})
          </h3>
          <span className="text-xs text-slate-400">
            تُحسب النقاط تلقائياً بضرب وزن التقدير في عدد الساعات
          </span>
        </div>

        {student.completed_courses.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <GraduationCap className="mx-auto h-10 w-10 text-slate-600" />
            <p className="mt-3 text-sm font-medium text-slate-300">
              الجدول فارغ حالياً — ابدأ بإضافة مقرراتك من الأعلى أو ارفع كشف درجاتك.
            </p>
            <p className="mt-1 text-xs text-slate-500">
              تُحفظ بياناتك محلياً في متصفحك فقط ولا تُشارك مع أي شخص آخر.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-sm">
              <thead className="bg-slate-950/70 text-xs text-slate-400">
                <tr>
                  <th className="px-4 py-3">الكود</th>
                  <th className="px-4 py-3">اسم المقرر</th>
                  <th className="px-4 py-3">الساعات</th>
                  <th className="px-4 py-3">الفصل</th>
                  <th className="px-4 py-3">التقدير</th>
                  <th className="px-4 py-3">النقاط</th>
                  <th className="px-4 py-3">الحالة</th>
                  <th className="px-4 py-3">حذف</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80">
                {student.completed_courses.map((c, idx) => {
                  const pts = calculateCoursePoints(c.grade, c.credit_hours);
                  const passed = isPassingGrade(c.grade);
                  return (
                    <tr key={`${c.course_code}-${idx}`} className="hover:bg-slate-800/40">
                      <td className="px-4 py-2.5 font-mono text-xs text-sky-300">
                        {c.course_code}
                      </td>
                      <td className="px-4 py-2.5 font-medium text-slate-100">{c.course_title}</td>
                      <td className="px-4 py-2.5">
                        <input
                          type="number"
                          min={0}
                          max={6}
                          value={c.credit_hours}
                          onChange={(e) =>
                            handleUpdateCompleted(idx, {
                              credit_hours: Math.max(0, Math.min(6, Number(e.target.value))),
                            })
                          }
                          className="w-16 rounded-lg border border-slate-700 bg-slate-950 px-2 py-1 text-center text-xs text-white focus:border-sky-500 focus:outline-none"
                        />
                      </td>
                      <td className="px-4 py-2.5">
                        <input
                          type="text"
                          value={c.semester}
                          onChange={(e) =>
                            handleUpdateCompleted(idx, { semester: e.target.value })
                          }
                          className="w-32 rounded-lg border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-200 focus:border-sky-500 focus:outline-none"
                        />
                      </td>
                      <td className="px-4 py-2.5">
                        <select
                          value={c.grade}
                          onChange={(e) => handleUpdateCompleted(idx, { grade: e.target.value })}
                          className="rounded-lg border border-slate-700 bg-slate-950 px-2 py-1 text-xs font-semibold text-white focus:border-sky-500 focus:outline-none"
                        >
                          {GRADE_OPTIONS.map((g) => (
                            <option key={g} value={g}>
                              {g}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-2.5 font-mono text-xs text-slate-300">
                        {pts.toFixed(3)}
                      </td>
                      <td className="px-4 py-2.5">
                        <span
                          className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                            passed
                              ? "bg-emerald-500/15 text-emerald-300"
                              : "bg-rose-500/15 text-rose-300"
                          }`}
                        >
                          {passed ? "ناجح" : "راسب"}
                        </span>
                      </td>
                      <td className="px-4 py-2.5">
                        <button
                          type="button"
                          onClick={() => handleDeleteCompleted(idx)}
                          className="rounded-lg p-1.5 text-slate-400 hover:bg-rose-500/10 hover:text-rose-400"
                          title="حذف المقرر"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Row 3: Registered Current Semester Courses */}
      <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/60">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 px-5 py-3.5">
          <h3 className="text-sm font-bold text-white">
            المقررات المسجلة للفصل الحالي ({student.registered_courses.length})
          </h3>
          {student.registered_courses.length > 0 && (
            <button
              type="button"
              onClick={() => setFinalizeOpen((v) => !v)}
              className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500"
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              إنهاء الفصل وترحيل الدرجات
            </button>
          )}
        </div>

        {student.registered_courses.length === 0 ? (
          <div className="px-6 py-8 text-center text-xs text-slate-500">
            لا توجد مقررات مسجلة للفصل الحالي بعد. يمكنك إضافتها من بطاقة الإضافة بالأعلى لتظهر
            تلقائياً في محاكي الـ GPA.
          </div>
        ) : (
          <div className="divide-y divide-slate-800/80">
            {student.registered_courses.map((r, idx) => (
              <div
                key={`${r.course_code}-${idx}`}
                className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 text-sm"
              >
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs text-indigo-300">{r.course_code}</span>
                  <span className="font-medium text-slate-100">{r.course_title}</span>
                  <span className="rounded-md bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
                    {r.credit_hours} ساعات
                  </span>
                  <span className="text-xs text-slate-500">{r.semester}</span>
                </div>
                <button
                  type="button"
                  onClick={() => handleDeleteRegistered(idx)}
                  className="rounded-lg p-1.5 text-slate-400 hover:bg-rose-500/10 hover:text-rose-400"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}

        {finalizeOpen && student.registered_courses.length > 0 && (
          <div className="border-t border-indigo-500/30 bg-indigo-950/20 p-5">
            <h4 className="text-xs font-bold text-indigo-300">
              أدخل التقدير النهائي لكل مقرر لترحيل الفصل إلى السجل المكتمل:
            </h4>
            <div className="mt-3 space-y-2.5">
              {student.registered_courses.map((r, idx) => (
                <div key={idx} className="flex items-center justify-between gap-3">
                  <span className="text-sm text-slate-200">
                    {r.course_code} — {r.course_title} ({r.credit_hours}س)
                  </span>
                  <select
                    value={finalGrades[idx] || "B"}
                    onChange={(e) =>
                      setFinalGrades((prev) => ({ ...prev, [idx]: e.target.value }))
                    }
                    className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-1 text-xs font-semibold text-white"
                  >
                    {GRADE_OPTIONS.map((g) => (
                      <option key={g} value={g}>
                        {g}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
            <button
              type="button"
              onClick={handleFinalizeSemester}
              className="mt-4 w-full rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
            >
              تأكيد ترحيل الدرجات وتحديث المعدل
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
