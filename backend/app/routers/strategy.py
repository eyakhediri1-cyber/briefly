"""Strategy Router — Retrieve job search strategy."""

import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.strategy import Strategy
from app.models.job_search_session import JobSearchSession
from app.schemas.strategy import JobSearchStrategyResponse
from app.middleware.auth_middleware import get_current_user
from app.services.redis_service import redis_service

router = APIRouter()


@router.get("/{session_id}", response_model=JobSearchStrategyResponse)
async def get_strategy(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the strategy for a completed search session."""
    # Try Redis cache first
    cached = await redis_service.get_json(f"strategy:{session_id}")
    if cached:
        return JobSearchStrategyResponse(
            id=cached.get("id", str(uuid.uuid4())),
            session_id=session_id,
            quick_wins=cached.get("quick_wins", []),
            stretch_goals=cached.get("stretch_goals", []),
            develop_first=cached.get("develop_first", []),
            executive_summary=cached.get("executive_summary", ""),
            week_1_actions=cached.get("week_1_actions", []),
            week_2_actions=cached.get("week_2_actions", []),
            month_1_goal=cached.get("month_1_goal", ""),
            skills_to_upskill=cached.get("skills_to_upskill", []),
            top_recommendation=cached.get("top_recommendation", ""),
            generated_at=cached.get("generated_at", datetime.utcnow().isoformat()),
            total_jobs_found=cached.get("total_jobs_found"),
            total_jobs_analyzed=cached.get("total_jobs_analyzed"),
        )

    # Verify session belongs to user
    session_result = await db.execute(
        select(JobSearchSession).where(
            JobSearchSession.id == uuid.UUID(session_id),
            JobSearchSession.user_id == current_user.id,
        )
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Get strategy from DB
    result = await db.execute(
        select(Strategy).where(Strategy.session_id == uuid.UUID(session_id))
    )
    strategy = result.scalar_one_or_none()

    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy not yet generated. The pipeline may still be running.",
        )

    return JobSearchStrategyResponse(
        id=strategy.id,
        session_id=strategy.session_id,
        quick_wins=strategy.quick_wins or [],
        stretch_goals=strategy.stretch_goals or [],
        develop_first=strategy.develop_first or [],
        executive_summary=strategy.executive_summary or "",
        week_1_actions=strategy.week_1_actions or [],
        week_2_actions=strategy.week_2_actions or [],
        month_1_goal=strategy.month_1_goal or "",
        skills_to_upskill=strategy.skills_to_upskill or [],
        top_recommendation=strategy.top_recommendation or "",
        generated_at=strategy.generated_at,
    )
