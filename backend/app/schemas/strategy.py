"""Strategy schemas."""

from datetime import datetime
from uuid import UUID
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from app.schemas.job import JobWithFit


class UpskillItem(BaseModel):
    skill: str
    reason: str
    resource_type: str = "course"  # course | project | tutorial


class DiffEntry(BaseModel):
    section: str
    change_type: str  # REORDERED | REPHRASED | KEYWORD_ADDED | STRENGTHENED
    original_text: str
    adapted_text: str
    reason: str


class KeyChangePreview(BaseModel):
    section: str
    change_type: str
    original_text: str = ""
    adapted_text: str = ""
    reason: str = ""


class TailoredCVPreview(BaseModel):
    tailored_cv_id: Optional[UUID] = None
    preview_snippet: str = ""
    emphasized_skills: List[str] = []
    highlighted_projects: List[str] = []
    key_changes: List[KeyChangePreview] = []
    ats_score_estimate: int = 0
    pending_approval: bool = True
    tailoring_status: str = "pending"  # pending | ready | failed


class JobWithTailoredPreview(JobWithFit):
    tailored_preview: TailoredCVPreview = TailoredCVPreview()
    application_status: Optional[str] = None
    applied_at: Optional[datetime] = None


class JobResultsResponse(BaseModel):
    session_id: UUID
    jobs: List[JobWithTailoredPreview] = []
    total_jobs_found: int = 0
    total_tailored: int = 0


class JobSearchStrategyResponse(BaseModel):
    id: UUID
    session_id: UUID
    quick_wins: List[JobWithFit] = []
    stretch_goals: List[JobWithFit] = []
    develop_first: List[JobWithFit] = []
    executive_summary: str = ""
    week_1_actions: List[str] = []
    week_2_actions: List[str] = []
    month_1_goal: str = ""
    skills_to_upskill: List[UpskillItem] = []
    top_recommendation: str = ""
    generated_at: datetime
    total_jobs_found: Optional[int] = None
    total_jobs_analyzed: Optional[int] = None

    class Config:
        from_attributes = True


class TailoredCVResponse(BaseModel):
    id: UUID
    job_posting_id: UUID
    original_cv_id: UUID
    adapted_sections: dict
    original_sections: dict = {}
    diff: List[DiffEntry]
    ats_score_estimate: int = 0
    pending_approval: bool = True
    approved_at: Optional[datetime] = None
    preview_snippet: str = ""
    emphasized_skills: List[str] = []
    highlighted_projects: List[str] = []
    key_changes: List[KeyChangePreview] = []

    class Config:
        from_attributes = True


class ApplicationSubmitRequest(BaseModel):
    confirm_cv: bool = False


class ApplicationSubmitResponse(BaseModel):
    application_id: UUID
    job_posting_id: UUID
    tailored_cv_id: UUID
    job_title: str
    company: str
    applied_at: datetime
    status: str
    message: str


class ApproveChangesRequest(BaseModel):
    approved_changes: List[int]  # indices of approved diff entries


class ApproveChangesResponse(BaseModel):
    download_url: str
    approved_count: int
