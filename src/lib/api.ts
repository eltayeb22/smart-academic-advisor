import type {
  ChatMessage,
  ChatResponse,
  CoursesListResponse,
  ExpectedCourseInput,
  HealthResponse,
  RepeatCourseInput,
  SimulateGPAResponse,
  StudentRecord,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const errBody = await res.json();
      if (typeof errBody?.detail === "string") {
        message = errBody.detail;
      } else if (Array.isArray(errBody?.detail) && errBody.detail[0]?.msg) {
        message = errBody.detail[0].msg;
      }
    } catch {
      // ignore non-JSON body
    }
    throw new Error(message);
  }
  return (await res.json()) as T;
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/api/health`, { cache: "no-store" });
  return handleResponse<HealthResponse>(res);
}

export async function fetchCourses(params?: {
  level?: number;
  search?: string;
  category?: string;
}): Promise<CoursesListResponse> {
  const qs = new URLSearchParams();
  if (params?.level) qs.set("level", String(params.level));
  if (params?.search) qs.set("search", params.search);
  if (params?.category) qs.set("category", params.category);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  const res = await fetch(`${API_BASE}/api/courses${suffix}`);
  return handleResponse<CoursesListResponse>(res);
}

export async function simulateGpa(payload: {
  student_record: StudentRecord;
  new_courses: ExpectedCourseInput[];
  repeat_courses: RepeatCourseInput[];
}): Promise<SimulateGPAResponse> {
  const res = await fetch(`${API_BASE}/api/simulate-gpa`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<SimulateGPAResponse>(res);
}

export async function parseTranscriptFile(file: File): Promise<StudentRecord> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/api/parse-transcript`, {
    method: "POST",
    body: formData,
  });
  return handleResponse<StudentRecord>(res);
}

export async function sendChatMessage(payload: {
  message: string;
  student_record: StudentRecord;
  history: ChatMessage[];
}): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: payload.message,
      student_record: payload.student_record,
      history: payload.history.map((m) => ({ role: m.role, content: m.content })),
    }),
  });
  return handleResponse<ChatResponse>(res);
}
