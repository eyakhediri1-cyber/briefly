"""Shared CV tailoring persistence logic for pipeline and API."""

import logging
import uuid
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.agent6_cv_tailor import cv_tailor
from app.models.tailored_cv import TailoredCV
from app.utils.cv_preview import build_cv_preview

logger = logging.getLogger(__name__)


async def tailor_and_store(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    cv_profile_id: uuid.UUID,
    job_posting_id: uuid.UUID,
    cv_data: dict,
    job_data: dict,
) -> Optional[TailoredCV]:
    """Run Agent 6 and persist TailoredCV with original + preview. Returns None on failure."""
    existing_result = await db.execute(
        select(TailoredCV).where(
            TailoredCV.user_id == user_id,
            TailoredCV.job_posting_id == job_posting_id,
            TailoredCV.original_cv_id == cv_profile_id,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        return existing

    try:
        tailored_data = await cv_tailor.run(cv_data, job_data)
    except Exception as e:
        logger.error("CV tailoring failed for job %s: %s", job_posting_id, e)
        return None

    original_sections = tailored_data.get("original_sections", {})
    adapted_sections = tailored_data.get("adapted_sections", {})
    diff = tailored_data.get("diff", [])
    preview = build_cv_preview(adapted_sections, original_sections, diff)

    tailored_cv = TailoredCV(
        id=uuid.UUID(tailored_data["id"]),
        user_id=user_id,
        job_posting_id=job_posting_id,
        original_cv_id=cv_profile_id,
        adapted_sections=adapted_sections,
        original_sections=original_sections,
        preview_summary=preview,
        diff=diff,
        ats_score_estimate=tailored_data.get("ats_score_estimate", 0),
        approved_changes=[],
        pending_approval=True,
    )
    db.add(tailored_cv)
    await db.commit()
    await db.refresh(tailored_cv)
    return tailored_cv


def tailored_cv_to_response(tailored_cv: TailoredCV) -> Dict[str, Any]:
    """Map TailoredCV ORM object to API response dict."""
    preview = tailored_cv.preview_summary or build_cv_preview(
        tailored_cv.adapted_sections or {},
        tailored_cv.original_sections or {},
        tailored_cv.diff or [],
    )
    return {
        "id": tailored_cv.id,
        "job_posting_id": tailored_cv.job_posting_id,
        "original_cv_id": tailored_cv.original_cv_id,
        "adapted_sections": tailored_cv.adapted_sections,
        "original_sections": tailored_cv.original_sections or {},
        "diff": tailored_cv.diff or [],
        "ats_score_estimate": tailored_cv.ats_score_estimate or 0,
        "pending_approval": tailored_cv.pending_approval,
        "approved_at": tailored_cv.approved_at,
        "preview_snippet": preview.get("preview_snippet", ""),
        "emphasized_skills": preview.get("emphasized_skills", []),
        "highlighted_projects": preview.get("highlighted_projects", []),
        "key_changes": preview.get("key_changes", []),
    }
