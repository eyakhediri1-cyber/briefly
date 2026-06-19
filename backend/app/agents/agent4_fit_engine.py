"""
Agent 4 — Fit Reasoning Engine ("The Brain")
The most critical agent. Computes semantic skill matching via cosine similarity,
generates LLM-powered explanations for each skill assessment, and produces
explainable fit scores with full reasoning chains.
"""

import asyncio
import logging
import os
import uuid
from typing import List, Dict, Tuple

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.config import settings
from app.schemas.job import AnalyzedJobPosting
from app.schemas.fit import SkillAssessment, FitAnalysisResponse
from app.services.gemini_service import gemini_service
from app.services.embedding_service import embedding_service
from app.utils.agent_logger import log_agent_start, log_agent_complete

logger = logging.getLogger(__name__)

SKILL_REASONING_PROMPT = """Given this student profile:
Skills: {student_skills}
Experience: {experience_summary}
Projects: {projects_summary}

And this job requirement: "{required_skill}"

The cosine similarity between the student's closest skill and this requirement is {similarity:.2f}.

Explain in 1-2 sentences:
1. Whether the student has an exact match, a transferable skill, or a genuine gap
2. What specific evidence from their profile supports this assessment

Be concrete, honest, and non-definitive. Never say "you are unqualified."
Return JSON: {{"assessment": "EXACT_MATCH|TRANSFERABLE|PARTIAL|GAP", "explanation": "...", "evidence": "..."}}"""

OVERALL_REASONING_PROMPT = """Based on this skill-by-skill analysis for a {job_title} position at {company}:

Strengths (matching skills): {strengths}
Transferable skills: {transferable}
Gaps: {gaps}
Fit percentage: {fit_pct}%

Write 3-4 sentences summarizing this student's fit for the role. Be encouraging but honest.
Be specific about what makes them a good or developing candidate.
Do NOT use generic phrases. Reference specific skills and evidence."""


class FitReasoningEngine:
    """Agent 4: Computes semantic fit scores with full explainability."""

    async def run(self, cv_profile: dict, analyzed_jobs: List[AnalyzedJobPosting]) -> List[dict]:
        """
        Compute fit analyses for all analyzed job postings.
        
        Args:
            cv_profile: Structured CV data with embeddings
            analyzed_jobs: List of analyzed job postings with skill embeddings
            
        Returns:
            List of fit analysis dicts
        """
        log_agent_start("Fit Reasoning Engine", f"{len(analyzed_jobs)} jobs")
        logger.info(f"Agent 4: Computing fit for {len(analyzed_jobs)} jobs")

        # Load saved FAISS index from CV upload if available
        index_path = cv_profile.get("embedding_index_path", "")
        if index_path:
            loaded = embedding_service.load_faiss_index(index_path)
            if loaded is not None:
                logger.info("Agent 4: Using FAISS index with %d vectors", loaded.ntotal)
            else:
                logger.warning("Agent 4: FAISS index unavailable at %s", index_path)

        # Prepare student skill embeddings
        student_skills = self._get_all_skills(cv_profile)
        student_skill_embeddings = {}
        for skill in student_skills:
            emb = await embedding_service.embed_text(skill)
            student_skill_embeddings[skill] = emb

        # Prepare profile summaries for LLM reasoning
        profile_context = self._build_profile_context(cv_profile)

        fit_analyses = []
        for i, job in enumerate(analyzed_jobs):
            logger.info(f"Agent 4: Analyzing fit for job {i + 1}/{len(analyzed_jobs)}: {job.title}")
            try:
                analysis = await self._compute_fit(
                    job, student_skills, student_skill_embeddings, profile_context
                )
                fit_analyses.append(analysis)
            except Exception as e:
                logger.error(f"Agent 4: Failed to compute fit for '{job.title}': {e}")
                continue

        log_agent_complete("Fit Reasoning Engine", f"{len(fit_analyses)} analyses")
        logger.info(f"Agent 4: Completed fit analysis for {len(fit_analyses)} jobs")
        return fit_analyses

    async def _compute_fit(self, job: AnalyzedJobPosting, student_skills: List[str],
                           student_embeddings: Dict[str, List[float]],
                           profile_context: dict) -> dict:
        """Compute full fit analysis for a single job posting."""

        skill_assessments = []
        strengths = []
        gaps = []
        transferable = []

        for req_skill in job.required_skills:
            # Step 4.1: Semantic matching via cosine similarity
            best_match, best_sim = self._find_best_match(
                req_skill, job.skill_embeddings.get(req_skill, []),
                student_skills, student_embeddings
            )
            category, sim_score = self._categorize_match(best_sim)

            # Step 4.2: LLM reasoning (skip in mock/dev mode for speed)
            if settings.gcp_enabled:
                reasoning = await self._get_skill_reasoning(
                    req_skill, sim_score, profile_context
                )
            else:
                reasoning = {
                    "assessment": category,
                    "explanation": f"Semantic similarity score: {sim_score:.2f} (closest: {best_match or 'none'})",
                    "evidence": f"Matched against CV skill profile",
                }

            assessment = SkillAssessment(
                skill_name=req_skill,
                assessment=reasoning.get("assessment", category),
                similarity_score=round(sim_score, 3),
                explanation=reasoning.get("explanation", f"Similarity: {sim_score:.2f}"),
                evidence=reasoning.get("evidence", f"Closest match: {best_match}"),
            )
            skill_assessments.append(assessment)

            # Categorize
            if assessment.assessment == "EXACT_MATCH":
                strengths.append(req_skill)
            elif assessment.assessment == "TRANSFERABLE":
                transferable.append(req_skill)
            elif assessment.assessment == "GAP":
                gaps.append(req_skill)

        # Step 4.3: Compute fit percentage
        fit_pct = self._compute_fit_percentage(skill_assessments)

        # Step 4.4: Categorize
        fit_category = self._categorize_fit(fit_pct)

        # Generate overall reasoning
        if settings.gcp_enabled:
            overall = await self._generate_overall_reasoning(
                job, fit_pct, strengths, transferable, gaps
            )
        else:
            overall = (
                f"Your fit for {job.title} at {job.company} is {fit_pct}%. "
                f"Strengths: {', '.join(strengths[:3]) or 'N/A'}. "
                f"Areas to develop: {', '.join(gaps[:3]) or 'N/A'}."
            )

        return {
            "id": str(uuid.uuid4()),
            "job_posting_id": str(job.raw_posting_id),
            "job_title": job.title,
            "company": job.company,
            "location": job.location,
            "contract_type": job.contract_type,
            "url": job.url,
            "source": job.source,
            "fit_percentage": fit_pct,
            "fit_category": fit_category,
            "skill_breakdown": [a.model_dump() for a in skill_assessments],
            "strengths": strengths,
            "gaps": gaps,
            "transferable_skills": transferable,
            "overall_reasoning": overall,
        }

    def _find_best_match(self, req_skill: str, req_embedding: List[float],
                         student_skills: List[str],
                         student_embeddings: Dict[str, List[float]]) -> Tuple[str, float]:
        """Find the best matching student skill using cosine similarity."""
        if not student_embeddings or not req_embedding:
            # Fallback: simple string matching
            req_lower = req_skill.lower()
            for s_skill in student_skills:
                if req_lower in s_skill.lower() or s_skill.lower() in req_lower:
                    return s_skill, 0.95
            return "", 0.0

        best_skill = ""
        best_sim = 0.0

        req_vec = np.array(req_embedding).reshape(1, -1)
        for s_skill, s_emb in student_embeddings.items():
            s_vec = np.array(s_emb).reshape(1, -1)
            try:
                sim = cosine_similarity(req_vec, s_vec)[0][0]
                if sim > best_sim:
                    best_sim = sim
                    best_skill = s_skill
            except Exception:
                continue

        return best_skill, float(best_sim)

    def _categorize_match(self, similarity: float) -> Tuple[str, float]:
        """Categorize skill match based on cosine similarity threshold."""
        if similarity >= 0.95:
            return "EXACT_MATCH", similarity
        elif similarity >= 0.75:
            return "TRANSFERABLE", similarity
        elif similarity >= 0.55:
            return "PARTIAL", similarity
        else:
            return "GAP", similarity

    async def _get_skill_reasoning(self, req_skill: str, similarity: float,
                                    profile_context: dict) -> dict:
        """Get LLM reasoning for a single skill assessment."""
        try:
            prompt = SKILL_REASONING_PROMPT.format(
                student_skills=", ".join(profile_context["skills"][:15]),
                experience_summary=profile_context["experience_summary"],
                projects_summary=profile_context["projects_summary"],
                required_skill=req_skill,
                similarity=similarity,
            )
            return await gemini_service.generate_json(prompt)
        except Exception as e:
            logger.warning(f"LLM reasoning failed for '{req_skill}': {e}")
            return {
                "assessment": self._categorize_match(similarity)[0],
                "explanation": f"Based on semantic similarity of {similarity:.2f}",
                "evidence": "Automated analysis",
            }

    def _compute_fit_percentage(self, assessments: List[SkillAssessment]) -> int:
        """Compute overall fit percentage from skill assessments."""
        if not assessments:
            return 50  # Neutral default

        weights = {"EXACT_MATCH": 1.0, "TRANSFERABLE": 0.7, "PARTIAL": 0.4, "GAP": 0.0}
        total = sum(weights.get(a.assessment, 0.0) for a in assessments)
        return round((total / len(assessments)) * 100)

    def _categorize_fit(self, fit_pct: int) -> str:
        """Categorize fit level."""
        if fit_pct >= 80:
            return "STRONG_FIT"
        elif fit_pct >= 60:
            return "PARTIAL_FIT"
        elif fit_pct >= 40:
            return "STRETCH_GOAL"
        else:
            return "DEVELOP_FIRST"

    async def _generate_overall_reasoning(self, job: AnalyzedJobPosting,
                                           fit_pct: int, strengths: List[str],
                                           transferable: List[str],
                                           gaps: List[str]) -> str:
        """Generate overall reasoning summary."""
        try:
            prompt = OVERALL_REASONING_PROMPT.format(
                job_title=job.title,
                company=job.company,
                strengths=", ".join(strengths) or "None identified",
                transferable=", ".join(transferable) or "None identified",
                gaps=", ".join(gaps) or "None identified",
                fit_pct=fit_pct,
            )
            return await gemini_service.generate(prompt)
        except Exception:
            return (
                f"Your fit for {job.title} at {job.company} is {fit_pct}%. "
                f"Strengths: {', '.join(strengths[:3]) or 'N/A'}. "
                f"Areas to develop: {', '.join(gaps[:3]) or 'N/A'}."
            )

    def _get_all_skills(self, cv_profile: dict) -> List[str]:
        """Extract all skills from CV profile."""
        structured = cv_profile.get("structured_data", cv_profile)
        skills = structured.get("skills", {})
        all_skills = []
        if isinstance(skills, dict):
            all_skills.extend(skills.get("technical", []))
            all_skills.extend(skills.get("frameworks", []))
            all_skills.extend(skills.get("tools", []))
        elif isinstance(skills, list):
            all_skills = skills
        return all_skills

    def _build_profile_context(self, cv_profile: dict) -> dict:
        """Build context dict for LLM prompts."""
        structured = cv_profile.get("structured_data", cv_profile)
        skills = self._get_all_skills(cv_profile)

        exp_parts = []
        for exp in structured.get("experience", []):
            exp_parts.append(f"{exp.get('title', '')} at {exp.get('company', '')}: {exp.get('description', '')[:100]}")
        exp_summary = "; ".join(exp_parts) if exp_parts else "No experience listed"

        proj_parts = []
        for proj in structured.get("projects", []):
            techs = ", ".join(proj.get("technologies", []))
            proj_parts.append(f"{proj.get('name', '')}: {proj.get('description', '')[:80]} ({techs})")
        proj_summary = "; ".join(proj_parts) if proj_parts else "No projects listed"

        return {
            "skills": skills,
            "experience_summary": exp_summary,
            "projects_summary": proj_summary,
        }


# Singleton
fit_engine = FitReasoningEngine()
