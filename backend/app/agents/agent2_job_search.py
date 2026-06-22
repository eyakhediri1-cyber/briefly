"""
Agent 2 — Job Search Engine
Queries multiple job platforms via the job aggregator, returns live results fast.
"""

import logging
from typing import List

from app.config import settings
from app.schemas.job import RawJobPosting, SearchFilters
from app.services.job_aggregator import job_aggregator
from app.utils.agent_logger import log_agent_start, log_agent_complete

logger = logging.getLogger(__name__)

BROAD_QUERIES = ("developer", "software engineer", "engineer")


class JobSearchAgent:
    """Agent 2: Multi-source job search — real APIs only, broad terms, no LLM delay."""

    async def run(self, target_role: str, cv_profile: dict,
                  filters: SearchFilters) -> List[RawJobPosting]:
        log_agent_start("Job Searcher", f"role='{target_role}'")
        logger.info("Agent 2: Starting fast job search for '%s'", target_role)

        # Expand the target role into multiple query variants to maximize API hits
        queries = self._expand_query_variants(target_role)
        logger.info("Agent 2: Using query variants: %s", queries)
        # Extra debug: show the exact queries and filters
        logger.debug("Agent 2: queries=%s filters=%s", queries, filters.model_dump() if hasattr(filters, 'model_dump') else filters)

        postings, meta = await job_aggregator.search(
            queries=queries,
            filters=filters,
            cv_profile=cv_profile,
        )
        # Log detailed source summary if available
        if meta.get("api_failures"):
            logger.warning("Agent 2: API failures: %s", meta["api_failures"]) 

        try:
            sources = meta.get('sources', {})
            for name, info in sources.items():
                logger.info("Agent2: source=%s jobs_returned=%s raw_fetched=%s errors=%s", name, info.get('jobs_returned'), info.get('raw_fetched'), info.get('errors'))
        except Exception:
            pass

        sources_summary = ", ".join(
            f"{name}={info.get('jobs_returned', info.get('count', 0))}"
            for name, info in meta.get("sources", {}).items()
        )
        log_agent_complete(
            "Job Searcher",
            f"{len(postings)} jobs in {meta.get('elapsed_ms', 0)}ms [{sources_summary}]",
        )
        logger.info("Agent 2 metadata: %s", meta)
        return postings

    def _build_queries(self, target_role: str) -> List[str]:
        """Broad search terms first — skip slow LLM query generation."""
        # Backwards compatible: simple builder kept for callers that use it
        return self._expand_query_variants(target_role)[:3]

    def _expand_query_variants(self, role: str) -> List[str]:
        """
        Expand a role into up to 6 query variants to increase coverage across
        different job platforms and wording.
        """
        r = (role or "").strip()
        if not r:
            return list(BROAD_QUERIES)

        base = r
        tokens = base.replace('-', ' ').split()
        head = tokens[0] if tokens else base

        variants = [
            base,
            base.replace('-', ' ').replace('internship', 'intern'),
            base.replace('internship', 'engineer'),
            f"junior {head}",
            f"{head} developer",
            f"{head} engineer",
        ]

        # dedupe while preserving order and lowercase-insensitive
        seen = set()
        out = []
        for v in variants:
            key = v.lower().strip()
            if key and key not in seen:
                seen.add(key)
                out.append(v.strip())
        return out[:6]


job_search_agent = JobSearchAgent()
