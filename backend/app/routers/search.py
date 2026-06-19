"""Search Router — Start job search pipeline and check status."""

import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.cv_profile import CVProfile
from app.models.job_search_session import JobSearchSession
from app.schemas.job import SearchStartRequest, SearchStartResponse, SearchStatusResponse
from app.middleware.auth_middleware import get_current_user
from app.pipeline.orchestrator import run_pipeline, update_session_status
from app.services.redis_service import redis_service

router = APIRouter()


@router.post("/start", response_model=SearchStartResponse)
async def start_search(
    request: SearchStartRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start a new job search pipeline (runs in background)."""
    result = await db.execute(
        select(CVProfile)
        .where(CVProfile.user_id == current_user.id)
        .order_by(CVProfile.parsed_at.desc())
        .limit(1)
    )
    cv_profile = result.scalar_one_or_none()

    if not cv_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please upload your CV before starting a job search",
        )

    session = JobSearchSession(
        user_id=current_user.id,
        cv_profile_id=cv_profile.id,
        target_role=request.target_role,
        filters=request.filters.model_dump() if request.filters else {},
        status="PENDING",
        progress_percent=0,
        current_step="Initializing agent pipeline...",
    )
    db.add(session)
    await db.flush()

    session_id = str(session.id)

    cv_data = {
        "structured_data": cv_profile.structured_data,
        "raw_text": cv_profile.raw_text,
        "embedding_index_path": cv_profile.embedding_index_path,
    }

    # Prime status cache so polling shows activity immediately
    await update_session_status(
        session_id, "PENDING", 5, "Starting agent pipeline..."
    )

    background_tasks.add_task(
        run_pipeline,
        session_id,
        cv_data,
        request.target_role,
        request.filters.model_dump() if request.filters else {},
    )

    return SearchStartResponse(session_id=session.id)


@router.get("/status/{session_id}", response_model=SearchStatusResponse)
async def get_search_status(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Poll the status of a running search pipeline."""
    # Always verify session ownership first
    result = await db.execute(
        select(JobSearchSession).where(
            JobSearchSession.id == uuid.UUID(session_id),
            JobSearchSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Prefer Redis cache for live progress fields
    cached = await redis_service.get_json(f"session_status:{session_id}")
    if cached:
        return SearchStatusResponse(
            status=cached.get("status", session.status),
            progress_percent=cached.get("progress_percent", session.progress_percent),
            current_step=cached.get("current_step", session.current_step),
            current_agent=cached.get("current_agent"),
            jobs_found=cached.get("jobs_found"),
            jobs_analyzed=cached.get("jobs_analyzed"),
        )

    return SearchStatusResponse(
        status=session.status,
        progress_percent=session.progress_percent,
        current_step=session.current_step,
    )
