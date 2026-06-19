"""Tailored CV model."""

import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class TailoredCV(Base):
    __tablename__ = "tailored_cvs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_posting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False)
    original_cv_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cv_profiles.id"), nullable=False)
    adapted_sections: Mapped[dict] = mapped_column(JSON, nullable=False)
    diff: Mapped[dict] = mapped_column(JSON, nullable=False)
    ats_score_estimate: Mapped[int] = mapped_column(Integer, nullable=True)
    approved_changes: Mapped[dict] = mapped_column(JSON, nullable=True)
    pending_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    download_url: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    approved_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="tailored_cvs")
    job_posting = relationship("JobPosting", back_populates="tailored_cvs")
    original_cv = relationship("CVProfile", back_populates="tailored_cvs")
