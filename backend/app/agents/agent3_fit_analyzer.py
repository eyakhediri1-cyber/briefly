"""
Agent 3 (lightweight) — Fit analysis helper used by pipeline or ad-hoc tasks.
Returns a simple fit score (0-100) based on skill overlap and job metadata.
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


async def agent3_analyze_fit(cv_data: Dict, job: Dict) -> Dict:
    """Analyze CV vs Job - return fit score 0-100."""

    cv_skills = set([s.lower() for s in cv_data.get("skills", [])])
    job_description = (job.get("description", "") or "").lower()

    # Extract skills from job description
    common_skills = [
        "python",
        "javascript",
        "typescript",
        "react",
        "vue",
        "angular",
        "node",
        "fastapi",
        "django",
        "sql",
        "aws",
        "docker",
        "kubernetes",
    ]

    job_skills = set([s for s in common_skills if s in job_description])

    # Calculate fit score
    skill_matches = len(cv_skills & job_skills)
    total_job_skills = len(job_skills) if job_skills else 1
    skill_score = (skill_matches / total_job_skills) * 50

    # Location score
    location_score = 30 if (job.get("job_type") == "remote" or job.get("remote")) else 20

    # Job type score (simple heuristic)
    job_type_score = 20

    total_score = min(100, int(skill_score + location_score + job_type_score))

    logger.info("Agent3 fit: matches=%d job_skills=%d score=%d", skill_matches, len(job_skills), total_score)

    return {
        "fit_score": total_score,
        "skill_matches": skill_matches,
        "matched_skills": list(cv_skills & job_skills),
    }
