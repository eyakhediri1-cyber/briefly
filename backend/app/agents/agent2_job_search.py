"""
Agent 2 — Job Search Engine
Queries multiple job platforms via the job aggregator, ranks by CV relevance,
and returns deduplicated live results.
"""

import logging
from typing import List

from app.schemas.job import RawJobPosting, SearchFilters
from app.services.gemini_service import gemini_service
from app.services.job_aggregator import job_aggregator
from app.utils.agent_logger import log_agent_start, log_agent_complete

logger = logging.getLogger(__name__)

QUERY_GENERATION_PROMPT = """Given target role: "{target_role}" and student skills: {skills}
Generate 5 different search queries for job board APIs. Cover:
1. The exact phrase
2. A more senior/general version
3. A technology-specific version
4. A synonym version
5. An adjacent role version
Return as JSON array of strings."""


class JobSearchAgent:
    """Agent 2: Multi-source job search with semantic ranking."""

    async def run(self, target_role: str, cv_profile: dict,
                  filters: SearchFilters) -> List[RawJobPosting]:
        log_agent_start("Job Searcher", f"role='{target_role}'")
        logger.info(f"Agent 2: Starting multi-source job search for '{target_role}'")

        skills = self._get_top_skills(cv_profile, limit=10)
        logger.info(f"Agent 2: Using skills: {skills}")

        queries = await self._generate_queries(target_role, skills)
        logger.info(f"Agent 2: Generated {len(queries)} query variants: {queries}")

        postings, meta = await job_aggregator.search(
            queries=queries,
            filters=filters,
            cv_profile=cv_profile,
        )

        sources_summary = ", ".join(
            f"{name}({info.get('count', 0)})"
            for name, info in meta.get("sources", {}).items()
            if info.get("count", 0) > 0
        )
        log_agent_complete(
            "Job Searcher",
            f"{len(postings)} postings from [{sources_summary or 'cache'}]",
        )
        logger.info("Agent 2 metadata: %s", meta)
        return postings

    async def _generate_queries(self, target_role: str, skills: List[str]) -> List[str]:
        try:
            prompt = QUERY_GENERATION_PROMPT.format(
                target_role=target_role,
                skills=", ".join(skills[:10]),
            )
            result = await gemini_service.generate_json(prompt)

            if isinstance(result, list):
                return result[:5]
            return [target_role]
        except Exception as e:
            logger.error(f"Query generation failed: {e}")
            queries = [target_role, f"junior {target_role}", f"{target_role} intern"]
            if "intern" in (target_role + " ".join(skills)).lower():
                queries.append("internship")
            return queries

    def _get_top_skills(self, cv_profile: dict, limit: int = 10) -> List[str]:
        structured = cv_profile.get("structured_data", cv_profile)
        skills = structured.get("skills", {})

        all_skills = []
        if isinstance(skills, dict):
            all_skills.extend(skills.get("technical", []))
            all_skills.extend(skills.get("frameworks", []))
            all_skills.extend(skills.get("tools", []))
        elif isinstance(skills, list):
            all_skills = skills

        return all_skills[:limit]


job_search_agent = JobSearchAgent()
