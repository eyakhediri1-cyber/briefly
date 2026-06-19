"""Fit Analysis model."""

import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class FitAnalysis(Base):
    __tablename__ = "fit_analyses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_search_sessions.id", ondelete="CASCADE"), nullable=False)
    job_posting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False)
    fit_percentage: Mapped[int] = mapped_column(Integer, nullable=False)
    fit_category: Mapped[str] = mapped_column(String(50), nullable=False)
    skill_breakdown: Mapped[dict] = mapped_column(JSON, nullable=False)
    strengths: Mapped[dict] = mapped_column(JSON, nullable=True)
    gaps: Mapped[dict] = mapped_column(JSON, nullable=True)
    transferable_skills: Mapped[dict] = mapped_column(JSON, nullable=True)
    overall_reasoning: Mapped[str] = mapped_column(Text, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("JobSearchSession", back_populates="fit_analyses")
    job_posting = relationship("JobPosting", back_populates="fit_analyses")
