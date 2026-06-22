"""Build CV tailoring preview summaries for the UI."""

from typing import Any, Dict, List


def build_cv_preview(
    adapted_sections: Dict[str, str],
    original_sections: Dict[str, str],
    diff: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Extract preview data: snippet, emphasized skills, highlighted projects, key changes."""
    emphasized_skills: List[str] = []
    highlighted_projects: List[str] = []

    for entry in diff or []:
        section = entry.get("section", "")
        change_type = entry.get("change_type", "")
        adapted_text = (entry.get("adapted_text") or "").strip()

        if section == "Skills" and change_type in ("KEYWORD_ADDED", "STRENGTHENED", "REPHRASED"):
            if adapted_text and adapted_text not in emphasized_skills:
                emphasized_skills.append(adapted_text[:120])

        if section == "Projects":
            if adapted_text and adapted_text not in highlighted_projects:
                highlighted_projects.append(adapted_text[:160])

    if not emphasized_skills and adapted_sections.get("Skills"):
        emphasized_skills = [
            line.strip()
            for line in adapted_sections["Skills"].split("\n")
            if line.strip()
        ][:4]

    if not highlighted_projects and adapted_sections.get("Projects"):
        blocks = adapted_sections["Projects"].split("\n\n")
        highlighted_projects = [b.strip()[:160] for b in blocks if b.strip()][:3]

    preview_parts: List[str] = []
    for section_name in ("Skills", "Projects", "Experience"):
        content = adapted_sections.get(section_name, "")
        if content:
            preview_parts.append(f"**{section_name}**\n{content[:250]}")

    key_changes = [
        {
            "section": d.get("section", ""),
            "change_type": d.get("change_type", ""),
            "original_text": (d.get("original_text") or "")[:100],
            "adapted_text": (d.get("adapted_text") or "")[:100],
            "reason": d.get("reason", ""),
        }
        for d in (diff or [])[:4]
    ]

    return {
        "preview_snippet": "\n\n".join(preview_parts)[:600],
        "emphasized_skills": emphasized_skills[:6],
        "highlighted_projects": highlighted_projects[:4],
        "key_changes": key_changes,
        "original_sections": original_sections,
        "adapted_sections": adapted_sections,
    }
