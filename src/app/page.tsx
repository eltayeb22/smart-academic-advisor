"use client";

import { useEffect, useState } from "react";
import { BookOpen, Calculator, FileSpreadsheet, MessageSquare } from "lucide-react";
import HeaderKPIs from "@/components/HeaderKPIs";
import AdvisorChat from "@/components/AdvisorChat";
import TranscriptTab from "@/components/TranscriptTab";
import GpaSimulator from "@/components/GpaSimulator";
import CourseCatalog from "@/components/CourseCatalog";
import { fetchCourses, fetchHealth } from "@/lib/api";
import { createEmptyStudentRecord, recalculateStudentRecord } from "@/lib/grading";
import type { CourseItem, HealthResponse, StudentRecord } from "@/lib/types";

const STORAGE_KEY = "smart_academic_advisor_student_v1";

type TabId = "chat" | "transcript" | "simulator" | "catalog";

export default function HomePage() {
  const [activeTab, setActiveTab] = useState<TabId>("transcript");
  const [student, setStudent] = useState<StudentRecord>(() => createEmptyStudentRecord());
  const [hydrated, setHydrated] = useState(false);

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [courses, setCourses] = useState<CourseItem[]>([]);
  const [apiError, setApiError] = useState<string | null>(null);

  // Load saved local transcript from browser localStorage (starts empty on first visit)
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as StudentRecord;
        setStudent(recalculateStudentRecord(parsed));
      }
    } catch {
      // ignore corrupt storage
    } finally {
      setHydrated(true);
    }
  }, []);

  // Persist changes locally in browser localStorage
  useEffect(() => {
    if (!hydrated) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(student));
    } catch {
      // ignore storage quota errors
    }
  }, [student, hydrated]);

  // Load API health & curriculum courses
  useEffect(() => {
    let active = true;
    Promise.all([fetchHealth(), fetchCourses()])
      .then(([h, c]) => {
        if (!active) return;
        setHealth(h);
        setCourses(c.courses);
        setApiError(null);
      })
      .catch((err) => {
        if (!active) return;
        setApiError(err instanceof Error ? err.message : "Failed to connect to FastAPI backend");
      });
    return () => {
      active = false;
    };
  }, []);

  const handleUpdateProfile = (patch: Partial<StudentRecord>) => {
    setStudent((prev) => ({ ...prev, ...patch }));
  };

  const tabs: { id: TabId; label: string; icon: React.ReactNode }[] = [
    { id: "chat", label: "محادثة المرشد الذكي", icon: <MessageSquare className="h-4 w-4" /> },
    { id: "transcript", label: "السجل الأكاديمي", icon: <FileSpreadsheet className="h-4 w-4" /> },
    { id: "simulator", label: "محاكي الـ GPA الفوري", icon: <Calculator className="h-4 w-4" /> },
    { id: "catalog", label: "دليل المقررات والمتطلبات", icon: <BookOpen className="h-4 w-4" /> },
  ];

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <HeaderKPIs
        student={student}
        health={health}
        apiError={apiError}
        onUpdateProfile={handleUpdateProfile}
      />

      {/* Navigation Tabs */}
      <nav className="mt-7 flex flex-wrap gap-2 border-b border-slate-800 pb-3">
        {tabs.map((t) => {
          const active = activeTab === t.id;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => setActiveTab(t.id)}
              className={`inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition ${
                active
                  ? "bg-sky-600 text-white shadow-lg shadow-sky-600/20"
                  : "border border-slate-800 bg-slate-900/80 text-slate-300 hover:border-slate-700 hover:text-white"
              }`}
            >
              {t.icon}
              {t.label}
            </button>
          );
        })}
      </nav>

      {/* Active Tab Content */}
      <section className="mt-6">
        {activeTab === "chat" && <AdvisorChat student={student} />}
        {activeTab === "transcript" && (
          <TranscriptTab student={student} courses={courses} onChangeStudent={setStudent} />
        )}
        {activeTab === "simulator" && <GpaSimulator student={student} courses={courses} />}
        {activeTab === "catalog" && <CourseCatalog courses={courses} student={student} />}
      </section>
    </main>
  );
}
