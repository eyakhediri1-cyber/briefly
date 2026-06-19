"""CV Router — Upload CV and retrieve parsed profile."""

import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.cv_profile import CVProfile
from app.schemas.cv import CVUploadResponse, CVProfileResponse
from app.agents.agent1_profile_parser import profile_parser
from app.middleware.auth_middleware import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/upload", response_model=CVUploadResponse)
async def upload_cv(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a CV file (PDF) and parse it using Agent 1."""
    # Validate file type
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted",
        )

    # Read and validate file size
    content = await file.read()
    max_bytes = settings.CV_MAX_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds {settings.CV_MAX_SIZE_MB}MB limit",
        )

    # Run Agent 1: Profile Parser
    profile_data = await profile_parser.run(content, file.filename, str(current_user.id))

    # Store in database
    cv_profile = CVProfile(
        user_id=current_user.id,
        raw_text=profile_data.get("raw_text", ""),
        structured_data=profile_data.get("structured_data", {}),
        embedding_index_path=profile_data.get("embedding_index_path", ""),
    )
    db.add(cv_profile)
    await db.flush()

    # Build profile summary with labeled metrics (only non-zero counts)
    structured = profile_data.get("structured_data", {})
    skills = structured.get("skills", {})
    if isinstance(skills, dict):
        skills_count = len(
            skills.get("technical", [])
            + skills.get("frameworks", [])
            + skills.get("tools", [])
        )
        certifications_count = len(structured.get("certifications", []))
        languages_count = len(structured.get("languages", []))
    else:
        skills_count = len(skills) if isinstance(skills, list) else 0
        certifications_count = len(structured.get("certifications", []))
        languages_count = len(structured.get("languages", []))

    experience_count = len(structured.get("experience", []))
    projects_count = len(structured.get("projects", []))
    education_count = len(structured.get("education", []))

    summary = {
        "full_name": structured.get("full_name", ""),
        "skills_count": skills_count,
        "experience_count": experience_count,
        "projects_count": projects_count,
        "education_count": education_count,
        "certifications_count": certifications_count,
        "languages_count": languages_count,
    }

    metrics = []
    for label, count, icon in [
        ("Skills", skills_count, "bi-tools"),
        ("Experience", experience_count, "bi-briefcase"),
        ("Projects", projects_count, "bi-folder"),
        ("Education", education_count, "bi-mortarboard"),
        ("Certifications", certifications_count, "bi-award"),
        ("Languages", languages_count, "bi-translate"),
    ]:
        if count > 0:
            metrics.append({"label": label, "count": count, "icon": icon})

    logger.info("CV upload response: %s", summary)
    return CVUploadResponse(
        cv_profile_id=cv_profile.id,
        profile_summary=summary,
        metrics=metrics,
    )


@router.get("/profile", response_model=CVProfileResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's parsed CV profile."""
    result = await db.execute(
        select(CVProfile)
        .where(CVProfile.user_id == current_user.id)
        .order_by(CVProfile.parsed_at.desc())
        .limit(1)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No CV profile found. Please upload your CV first.",
        )

    structured = profile.structured_data or {}
    skills = structured.get("skills", {})

    return CVProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        full_name=structured.get("full_name"),
        email=structured.get("email"),
        phone=structured.get("phone"),
        location=structured.get("location"),
        languages=structured.get("languages", []),
        education=structured.get("education", []),
        experience=structured.get("experience", []),
        projects=structured.get("projects", []),
        skills=skills,
        skills_technical=skills.get("technical", []) if isinstance(skills, dict) else [],
        skills_frameworks=skills.get("frameworks", []) if isinstance(skills, dict) else [],
        raw_text=profile.raw_text,
        embedding_index_path=profile.embedding_index_path,
        parsed_at=profile.parsed_at,
    )
