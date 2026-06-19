"""Job Posting model."""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class JobPosting(Base):
    __tablename__ = "job_postings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_search_sessions.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=True)
    contract_type: Mapped[str] = mapped_column(String(50), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=True)
    structured_requirements: Mapped[dict] = mapped_column(JSON, nullable=True)
    posted_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # Relationships
    session = relationship("JobSearchSession", back_populates="job_postings")
    fit_analyses = relationship("FitAnalysis", back_populates="job_posting", cascade="all, delete-orphan")
    tailored_cvs = relationship("TailoredCV", back_populates="job_posting", cascade="all, delete-orphan")
