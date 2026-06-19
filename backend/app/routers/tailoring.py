"""Tailoring Router — Generate tailored CV, approve changes, and download PDF."""

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
from app.agents.agent6_cv_tailor import cv_tailor
from app.middleware.auth_middleware import get_current_user

router = APIRouter()


@router.post("/{job_id}", response_model=TailoredCVResponse)
async def tailor_cv(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger Agent 6 to tailor the CV for a specific job posting."""
    # Get the latest original CV profile for the user
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

    # Get the job posting details
    job_result = await db.execute(
        select(JobPosting).where(JobPosting.id == uuid.UUID(job_id))
    )
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job posting not found",
        )

    # Check if a tailored CV already exists for this job and original CV
    existing_result = await db.execute(
        select(TailoredCV).where(
            TailoredCV.user_id == current_user.id,
            TailoredCV.job_posting_id == uuid.UUID(job_id),
            TailoredCV.original_cv_id == cv_profile.id,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        # Map DB model to response format
        return TailoredCVResponse(
            id=existing.id,
            job_posting_id=existing.job_posting_id,
            original_cv_id=existing.original_cv_id,
            adapted_sections=existing.adapted_sections,
            diff=existing.diff or [],
            ats_score_estimate=existing.ats_score_estimate or 0,
            pending_approval=existing.pending_approval,
            approved_at=existing.approved_at,
        )

    # Run Agent 6 to tailor
    cv_data = {
        "structured_data": cv_profile.structured_data,
        "raw_text": cv_profile.raw_text,
    }
    job_data = {
        "title": job.title,
        "required_skills": job.structured_requirements.get("required_skills", []) if job.structured_requirements else [],
        "ats_keywords": job.structured_requirements.get("ats_keywords", []) if job.structured_requirements else [],
    }

    try:
        tailored_data = await cv_tailor.run(cv_data, job_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CV Tailoring failed: {str(e)}",
        )

    # Create TailoredCV record
    tailored_cv = TailoredCV(
        id=uuid.UUID(tailored_data["id"]),
        user_id=current_user.id,
        job_posting_id=uuid.UUID(job_id),
        original_cv_id=cv_profile.id,
        adapted_sections=tailored_data["adapted_sections"],
        diff=tailored_data["diff"],
        ats_score_estimate=tailored_data["ats_score_estimate"],
        approved_changes=[],
        pending_approval=True,
    )
    db.add(tailored_cv)
    await db.flush()

    return TailoredCVResponse(
        id=tailored_cv.id,
        job_posting_id=tailored_cv.job_posting_id,
        original_cv_id=tailored_cv.original_cv_id,
        adapted_sections=tailored_cv.adapted_sections,
        diff=tailored_cv.diff,
        ats_score_estimate=tailored_cv.ats_score_estimate,
        pending_approval=tailored_cv.pending_approval,
        approved_at=tailored_cv.approved_at,
    )


@router.post("/{job_id}/approve", response_model=ApproveChangesResponse)
async def approve_changes(
    job_id: str,
    request: ApproveChangesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve CV changes to enable PDF generation."""
    # Find the tailored CV
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

    # Validate that all changes have been approved
    # Wait, the spec says "The 'Download CV' button must be disabled until the user explicitly approves each diff entry."
    # Let's verify that the length of approved_changes matches the length of the diff list.
    diff_count = len(tailored_cv.diff) if tailored_cv.diff else 0
    approved_count = len(request.approved_changes)

    # Even if there are no changes, or the user approved them all
    if approved_count < diff_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Please approve all changes before downloading. Approved {approved_count}/{diff_count}.",
        )

    # Update approval status
    tailored_cv.approved_changes = request.approved_changes
    tailored_cv.pending_approval = False
    tailored_cv.approved_at = datetime.utcnow()
    tailored_cv.download_url = f"/tailor/{job_id}/download"

    await db.flush()

    return ApproveChangesResponse(
        download_url=tailored_cv.download_url,
        approved_count=approved_count,
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

    if tailored_cv.pending_approval:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please approve all changes before downloading the CV.",
        )

    # Generate PDF in memory using ReportLab
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

    # Define custom styles with the brand color #4F46E5
    title_style = ParagraphStyle(
        'CVTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        textColor=HexColor('#4F46E5'),
        spaceAfter=15,
        alignment=1, # Center
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

    # Title / Full Name
    # We try to get the full name from structured CV data or user details
    full_name = current_user.full_name or "Resume"
    story.append(Paragraph(full_name, title_style))
    story.append(Spacer(1, 10))

    # Add each section
    for section_name, section_content in tailored_cv.adapted_sections.items():
        story.append(Paragraph(section_name, section_style))
        # Split by double newline to preserve paragraphs or list items
        paragraphs = section_content.split("\n\n")
        for p in paragraphs:
            # Handle list items
            if p.strip().startswith("•") or p.strip().startswith("-"):
                # Simple list handling
                items = p.split("\n")
                for item in items:
                    story.append(Paragraph(item.strip(), body_style))
            else:
                # Regular paragraph, replace newlines with linebreaks
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
