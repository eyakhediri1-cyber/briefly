"""CV schemas for profile parsing and management."""

from datetime import datetime
from uuid import UUID
from typing import List, Optional, Dict
from pydantic import BaseModel


class ExperienceItem(BaseModel):
    title: str = ""
    company: str = ""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: str = ""
    technologies: List[str] = []


class ProjectItem(BaseModel):
    name: str = ""
    description: str = ""
    technologies: List[str] = []
    achievements: List[str] = []


class EducationItem(BaseModel):
    institution: str = ""
    degree: str = ""
    field: str = ""
    start_year: Optional[int] = None
    end_year: Optional[int] = None


class CertificationItem(BaseModel):
    name: str = ""
    issuer: str = ""
    year: Optional[int] = None


class SkillsBreakdown(BaseModel):
    technical: List[str] = []
    frameworks: List[str] = []
    tools: List[str] = []
    soft: List[str] = []


class CVProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    languages: List[str] = []
    education: List[EducationItem] = []
    experience: List[ExperienceItem] = []
    projects: List[ProjectItem] = []
    skills: SkillsBreakdown = SkillsBreakdown()
    certifications: List[CertificationItem] = []
    skills_technical: List[str] = []
    skills_frameworks: List[str] = []
    raw_text: str = ""
    embedding_index_path: Optional[str] = None
    parsed_at: datetime

    class Config:
        from_attributes = True


class CVUploadResponse(BaseModel):
    cv_profile_id: UUID
    profile_summary: dict
    metrics: List[dict] = []


class CVParsedProfile(BaseModel):
    """Raw parsed profile from Gemini."""
    full_name: str = ""
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    languages: List[str] = []
    education: List[EducationItem] = []
    experience: List[ExperienceItem] = []
    projects: List[ProjectItem] = []
    skills: SkillsBreakdown = SkillsBreakdown()
    certifications: List[CertificationItem] = []
