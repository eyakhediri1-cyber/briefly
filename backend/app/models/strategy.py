"""Strategy model."""

import uuid
from datetime import datetime
from sqlalchemy import Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_search_sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
    quick_wins: Mapped[dict] = mapped_column(JSON, nullable=True)
    stretch_goals: Mapped[dict] = mapped_column(JSON, nullable=True)
    develop_first: Mapped[dict] = mapped_column(JSON, nullable=True)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=True)
    week_1_actions: Mapped[dict] = mapped_column(JSON, nullable=True)
    week_2_actions: Mapped[dict] = mapped_column(JSON, nullable=True)
    month_1_goal: Mapped[str] = mapped_column(Text, nullable=True)
    skills_to_upskill: Mapped[dict] = mapped_column(JSON, nullable=True)
    top_recommendation: Mapped[str] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("JobSearchSession", back_populates="strategy")
