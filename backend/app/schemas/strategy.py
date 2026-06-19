"""Strategy schemas."""

from datetime import datetime
from uuid import UUID
from typing import List, Optional
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
    diff: List[DiffEntry]
    ats_score_estimate: int = 0
    pending_approval: bool = True
    approved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApproveChangesRequest(BaseModel):
    approved_changes: List[int]  # indices of approved diff entries


class ApproveChangesResponse(BaseModel):
    download_url: str
    approved_count: int
