export interface User {
  id: string;
  email: string;
  fullName?: string;
  createdAt: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface ExperienceItem {
  title: string;
  company: string;
  start_date?: string;
  end_date?: string;
  description: string;
  technologies: string[];
}

export interface ProjectItem {
  name: string;
  description: string;
  technologies: string[];
  achievements: string[];
}

export interface EducationItem {
  institution: string;
  degree: string;
  field: string;
  start_year?: number;
  end_year?: number;
}

export interface CertificationItem {
  name: string;
  issuer: string;
  year?: number;
}

export interface SkillsBreakdown {
  technical: string[];
  frameworks: string[];
  tools: string[];
  soft: string[];
}

export interface CVProfile {
  id: string;
  user_id: string;
  full_name?: string;
  email?: string;
  phone?: string;
  location?: string;
  languages: string[];
  education: EducationItem[];
  experience: ExperienceItem[];
  projects: ProjectItem[];
  skills: SkillsBreakdown;
  certifications: CertificationItem[];
  skills_technical: string[];
  skills_frameworks: string[];
  raw_text: string;
  embedding_index_path?: string;
  parsed_at: string;
}

export interface CVUploadResponse {
  cv_profile_id: string;
  profile_summary: {
    full_name: string;
    skills_count: number;
    experience_count: number;
    projects_count: number;
    education_count: number;
    certifications_count?: number;
    languages_count?: number;
  };
  metrics?: ProfileMetric[];
}

export interface ProfileMetric {
  label: string;
  count: number;
  icon: string;
}

export interface SearchStartResponse {
  session_id: string;
}

export interface SearchFilters {
  location?: string;
  contract_type?: string;
  remote?: boolean;
  max_results: number;
}

export interface SearchStatusResponse {
  status: 'PENDING' | 'AGENT_2_RUNNING' | 'AGENT_3_RUNNING' | 'AGENT_4_RUNNING' | 'AGENT_5_RUNNING' | 'COMPLETED' | 'FAILED';
  progress_percent: number;
  current_step?: string;
  current_agent?: string;
  jobs_found?: number;
  jobs_analyzed?: number;
}

export interface JobWithFit {
  job_id: string;
  title: string;
  company: string;
  location: string;
  contract_type: string;
  url: string;
  source: string;
  fit_percentage: number;
  fit_category: 'STRONG_FIT' | 'PARTIAL_FIT' | 'STRETCH_GOAL' | 'DEVELOP_FIRST';
  top_matched_skills: string[];
  top_gaps: string[];
}

export interface SkillAssessment {
  skill_name: string;
  assessment: 'EXACT_MATCH' | 'TRANSFERABLE' | 'PARTIAL' | 'GAP';
  similarity_score: number;
  explanation: string;
  evidence: string;
}

export interface FitAnalysisResponse {
  id: string;
  job_posting_id: string;
  job_title: string;
  company: string;
  fit_percentage: number;
  fit_category: 'STRONG_FIT' | 'PARTIAL_FIT' | 'STRETCH_GOAL' | 'DEVELOP_FIRST';
  skill_breakdown: SkillAssessment[];
  strengths: string[];
  gaps: string[];
  transferable_skills: string[];
  overall_reasoning: string;
}

export interface UpskillItem {
  skill: string;
  reason: string;
  resource_type: 'course' | 'project' | 'tutorial';
}

export interface JobSearchStrategyResponse {
  id: string;
  session_id: string;
  quick_wins: JobWithFit[];
  stretch_goals: JobWithFit[];
  develop_first: JobWithFit[];
  executive_summary: string;
  week_1_actions: string[];
  week_2_actions: string[];
  month_1_goal: string;
  skills_to_upskill: UpskillItem[];
  top_recommendation: string;
  generated_at: string;
  total_jobs_found?: number;
  total_jobs_analyzed?: number;
}

export interface DiffEntry {
  section: string;
  change_type: 'REORDERED' | 'REPHRASED' | 'KEYWORD_ADDED' | 'STRENGTHENED';
  original_text: string;
  adapted_text: string;
  reason: string;
}

export interface TailoredCVResponse {
  id: string;
  job_posting_id: string;
  original_cv_id: string;
  adapted_sections: Record<string, string>;
  diff: DiffEntry[];
  ats_score_estimate: number;
  pending_approval: boolean;
  approved_at?: string;
}

export interface ApproveChangesResponse {
  download_url: string;
  approved_count: number;
}
