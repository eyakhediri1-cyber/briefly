"""
Simple CV tailoring helper (lightweight). This produces a tailored CV preview
and returns an id. It is intentionally conservative and does not modify the
database — the longer-lived `tailor_and_store` service remains the canonical
persistence path used by the pipeline.
"""

import uuid
import logging
from typing import Dict, List

from app.agents.agent3_fit_analyzer import agent3_analyze_fit

logger = logging.getLogger(__name__)


def _extract_job_keywords(job_description: str, limit: int = 10) -> List[str]:
    words = [w.strip(".,()\n") for w in job_description.split() if len(w) > 5]
    seen = []
    for w in words:
        lw = w.lower()
        if lw not in seen:
            seen.append(lw)
        if len(seen) >= limit:
            break
    return seen


async def agent4_tailor_cv(cv_data: Dict, job: Dict) -> Dict:
    """Generate a lightweight tailored CV for a specific job.

    This function returns a dict with an `id` and a simple preview. It does
    not persist to the DB; use `tailor_and_store` service for persistence.
    """
    job_description = (job.get("description") or "")
    job_keywords = _extract_job_keywords(job_description)

    tailored = {
        "full_name": cv_data.get("full_name"),
        "email": cv_data.get("email"),
        "phone": cv_data.get("phone"),
        # Reorder skills naively by whether any keyword appears
        "skills": sorted(
            cv_data.get("skills", []),
            key=lambda s: 0 if any(k in s.lower() for k in job_keywords) else 1,
        ),
        "projects": cv_data.get("projects", []),
        "experience": cv_data.get("experience", []),
        "summary": f"{cv_data.get('summary','')} | Key skills: {', '.join(job_keywords)}",
    }

    tailored_cv_id = str(uuid.uuid4())

    # Compute fit score using Agent3 helper for convenience
    try:
        fit = await agent3_analyze_fit(cv_data, job)
        fit_score = fit.get("fit_score", 0)
    except Exception as e:
        logger.warning("agent4_tailor_cv: fit analysis failed: %s", e)
        fit_score = 0

    logger.info("Generated lightweight tailored CV %s for job %s (fit=%s)", tailored_cv_id, job.get("id"), fit_score)

    return {"id": tailored_cv_id, "preview": tailored, "fit_score": fit_score}
