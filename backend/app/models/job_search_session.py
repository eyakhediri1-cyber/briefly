"""Job Search Session model."""

import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class JobSearchSession(Base):
    __tablename__ = "job_search_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    cv_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cv_profiles.id"), nullable=True)
    target_role: Mapped[str] = mapped_column(String(255), nullable=False)
    filters: Mapped[dict] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    current_step: Mapped[str] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="sessions")
    cv_profile = relationship("CVProfile", back_populates="sessions")
    job_postings = relationship("JobPosting", back_populates="session", cascade="all, delete-orphan")
    fit_analyses = relationship("FitAnalysis", back_populates="session", cascade="all, delete-orphan")
    strategy = relationship("Strategy", back_populates="session", uselist=False, cascade="all, delete-orphan")
