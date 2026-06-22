"""Jobs Router — List jobs, results with tailored previews, and fit analysis."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from types import SimpleNamespace

from app.database import get_db
from app.models.user import User
from app.models.job_posting import JobPosting
from app.models.fit_analysis import FitAnalysis
from app.models.job_search_session import JobSearchSession
from app.models.tailored_cv import TailoredCV
from app.models.job_application import JobApplication
from app.schemas.job import JobWithFit
from app.schemas.fit import FitAnalysisResponse, SkillAssessment
from app.schemas.strategy import (
    JobResultsResponse,
    JobWithTailoredPreview,
    TailoredCVPreview,
    KeyChangePreview,
)
from app.middleware.auth_middleware import get_current_user

router = APIRouter()


def _build_job_with_preview(job, fit, tailored_cv, application) -> JobWithTailoredPreview:
    strengths = fit.strengths if fit and fit.strengths else []
    gaps = fit.gaps if fit and fit.gaps else []

    preview = TailoredCVPreview()
    if tailored_cv:
        summary = tailored_cv.preview_summary or {}
        preview = TailoredCVPreview(
            tailored_cv_id=tailored_cv.id,
            preview_snippet=summary.get("preview_snippet", ""),
            emphasized_skills=summary.get("emphasized_skills", []),
            highlighted_projects=summary.get("highlighted_projects", []),
            key_changes=[KeyChangePreview(**kc) for kc in summary.get("key_changes", [])],
            ats_score_estimate=tailored_cv.ats_score_estimate or 0,
            pending_approval=tailored_cv.pending_approval,
            tailoring_status="ready",
        )

    return JobWithTailoredPreview(
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
        tailored_preview=preview,
        application_status=application.status if application else None,
        applied_at=application.applied_at if application else None,
    )


@router.get("/results/{session_id}", response_model=JobResultsResponse)
async def get_job_results(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all jobs with tailored CV previews for a completed search session."""
    session_result = await db.execute(
        select(JobSearchSession).where(
            JobSearchSession.id == uuid.UUID(session_id),
            JobSearchSession.user_id == current_user.id,
        )
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    jobs_result = await db.execute(
        select(JobPosting).where(JobPosting.session_id == uuid.UUID(session_id))
    )
    jobs = jobs_result.scalars().all()

    fits_result = await db.execute(
        select(FitAnalysis).where(FitAnalysis.session_id == uuid.UUID(session_id))
    )
    fits = {str(f.job_posting_id): f for f in fits_result.scalars().all()}

    job_ids = [job.id for job in jobs]
    tailored_map = {}
    if job_ids:
        tailored_result = await db.execute(
            select(TailoredCV).where(
                TailoredCV.user_id == current_user.id,
                TailoredCV.job_posting_id.in_(job_ids),
            )
        )
        tailored_map = {str(t.job_posting_id): t for t in tailored_result.scalars().all()}

    apps = {}
    if job_ids:
        apps_result = await db.execute(
            select(JobApplication).where(
                JobApplication.user_id == current_user.id,
                JobApplication.job_posting_id.in_(job_ids),
            )
        )
        apps = {str(a.job_posting_id): a for a in apps_result.scalars().all()}

    results: List[JobWithTailoredPreview] = []
    for job in jobs:
        fit = fits.get(str(job.id))
        # If no fit analysis was produced for this job, create a minimal placeholder
        # so we still return the job in results (fit percentage defaults to 0).
        if not fit:
            fit = SimpleNamespace(
                fit_percentage=0,
                fit_category="DEVELOP_FIRST",
                strengths=[],
                gaps=[],
            )
        tailored_cv = tailored_map.get(str(job.id))
        application = apps.get(str(job.id))
        results.append(_build_job_with_preview(job, fit, tailored_cv, application))

    results.sort(key=lambda x: x.fit_percentage, reverse=True)
    tailored_ready = sum(1 for r in results if r.tailored_preview.tailoring_status == "ready")

    return JobResultsResponse(
        session_id=uuid.UUID(session_id),
        jobs=results,
        total_jobs_found=len(jobs),
        total_tailored=tailored_ready,
    )


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
