"""Job schemas for search and analysis."""

from datetime import datetime
from uuid import UUID
from typing import List, Optional, Dict
from pydantic import BaseModel


class SearchFilters(BaseModel):
    location: Optional[str] = None
    contract_type: Optional[str] = None  # "internship", "fulltime", "parttime"
    remote: Optional[bool] = None
    max_results: int = 80


class SearchStartRequest(BaseModel):
    target_role: str
    filters: SearchFilters = SearchFilters()


class SearchStartResponse(BaseModel):
    session_id: UUID


class SearchStatusResponse(BaseModel):
    status: str
    progress_percent: int
    current_step: Optional[str] = None
    current_agent: Optional[str] = None
    jobs_found: Optional[int] = None
    jobs_analyzed: Optional[int] = None


class RawJobPosting(BaseModel):
    id: UUID
    title: str
    company: str
    location: str = ""
    contract_type: str = ""
    description: str
    url: str = ""
    posted_at: Optional[datetime] = None
    source: str = "unknown"


class AnalyzedJobPosting(BaseModel):
    id: UUID
    raw_posting_id: UUID
    title: str
    company: str
    location: str = ""
    contract_type: str = ""
    description: str = ""
    url: str = ""
    source: str = "unknown"
    required_skills: List[str] = []
    nice_to_have_skills: List[str] = []
    seniority_level: str = "internship"
    soft_skills: List[str] = []
    ats_keywords: List[str] = []
    role_summary: str = ""
    main_responsibilities: List[str] = []
    skill_embeddings: Dict[str, List[float]] = {}
    summary_embedding: List[float] = []


class JobWithFit(BaseModel):
    job_id: UUID
    title: str
    company: str
    location: str = ""
    contract_type: str = ""
    url: str = ""
    source: str = ""
    fit_percentage: int
    fit_category: str
    top_matched_skills: List[str] = []
    top_gaps: List[str] = []

    class Config:
        from_attributes = True
