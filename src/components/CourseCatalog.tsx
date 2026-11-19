"use client";

import { useMemo, useState } from "react";
import { BookOpen, CheckCircle2, Clock, Lock, Search } from "lucide-react";
import { isPassingGrade } from "@/lib/grading";
import type { CourseItem, StudentRecord } from "@/lib/types";

interface CourseCatalogProps {
  courses: CourseItem[];
  student: StudentRecord;
}

export default function CourseCatalog({ courses, student }: CourseCatalogProps) {
  const [search, setSearch] = useState("");
  const [levelFilter, setLevelFilter] = useState<number | "ALL">("ALL");

  const passedSet = useMemo(() => {
    const s = new Set<string>();
    for (const c of student.completed_courses) {
      if (isPassingGrade(c.grade)) s.add(c.course_code.toUpperCase());
    }
    return s;
  }, [student.completed_courses]);

  const registeredSet = useMemo(() => {
    return new Set(student.registered_courses.map((r) => r.course_code.toUpperCase()));
  }, [student.registered_courses]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return courses.filter((c) => {
      if (levelFilter !== "ALL" && c.level !== levelFilter) return false;
      if (
        q &&
        !c.code.toLowerCase().includes(q) &&
        !c.name.toLowerCase().includes(q) &&
        !c.prerequisite_names.some((p) => p.toLowerCase().includes(q))
      ) {
        return false;
      }
      return true;
    });
  }, [courses, search, levelFilter]);

  return (
    <div className="space-y-5">
      {/* Search & Level Filter */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="ابحث بكود المادة أو اسمها أو المتطلب السابق..."
            className="w-full rounded-xl border border-slate-700 bg-slate-900/90 py-2.5 pr-10 pl-4 text-sm text-white placeholder:text-slate-500 focus:border-sky-500 focus:outline-none"
          />
        </div>

        <div className="flex flex-wrap gap-1.5">
          {(["ALL", 1, 2, 3, 4] as const).map((lvl) => (
            <button
              key={String(lvl)}
              type="button"
              onClick={() => setLevelFilter(lvl)}
              className={`rounded-xl px-3.5 py-2 text-xs font-semibold transition ${
                levelFilter === lvl
                  ? "bg-sky-600 text-white"
                  : "border border-slate-800 bg-slate-900 text-slate-300 hover:border-slate-700"
              }`}
            >
              {lvl === "ALL" ? `الكل (${courses.length})` : `المستوى ${lvl}`}
            </button>
          ))}
        </div>
      </div>

      {/* Courses Grid */}
      <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2">
        {filtered.map((course) => {
          const codeUp = course.code.toUpperCase();
          const isPassed = passedSet.has(codeUp);
          const isRegistered = registeredSet.has(codeUp);
          const missingPrereqs = course.prerequisites_details.filter(
            (p) => !passedSet.has(p.code.toUpperCase())
          );
          const isEligible = !isPassed && !isRegistered && missingPrereqs.length === 0;

          return (
            <div
              key={course.code}
              className="flex flex-col justify-between rounded-2xl border border-slate-800 bg-slate-900/70 p-4 transition hover:border-slate-700"
            >
              <div>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="font-mono text-xs font-semibold text-sky-400">
                      {course.code}
                    </span>
                    <h4 className="mt-0.5 text-sm font-bold text-white">{course.name}</h4>
                  </div>

                  {isPassed ? (
                    <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-emerald-500/15 px-2.5 py-1 text-[11px] font-semibold text-emerald-300">
                      <CheckCircle2 className="h-3 w-3" />
                      مكتمل
                    </span>
                  ) : isRegistered ? (
                    <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-indigo-500/15 px-2.5 py-1 text-[11px] font-semibold text-indigo-300">
                      <Clock className="h-3 w-3" />
                      مسجل حالياً
                    </span>
                  ) : isEligible ? (
                    <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-sky-500/15 px-2.5 py-1 text-[11px] font-semibold text-sky-300">
                      <BookOpen className="h-3 w-3" />
                      متاح للتسجيل
                    </span>
                  ) : (
                    <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-amber-500/15 px-2.5 py-1 text-[11px] font-semibold text-amber-300">
                      <Lock className="h-3 w-3" />
                      مغلق
                    </span>
                  )}
                </div>

                <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-slate-400">
                  <span className="rounded-md bg-slate-800 px-2 py-0.5">
                    {course.credit_hours} ساعات
                  </span>
                  <span className="rounded-md bg-slate-800 px-2 py-0.5">
                    المستوى {course.level}
                  </span>
                  <span className="rounded-md bg-slate-800 px-2 py-0.5">{course.category}</span>
                </div>
              </div>

              <div className="mt-3 border-t border-slate-800/80 pt-2.5 text-xs">
                <span className="text-slate-400">المتطلبات السابقة: </span>
                {course.prerequisites_details.length === 0 ? (
                  <span className="text-emerald-400">بدون متطلب سابق</span>
                ) : (
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {course.prerequisites_details.map((p) => {
                      const done = passedSet.has(p.code.toUpperCase());
                      return (
                        <span
                          key={p.code}
                          className={`inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-[11px] ${
                            done
                              ? "border border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                              : "border border-amber-500/30 bg-amber-500/10 text-amber-200"
                          }`}
                        >
                          {p.name}
                        </span>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
