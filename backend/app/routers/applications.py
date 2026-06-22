"""Applications Router — Submit job applications with tailored CVs."""

import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.job_posting import JobPosting
from app.models.job_application import JobApplication
from app.models.tailored_cv import TailoredCV
from app.schemas.strategy import ApplicationSubmitRequest, ApplicationSubmitResponse
from app.middleware.auth_middleware import get_current_user

router = APIRouter()


@router.post("/{job_id}", response_model=ApplicationSubmitResponse)
async def submit_application(
    job_id: str,
    request: ApplicationSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit an application using the approved tailored CV for this job.
    User must confirm they are happy with the CV before applying.
    """
    if not request.confirm_cv:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please confirm you are happy with the tailored CV before applying.",
        )

    job_result = await db.execute(
        select(JobPosting).where(JobPosting.id == uuid.UUID(job_id))
    )
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job posting not found")

    cv_result = await db.execute(
        select(TailoredCV).where(
            TailoredCV.user_id == current_user.id,
            TailoredCV.job_posting_id == uuid.UUID(job_id),
        )
    )
    tailored_cv = cv_result.scalar_one_or_none()
    if not tailored_cv:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No tailored CV found for this job. Complete CV tailoring first.",
        )

    if tailored_cv.pending_approval:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please review and approve your tailored CV before applying.",
        )

    existing = await db.execute(
        select(JobApplication).where(
            JobApplication.user_id == current_user.id,
            JobApplication.job_posting_id == uuid.UUID(job_id),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already applied to this job.",
        )

    application = JobApplication(
        user_id=current_user.id,
        job_posting_id=uuid.UUID(job_id),
        tailored_cv_id=tailored_cv.id,
        status="submitted",
        tailored_cv_snapshot=tailored_cv.adapted_sections,
        applied_at=datetime.utcnow(),
    )
    db.add(application)
    await db.flush()

    return ApplicationSubmitResponse(
        application_id=application.id,
        job_posting_id=application.job_posting_id,
        tailored_cv_id=application.tailored_cv_id,
        job_title=job.title,
        company=job.company,
        applied_at=application.applied_at,
        status=application.status,
        message=(
            f"Application submitted for {job.title} at {job.company} "
            f"using your tailored CV (ATS score: {tailored_cv.ats_score_estimate}%)."
        ),
    )
