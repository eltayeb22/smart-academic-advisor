export interface CourseRecord {
  course_code: string;
  course_title: string;
  credit_hours: number;
  grade: string;
  semester: string;
  points?: number;
  passed?: boolean;
}

export interface RegisteredCourseRecord {
  course_code: string;
  course_title: string;
  credit_hours: number;
  semester: string;
  status: string;
}

export interface StudentRecord {
  student_id: string;
  student_name: string;
  major: string;
  academic_level: number;
  current_gpa: number;
  total_completed_credits: number;
  total_quality_points: number;
  academic_standing: string;
  completed_courses: CourseRecord[];
  registered_courses: RegisteredCourseRecord[];
}

export interface PrerequisiteDetail {
  code: string;
  name: string;
}

export interface CourseItem {
  code: string;
  name: string;
  credit_hours: number;
  level: number;
  department: string;
  category: string;
  description: string;
  prerequisites: string[];
  prerequisite_names: string[];
  prerequisites_details: PrerequisiteDetail[];
}

export interface CoursesListResponse {
  total_courses: number;
  courses: CourseItem[];
}

export interface HealthResponse {
  status: string;
  courses_loaded: number;
  bylaws_loaded: boolean;
  gemini_configured: boolean;
  default_chat_model: string;
}

export interface ExpectedCourseInput {
  course_code: string;
  credit_hours: number;
  expected_grade: string;
}

export interface RepeatCourseInput {
  course_code: string;
  credit_hours: number;
  old_grade: string;
  new_grade: string;
}

export interface SimulateGPAResponse {
  gpa_projection: {
    student_name: string;
    current_gpa: number;
    projected_gpa: number;
    gpa_difference: number;
    semester_gpa: number;
    semester_credit_hours: number;
    total_attempted_credits_before: number;
    total_attempted_credits_after: number;
    status_evaluation: string;
  };
  academic_standing: {
    academic_standing: string;
    allowed_min_credits: number;
    allowed_max_credits: number;
    honors_degree_eligible: boolean;
    honors_note: string;
    advisor_guidance: string;
  };
  projected_academic_standing: {
    academic_standing: string;
    allowed_min_credits: number;
    allowed_max_credits: number;
    honors_degree_eligible: boolean;
    honors_note: string;
    advisor_guidance: string;
  };
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  modelUsed?: string;
}

export interface ChatResponse {
  response: string;
  model_used: string;
}
