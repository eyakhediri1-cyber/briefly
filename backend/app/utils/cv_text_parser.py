"""Fast regex/line-based CV extraction — no LLM, used when Gemini times out."""

import re
from typing import Dict, List


def extract_basic_profile(raw_text: str) -> dict:
    """Extract essential profile fields from raw CV text in milliseconds."""
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    full_name = lines[0] if lines else "Unknown"

    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", raw_text)
    phone_match = re.search(r"\+?[\d\s().-]{10,}", raw_text)

    skills_block = _extract_section(raw_text, ("skills", "technical skills", "compétences"))
    skill_tokens = _split_skill_list(skills_block) if skills_block else _guess_skills(raw_text)

    experience = _extract_experience_heuristic(lines)
    projects = _extract_projects_heuristic(raw_text)

    return {
        "full_name": full_name,
        "email": email_match.group(0) if email_match else None,
        "phone": phone_match.group(0).strip() if phone_match else None,
        "location": None,
        "languages": [],
        "education": [],
        "experience": experience,
        "projects": projects,
        "skills": {
            "technical": skill_tokens[:20],
            "frameworks": [],
            "tools": [],
            "soft": [],
        },
        "certifications": [],
    }


def _extract_section(text: str, headers: tuple) -> str:
    lines = text.split("\n")
    section_headers = ("experience", "work history", "employment", "projects", "education", "certifications")
    for i, line in enumerate(lines):
        low = line.lower().strip()
        if any(h in low for h in headers) and len(line.strip()) < 50:
            if ":" in line:
                inline = line.split(":", 1)[1].strip()
                if inline:
                    return inline
            collected = []
            for next_line in lines[i + 1 : i + 8]:
                if not next_line.strip():
                    break
                if any(h in next_line.lower() for h in section_headers) and len(next_line.strip()) < 40:
                    break
                collected.append(next_line.strip())
            return " ".join(collected)
    return ""


def _split_skill_list(block: str) -> List[str]:
    parts = re.split(r"[,;|•\n]", block)
    return [p.strip() for p in parts if 1 < len(p.strip()) < 40][:25]


def _guess_skills(text: str) -> List[str]:
    known = (
        "python", "javascript", "typescript", "java", "react", "angular", "vue",
        "node", "docker", "kubernetes", "aws", "sql", "postgresql", "mongodb",
        "fastapi", "django", "flask", "spring", "git", "linux", "html", "css",
    )
    lower = text.lower()
    return [s for s in known if s in lower]


def _extract_experience_heuristic(lines: List[str]) -> List[dict]:
    entries = []
    exp_markers = ("experience", "work history", "employment", "expérience")
    in_exp = False
    for line in lines:
        low = line.lower()
        if any(m in low for m in exp_markers) and len(line) < 40:
            in_exp = True
            continue
        if in_exp and line and not line.startswith("•"):
            if " at " in low or " - " in line or "|" in line:
                title, _, company = line.partition(" at ")
                if not company.strip():
                    title, _, company = line.partition(" - ")
                entries.append({
                    "title": title.strip(),
                    "company": company.strip() or "Unknown",
                    "start_date": "",
                    "end_date": "",
                    "description": "",
                    "technologies": [],
                })
            if len(entries) >= 5:
                break
    return entries


def _extract_projects_heuristic(text: str) -> List[dict]:
    block = _extract_section(text, ("projects", "personal projects", "projets"))
    if not block:
        return []
    projects = []
    for chunk in re.split(r"\n{2,}|• ", block):
        chunk = chunk.strip()
        if len(chunk) > 10:
            projects.append({
                "name": chunk.split("\n")[0][:80],
                "description": chunk[:200],
                "technologies": [],
                "achievements": [],
            })
        if len(projects) >= 5:
            break
    return projects
