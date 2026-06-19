"""Jobs Router — List jobs and get detailed fit analysis."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.database import get_db
from app.models.user import User
from app.models.job_posting import JobPosting
from app.models.fit_analysis import FitAnalysis
from app.models.job_search_session import JobSearchSession
from app.schemas.job import JobWithFit
from app.schemas.fit import FitAnalysisResponse, SkillAssessment
from app.middleware.auth_middleware import get_current_user

router = APIRouter()


@router.get("/{session_id}", response_model=List[JobWithFit])
async def get_jobs(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all jobs with fit scores for a session."""
    # Verify session ownership
    session_result = await db.execute(
        select(JobSearchSession).where(
            JobSearchSession.id == uuid.UUID(session_id),
            JobSearchSession.user_id == current_user.id,
        )
    )
    if not session_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Get jobs with fit analyses
    jobs_result = await db.execute(
        select(JobPosting).where(JobPosting.session_id == uuid.UUID(session_id))
    )
    jobs = jobs_result.scalars().all()

    fits_result = await db.execute(
        select(FitAnalysis).where(FitAnalysis.session_id == uuid.UUID(session_id))
    )
    fits = {str(f.job_posting_id): f for f in fits_result.scalars().all()}

    result = []
    for job in jobs:
        fit = fits.get(str(job.id))
        strengths = fit.strengths if fit and fit.strengths else []
        gaps = fit.gaps if fit and fit.gaps else []

        result.append(JobWithFit(
            job_id=job.id,
            title=job.title,
            company=job.company,
            location=job.location or "",
            contract_type=job.contract_type or "",
            url=job.url or "",
            source=job.source or "",
            fit_percentage=fit.fit_percentage if fit else 0,
            fit_category=fit.fit_category if fit else "DEVELOP_FIRST",
            top_matched_skills=strengths[:3] if isinstance(strengths, list) else [],
            top_gaps=gaps[:2] if isinstance(gaps, list) else [],
        ))

    # Sort by fit percentage DESC
    result.sort(key=lambda x: x.fit_percentage, reverse=True)
    return result


@router.get("/{job_id}/fit", response_model=FitAnalysisResponse)
async def get_fit_analysis(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed fit analysis for a specific job."""
    # Get the fit analysis
    result = await db.execute(
        select(FitAnalysis).where(FitAnalysis.job_posting_id == uuid.UUID(job_id))
    )
    fit = result.scalar_one_or_none()

    if not fit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fit analysis not found")

    # Get job details
    job_result = await db.execute(
        select(JobPosting).where(JobPosting.id == uuid.UUID(job_id))
    )
    job = job_result.scalar_one_or_none()

    # Parse skill breakdown
    breakdown = []
    for item in (fit.skill_breakdown or []):
        breakdown.append(SkillAssessment(
            skill_name=item.get("skill_name", ""),
            assessment=item.get("assessment", "GAP"),
            similarity_score=item.get("similarity_score", 0.0),
            explanation=item.get("explanation", ""),
            evidence=item.get("evidence", ""),
        ))

    return FitAnalysisResponse(
        id=fit.id,
        job_posting_id=fit.job_posting_id,
        job_title=job.title if job else "",
        company=job.company if job else "",
        fit_percentage=fit.fit_percentage,
        fit_category=fit.fit_category,
        skill_breakdown=breakdown,
        strengths=fit.strengths or [],
        gaps=fit.gaps or [],
        transferable_skills=fit.transferable_skills or [],
        overall_reasoning=fit.overall_reasoning or "",
    )
