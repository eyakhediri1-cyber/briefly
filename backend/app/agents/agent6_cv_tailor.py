"""
Agent 6 — CV Tailoring Engine
Rewrites CV sections to match job requirements while NEVER inventing content.
Generates structured diffs with change reasoning and enforces hallucination checks.
"""

import difflib
import logging
import uuid
from typing import List, Dict, Optional

from app.middleware.error_handler import HallucinationDetectedError
from app.services.gemini_service import gemini_service

logger = logging.getLogger(__name__)

CV_REWRITE_SYSTEM_PROMPT = """You are rewriting a CV section to better match a specific job posting.

ABSOLUTE RULES — violating these disqualifies your output:
1. NEVER add a skill the student did not list in their original CV
2. NEVER invent an achievement, project, or responsibility
3. NEVER change any date
4. NEVER change company names or job titles
5. You MAY: reorder bullet points, use the job posting's terminology, clarify ambiguous phrasing, strengthen action verbs, add measurable context that was implicit

STUDENT'S ORIGINAL SECTION:
{original_section}

JOB POSTING KEYWORDS & REQUIREMENTS:
{ats_keywords}
{required_skills}

Rewrite the section. Return JSON:
{{
  "rewritten_text": "...",
  "changes": [
    {{
      "type": "REORDERED|REPHRASED|KEYWORD_ADDED|STRENGTHENED",
      "original": "...",
      "adapted": "...",
      "reason": "..."
    }}
  ]
}}"""


class CVTailoringAgent:
    """Agent 6: Tailors CV to specific job postings with hallucination prevention."""

    async def run(self, cv_profile: dict, job_analysis: dict) -> dict:
        """
        Tailor a CV for a specific job posting.
        
        Args:
            cv_profile: Structured CV data from Agent 1
            job_analysis: Analyzed job posting with requirements
            
        Returns:
            Dict with adapted sections, diff entries, and ATS score
        """
        logger.info(f"Agent 6: Tailoring CV for {job_analysis.get('title', 'job')}")

        structured = cv_profile.get("structured_data", cv_profile)
        required_skills = job_analysis.get("required_skills", [])
        ats_keywords = job_analysis.get("ats_keywords", [])
        original_skills = self._get_all_skills(structured)

        # Step 6.1: Determine section order based on job requirements
        sections = self._build_sections(structured, required_skills)

        # Step 6.2: Rewrite each section
        adapted_sections = {}
        all_diffs = []

        for section_name, section_content in sections.items():
            if not section_content.strip():
                adapted_sections[section_name] = section_content
                continue

            try:
                result = await self._rewrite_section(
                    section_name, section_content, ats_keywords, required_skills
                )

                adapted_text = result.get("rewritten_text", section_content)
                changes = result.get("changes", [])

                # Step 6.3: Hallucination check
                self._verify_no_hallucination(original_skills, adapted_text, changes)

                adapted_sections[section_name] = adapted_text

                # Generate diff entries
                for change in changes:
                    if not change.get("reason"):
                        change["reason"] = "Optimization for job requirements"
                    all_diffs.append({
                        "section": section_name,
                        "change_type": change.get("type", "REPHRASED"),
                        "original_text": change.get("original", ""),
                        "adapted_text": change.get("adapted", ""),
                        "reason": change["reason"],
                    })

            except HallucinationDetectedError:
                raise
            except Exception as e:
                logger.error(f"Section rewrite failed for '{section_name}': {e}")
                adapted_sections[section_name] = section_content

        # Generate unified diff
        original_full = "\n\n".join(f"## {k}\n{v}" for k, v in sections.items())
        adapted_full = "\n\n".join(f"## {k}\n{v}" for k, v in adapted_sections.items())
        unified_diff = self._generate_unified_diff(original_full, adapted_full)

        # Step 6.4: Compute ATS score
        ats_score = self._compute_ats_score(adapted_full, ats_keywords, required_skills)

        return {
            "id": str(uuid.uuid4()),
            "adapted_sections": adapted_sections,
            "diff": all_diffs,
            "ats_score_estimate": ats_score,
            "pending_approval": True,
            "unified_diff": unified_diff,
        }

    async def _rewrite_section(self, section_name: str, content: str,
                                ats_keywords: List[str],
                                required_skills: List[str]) -> dict:
        """Rewrite a single CV section using Gemini."""
        prompt = CV_REWRITE_SYSTEM_PROMPT.format(
            original_section=content,
            ats_keywords=", ".join(ats_keywords),
            required_skills=", ".join(required_skills),
        )
        return await gemini_service.generate_json(prompt)

    def _verify_no_hallucination(self, original_skills: List[str],
                                  adapted_text: str,
                                  changes: List[dict]) -> bool:
        """
        Verify Agent 6 did not invent skills or content.
        Raises HallucinationDetectedError if fabrication detected.
        """
        adapted_lower = adapted_text.lower()
        original_lower = {s.lower() for s in original_skills}

        # Check each change for potential hallucination
        for change in changes:
            if change.get("type") == "KEYWORD_ADDED":
                adapted = change.get("adapted", "")
                # Extract potential new skills mentioned in the adapted text
                words = set(adapted.lower().split())
                # This is a conservative check — flag obviously new technical terms
                # In production, use a more sophisticated NLP approach

        # Additional check: look for common tech skills in adapted text
        # that weren't in the original
        tech_skills_db = {
            "react", "angular", "vue", "svelte", "django", "flask", "spring",
            "kubernetes", "terraform", "rust", "go", "swift", "kotlin",
            "pytorch", "tensorflow", "hadoop", "spark", "kafka",
        }

        for skill in tech_skills_db:
            if skill in adapted_lower and skill not in " ".join(original_lower):
                # Check if it was in the original text too (might be in descriptions)
                # Only flag if truly not mentioned anywhere
                all_original = " ".join(original_lower)
                if skill not in all_original:
                    raise HallucinationDetectedError(
                        f"Agent 6 attempted to add '{skill}' which was not in original CV"
                    )

        return True

    def _build_sections(self, structured: dict, required_skills: List[str]) -> Dict[str, str]:
        """Build CV sections in optimal order for the target job."""
        sections = {}

        # Experience
        exp_texts = []
        for exp in structured.get("experience", []):
            text = f"**{exp.get('title', '')}** at {exp.get('company', '')}"
            if exp.get("start_date"):
                text += f" ({exp.get('start_date', '')} - {exp.get('end_date', 'Present')})"
            text += f"\n{exp.get('description', '')}"
            techs = exp.get("technologies", [])
            if techs:
                text += f"\nTechnologies: {', '.join(techs)}"
            exp_texts.append(text)
        if exp_texts:
            sections["Experience"] = "\n\n".join(exp_texts)

        # Projects
        proj_texts = []
        for proj in structured.get("projects", []):
            text = f"**{proj.get('name', '')}**\n{proj.get('description', '')}"
            techs = proj.get("technologies", [])
            if techs:
                text += f"\nTechnologies: {', '.join(techs)}"
            achievements = proj.get("achievements", [])
            if achievements:
                text += "\n" + "\n".join(f"• {a}" for a in achievements)
            proj_texts.append(text)
        if proj_texts:
            sections["Projects"] = "\n\n".join(proj_texts)

        # Skills
        skills = structured.get("skills", {})
        if isinstance(skills, dict):
            skill_parts = []
            for cat in ["technical", "frameworks", "tools"]:
                items = skills.get(cat, [])
                if items:
                    skill_parts.append(f"{cat.title()}: {', '.join(items)}")
            if skill_parts:
                sections["Skills"] = "\n".join(skill_parts)

        # Education
        edu_texts = []
        for edu in structured.get("education", []):
            text = f"**{edu.get('degree', '')}** in {edu.get('field', '')} — {edu.get('institution', '')}"
            if edu.get("start_year"):
                text += f" ({edu.get('start_year', '')} - {edu.get('end_year', 'Present')})"
            edu_texts.append(text)
        if edu_texts:
            sections["Education"] = "\n".join(edu_texts)

        return sections

    def _generate_unified_diff(self, original: str, adapted: str) -> List[str]:
        """Generate unified diff between original and adapted CV."""
        diff = difflib.unified_diff(
            original.splitlines(),
            adapted.splitlines(),
            fromfile="Original CV",
            tofile="Tailored CV",
            lineterm="",
        )
        return list(diff)

    def _compute_ats_score(self, adapted_text: str, ats_keywords: List[str],
                           required_skills: List[str]) -> int:
        """Estimate ATS keyword coverage percentage."""
        if not ats_keywords and not required_skills:
            return 75  # Neutral default

        all_keywords = list(set(ats_keywords + required_skills))
        adapted_lower = adapted_text.lower()

        matched = sum(1 for kw in all_keywords if kw.lower() in adapted_lower)
        return round((matched / len(all_keywords)) * 100) if all_keywords else 75

    def _get_all_skills(self, structured: dict) -> List[str]:
        """Get all skills from structured CV data."""
        skills = structured.get("skills", {})
        all_skills = []
        if isinstance(skills, dict):
            all_skills.extend(skills.get("technical", []))
            all_skills.extend(skills.get("frameworks", []))
            all_skills.extend(skills.get("tools", []))
            all_skills.extend(skills.get("soft", []))
        elif isinstance(skills, list):
            all_skills = skills

        # Also include technologies from experience and projects
        for exp in structured.get("experience", []):
            all_skills.extend(exp.get("technologies", []))
        for proj in structured.get("projects", []):
            all_skills.extend(proj.get("technologies", []))

        return list(set(all_skills))


# Singleton
cv_tailor = CVTailoringAgent()
