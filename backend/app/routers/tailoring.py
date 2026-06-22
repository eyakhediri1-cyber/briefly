"""Tailoring Router — Generate tailored CV, approve changes, preview, and download PDF."""

import io
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor

from app.database import get_db
from app.models.user import User
from app.models.cv_profile import CVProfile
from app.models.job_posting import JobPosting
from app.models.tailored_cv import TailoredCV
from app.schemas.strategy import TailoredCVResponse, ApproveChangesRequest, ApproveChangesResponse
from app.services.tailoring_service import tailor_and_store, tailored_cv_to_response
from app.middleware.auth_middleware import get_current_user

router = APIRouter()


@router.post("/{job_id}", response_model=TailoredCVResponse)
async def tailor_cv(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger Agent 6 to tailor the CV for a specific job posting."""
    cv_result = await db.execute(
        select(CVProfile)
        .where(CVProfile.user_id == current_user.id)
        .order_by(CVProfile.parsed_at.desc())
        .limit(1)
    )
    cv_profile = cv_result.scalar_one_or_none()
    if not cv_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No original CV found. Please upload a CV first.",
        )

    job_result = await db.execute(
        select(JobPosting).where(JobPosting.id == uuid.UUID(job_id))
    )
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job posting not found",
        )

    existing_result = await db.execute(
        select(TailoredCV).where(
            TailoredCV.user_id == current_user.id,
            TailoredCV.job_posting_id == uuid.UUID(job_id),
            TailoredCV.original_cv_id == cv_profile.id,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        return TailoredCVResponse(**tailored_cv_to_response(existing))

    job_data = {
        "title": job.title,
        "required_skills": job.structured_requirements.get("required_skills", []) if job.structured_requirements else [],
        "ats_keywords": job.structured_requirements.get("ats_keywords", []) if job.structured_requirements else [],
    }
    cv_data = {
        "structured_data": cv_profile.structured_data,
        "raw_text": cv_profile.raw_text,
    }

    try:
        tailored_cv = await tailor_and_store(
            db,
            user_id=current_user.id,
            cv_profile_id=cv_profile.id,
            job_posting_id=uuid.UUID(job_id),
            cv_data=cv_data,
            job_data=job_data,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CV Tailoring failed: {str(e)}",
        )

    if not tailored_cv:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CV Tailoring failed. Please try again.",
        )

    await db.flush()
    return TailoredCVResponse(**tailored_cv_to_response(tailored_cv))


@router.get("/{job_id}/preview", response_model=TailoredCVResponse)
async def get_cv_preview(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get tailored CV preview with emphasized skills and highlighted projects."""
    result = await db.execute(
        select(TailoredCV).where(
            TailoredCV.user_id == current_user.id,
            TailoredCV.job_posting_id == uuid.UUID(job_id),
        )
    )
    tailored_cv = result.scalar_one_or_none()
    if not tailored_cv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tailored CV not found. Run tailoring first.",
        )
    return TailoredCVResponse(**tailored_cv_to_response(tailored_cv))


@router.post("/{job_id}/approve", response_model=ApproveChangesResponse)
async def approve_changes(
    job_id: str,
    request: ApproveChangesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve CV changes to enable download and application."""
    result = await db.execute(
        select(TailoredCV).where(
            TailoredCV.user_id == current_user.id,
            TailoredCV.job_posting_id == uuid.UUID(job_id),
        )
    )
    tailored_cv = result.scalar_one_or_none()
    if not tailored_cv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tailored CV not found",
        )

    diff_count = len(tailored_cv.diff) if tailored_cv.diff else 0
    approved_count = len(request.approved_changes)

    if diff_count > 0 and approved_count < diff_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Please approve all changes before continuing. Approved {approved_count}/{diff_count}.",
        )

    tailored_cv.approved_changes = request.approved_changes
    tailored_cv.pending_approval = False
    tailored_cv.approved_at = datetime.utcnow()
    tailored_cv.download_url = f"/tailor/{job_id}/download"

    await db.commit()

    return ApproveChangesResponse(
        download_url=tailored_cv.download_url,
        approved_count=approved_count if diff_count else 0,
    )


@router.get("/{job_id}/download")
async def download_cv(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download the tailored CV as a PDF."""
    result = await db.execute(
        select(TailoredCV).where(
            TailoredCV.user_id == current_user.id,
            TailoredCV.job_posting_id == uuid.UUID(job_id),
        )
    )
    tailored_cv = result.scalar_one_or_none()
    if not tailored_cv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tailored CV not found")

    # Allow download if there are no diffs
    has_diffs = len(tailored_cv.diff) > 0 if tailored_cv.diff else False
    if has_diffs and tailored_cv.pending_approval:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please approve all changes before downloading the CV.",
        )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CVTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        textColor=HexColor('#4F46E5'),
        spaceAfter=15,
        alignment=1,
    )

    section_style = ParagraphStyle(
        'CVSection',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        textColor=HexColor('#1E293B'),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        'CVBody',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=HexColor('#334155'),
        spaceAfter=8,
    )

    story = []
    full_name = current_user.full_name or "Resume"
    story.append(Paragraph(full_name, title_style))
    story.append(Spacer(1, 10))

    for section_name, section_content in tailored_cv.adapted_sections.items():
        story.append(Paragraph(section_name, section_style))
        paragraphs = section_content.split("\n\n")
        for p in paragraphs:
            if p.strip().startswith("•") or p.strip().startswith("-"):
                items = p.split("\n")
                for item in items:
                    story.append(Paragraph(item.strip(), body_style))
            else:
                p_clean = p.replace("\n", "<br/>")
                story.append(Paragraph(p_clean, body_style))
        story.append(Spacer(1, 10))

    doc.build(story)
    buffer.seek(0)

    filename = f"Tailored_CV_{job_id[:8]}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
