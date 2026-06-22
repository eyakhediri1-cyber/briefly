"""Fast keyword-based fit scoring — no LLM or embedding calls."""

import re
import uuid
from typing import Dict, List

from app.schemas.job import RawJobPosting


def _cv_skills(cv_profile: dict) -> List[str]:
    structured = cv_profile.get("structured_data", cv_profile)
    skills = structured.get("skills", {})
    all_skills: List[str] = []
    if isinstance(skills, dict):
        for cat in ("technical", "frameworks", "tools", "soft"):
            all_skills.extend(skills.get(cat, []))
    elif isinstance(skills, list):
        all_skills = skills
    for exp in structured.get("experience", []):
        all_skills.extend(exp.get("technologies", []))
    for proj in structured.get("projects", []):
        all_skills.extend(proj.get("technologies", []))
    return list({s.lower().strip() for s in all_skills if s})


def _extract_job_keywords(job: RawJobPosting) -> List[str]:
    text = f"{job.title} {job.description}".lower()
    tokens = set(re.findall(r"[a-zA-Z+#\.]{2,}", text))
    for word in ("python", "javascript", "typescript", "react", "java", "node", "sql",
                 "docker", "kubernetes", "aws", "git", "linux", "api", "frontend",
                 "backend", "fullstack", "developer", "engineer"):
        if word in text:
            tokens.add(word)
    return list(tokens)


def extract_requirements_fast(job: RawJobPosting) -> dict:
    """Lightweight requirement extraction from job text — no LLM."""
    keywords = _extract_job_keywords(job)
    title_lower = job.title.lower()
    seniority = "internship" if any(w in title_lower for w in ("intern", "junior", "graduate", "entry")) else "mid"
    return {
        "required_skills": keywords[:12],
        "nice_to_have_skills": keywords[12:20],
        "seniority_level": seniority,
        "ats_keywords": keywords[:15],
        "role_summary": job.title,
    }


def compute_fit_fast(cv_profile: dict, job: RawJobPosting, requirements: dict) -> dict:
    """Keyword overlap fit score — instant, no external APIs."""
    cv_skill_set = set(_cv_skills(cv_profile))
    req_skills = requirements.get("required_skills", []) or _extract_job_keywords(job)

    strengths: List[str] = []
    gaps: List[str] = []
    transferable: List[str] = []
    breakdown = []

    for skill in req_skills[:10]:
        skill_lower = skill.lower()
        exact = skill_lower in cv_skill_set
        partial = any(skill_lower in s or s in skill_lower for s in cv_skill_set)

        if exact:
            assessment = "EXACT_MATCH"
            strengths.append(skill)
        elif partial:
            assessment = "TRANSFERABLE"
            transferable.append(skill)
        else:
            assessment = "GAP"
            gaps.append(skill)

        breakdown.append({
            "skill_name": skill,
            "assessment": assessment,
            "similarity_score": 1.0 if exact else (0.75 if partial else 0.0),
            "explanation": f"{'Direct match' if exact else 'Related skill' if partial else 'Not found'} in CV",
            "evidence": skill if exact else "",
        })

    if not req_skills:
        fit_pct = 70
    elif not cv_skill_set:
        # No CV skills - give base 40% fit so it's not DEVELOP_FIRST
        fit_pct = 40
    else:
        weights = {"EXACT_MATCH": 1.0, "TRANSFERABLE": 0.7, "PARTIAL": 0.4, "GAP": 0.0}
        total = sum(weights.get(b["assessment"], 0) for b in breakdown)
        fit_pct = round((total / len(breakdown)) * 100) if breakdown else 50

    if fit_pct >= 80:
        category = "STRONG_FIT"
    elif fit_pct >= 60:
        category = "PARTIAL_FIT"
    elif fit_pct >= 40:
        category = "STRETCH_GOAL"
    else:
        category = "DEVELOP_FIRST"

    return {
        "id": str(uuid.uuid4()),
        "job_posting_id": str(job.id),
        "job_title": job.title,
        "company": job.company,
        "fit_percentage": fit_pct,
        "fit_category": category,
        "skill_breakdown": breakdown,
        "strengths": strengths[:5],
        "gaps": gaps[:3],
        "transferable_skills": transferable[:3],
        "overall_reasoning": (
            f"{fit_pct}% match for {job.title} at {job.company}. "
            f"Matched: {', '.join(strengths[:3]) or 'general profile'}. "
            f"Gaps: {', '.join(gaps[:2]) or 'none identified'}."
        ),
    }
