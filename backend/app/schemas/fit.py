"""Fit analysis schemas."""

from uuid import UUID
from typing import List, Optional
from pydantic import BaseModel


class SkillAssessment(BaseModel):
    skill_name: str
    assessment: str  # EXACT_MATCH | TRANSFERABLE | PARTIAL | GAP
    similarity_score: float
    explanation: str
    evidence: str


class FitAnalysisResponse(BaseModel):
    id: UUID
    job_posting_id: UUID
    job_title: str = ""
    company: str = ""
    fit_percentage: int
    fit_category: str  # STRONG_FIT | PARTIAL_FIT | STRETCH_GOAL | DEVELOP_FIRST
    skill_breakdown: List[SkillAssessment]
    strengths: List[str] = []
    gaps: List[str] = []
    transferable_skills: List[str] = []
    overall_reasoning: str = ""

    class Config:
        from_attributes = True


class FitAnalysisCreate(BaseModel):
    job_posting_id: UUID
    fit_percentage: int
    fit_category: str
    skill_breakdown: List[dict]
    strengths: List[str] = []
    gaps: List[str] = []
    transferable_skills: List[str] = []
    overall_reasoning: str = ""
