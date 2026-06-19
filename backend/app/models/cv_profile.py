"""CV Profile model."""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class CVProfile(Base):
    __tablename__ = "cv_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    structured_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    embedding_index_path: Mapped[str] = mapped_column(String(500), nullable=True)
    parsed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="cv_profiles")
    sessions = relationship("JobSearchSession", back_populates="cv_profile")
    tailored_cvs = relationship("TailoredCV", back_populates="original_cv")
