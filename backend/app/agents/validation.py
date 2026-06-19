"""CRITICAL: Ensure no hallucination in CV tailoring."""

from typing import List, Tuple


def _collect_skill_names(structured: dict) -> set:
    """Extract normalized skill names from structured CV data."""
    names = set()
    skills = structured.get("skills", {})
    if isinstance(skills, dict):
        for category in ("technical", "frameworks", "tools", "soft"):
            for skill in skills.get(category, []):
                names.add(str(skill).lower())
    elif isinstance(skills, list):
        for skill in skills:
            if isinstance(skill, dict):
                names.add(str(skill.get("name", "")).lower())
            else:
                names.add(str(skill).lower())

    for exp in structured.get("experience", []):
        for tech in exp.get("technologies", []):
            names.add(str(tech).lower())

    for proj in structured.get("projects", []):
        for tech in proj.get("technologies", []):
            names.add(str(tech).lower())

    return {name for name in names if name}


def validate_no_invention(original_cv: dict, tailored_cv: dict) -> Tuple[bool, List[str]]:
    """
    Validate that tailored CV is a subset/rewording of the original.

    Returns: (is_valid, violations)
    """
    violations = []

    original_skills = _collect_skill_names(original_cv)
    tailored_skills = _collect_skill_names(tailored_cv)
    new_skills = tailored_skills - original_skills
    if new_skills:
        violations.append(f"NEW SKILLS ADDED: {new_skills}. NOT ALLOWED.")

    original_titles = {
        e.get("title", "").lower()
        for e in original_cv.get("experience", [])
        if e.get("title")
    }
    tailored_titles = {
        e.get("title", "").lower()
        for e in tailored_cv.get("experience", [])
        if e.get("title")
    }
    new_experiences = tailored_titles - original_titles
    if new_experiences:
        violations.append(f"NEW EXPERIENCES ADDED: {new_experiences}. NOT ALLOWED.")

    original_projects = {
        p.get("name", "").lower()
        for p in original_cv.get("projects", [])
        if p.get("name")
    }
    tailored_projects = {
        p.get("name", "").lower()
        for p in tailored_cv.get("projects", [])
        if p.get("name")
    }
    new_projects = tailored_projects - original_projects
    if new_projects:
        violations.append(f"NEW PROJECTS ADDED: {new_projects}. NOT ALLOWED.")

    return len(violations) == 0, violations
