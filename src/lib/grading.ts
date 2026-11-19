import type { CourseRecord, StudentRecord } from "./types";

export const GRADE_POINTS: Record<string, number> = {
  A: 4.0,
  "A-": 3.666,
  "B+": 3.333,
  B: 3.0,
  "B-": 2.666,
  "C+": 2.333,
  C: 2.0,
  "C-": 1.666,
  "D+": 1.333,
  D: 1.0,
  F: 0.0,
  "(F)": 0.0,
  Abs: 0.0,
};

export const GRADE_OPTIONS = [
  "A",
  "A-",
  "B+",
  "B",
  "B-",
  "C+",
  "C",
  "C-",
  "D+",
  "D",
  "F",
  "(F)",
  "Abs",
] as const;

export const PASSING_GRADE_OPTIONS = [
  "A",
  "A-",
  "B+",
  "B",
  "B-",
  "C+",
  "C",
  "C-",
  "D+",
  "D",
] as const;

export function isPassingGrade(grade: string): boolean {
  const norm = grade.trim().toUpperCase();
  return !["F", "(F)", "FW", "ABS", "N/A", ""].includes(norm);
}

export function calculateCoursePoints(grade: string, creditHours: number): number {
  const key = grade.trim() === "Abs" ? "Abs" : grade.trim().toUpperCase();
  const rate = GRADE_POINTS[key] ?? GRADE_POINTS[grade.trim()] ?? 0.0;
  return Number((rate * creditHours).toFixed(4));
}

export function getLatestUniqueCourses(courses: CourseRecord[]): Map<string, CourseRecord> {
  const map = new Map<string, CourseRecord>();
  for (const c of courses) {
    map.set(c.course_code.toUpperCase(), c);
  }
  return map;
}

export function getActiveFailedCodes(record: StudentRecord): string[] {
  const passed = new Set<string>();
  for (const c of record.completed_courses) {
    if (isPassingGrade(c.grade)) {
      passed.add(c.course_code.toUpperCase());
    }
  }
  const failed = new Set<string>();
  for (const c of record.completed_courses) {
    const code = c.course_code.toUpperCase();
    if (!isPassingGrade(c.grade) && !passed.has(code)) {
      failed.add(c.course_code);
    }
  }
  return Array.from(failed);
}

export function recalculateStudentRecord(record: StudentRecord): StudentRecord {
  const completed_courses = record.completed_courses.map((c) => {
    const points = calculateCoursePoints(c.grade, c.credit_hours);
    const passed = isPassingGrade(c.grade);
    return { ...c, points, passed };
  });

  const unique = getLatestUniqueCourses(completed_courses);
  let totalCompletedCredits = 0;
  let totalAttemptedCredits = 0;
  let totalQualityPoints = 0;

  for (const c of unique.values()) {
    totalAttemptedCredits += c.credit_hours;
    totalQualityPoints += c.points ?? 0;
    if (c.passed) {
      totalCompletedCredits += c.credit_hours;
    }
  }

  const currentGpa =
    totalAttemptedCredits > 0
      ? Number((totalQualityPoints / totalAttemptedCredits).toFixed(4))
      : 0.0;

  let academicStanding = "طالب مستجد (New Student)";
  if (completed_courses.length > 0) {
    academicStanding =
      currentGpa < 2.0 ? "إنذار أكاديمي (Probation)" : "حالة أكاديمية جيدة (Good Standing)";
  }

  return {
    ...record,
    completed_courses,
    total_completed_credits: totalCompletedCredits,
    total_quality_points: Number(totalQualityPoints.toFixed(4)),
    current_gpa: currentGpa,
    academic_standing: academicStanding,
  };
}

export function createEmptyStudentRecord(): StudentRecord {
  return {
    student_id: "",
    student_name: "طالب جديد",
    major: "Data Sciences & Analytics",
    academic_level: 1,
    current_gpa: 0.0,
    total_completed_credits: 0,
    total_quality_points: 0.0,
    academic_standing: "طالب مستجد (New Student)",
    completed_courses: [],
    registered_courses: [],
  };
}
