"""
Wellfound (formerly AngelList Talent) — startup jobs.

Official GraphQL/API access requires partner credentials.
Set WELLFOUND_API_TOKEN when available.
Docs: https://wellfound.com/
"""

import logging
from typing import List

from app.config import settings
from app.services.integrations.base import IntegrationResult, JobSourceIntegration, SearchParams
from app.services.integrations.http_client import get_http_client
from app.utils.job_normalizer import normalize_job

logger = logging.getLogger(__name__)

_PLACEHOLDERS = frozenset({"", "your-wellfound-api-token"})


class WellfoundIntegration(JobSourceIntegration):
    name = "wellfound"
    rate_limit_per_minute = 15

    @property
    def enabled(self) -> bool:
        return settings.WELLFOUND_API_TOKEN.strip() not in _PLACEHOLDERS

    async def search(self, params: SearchParams) -> IntegrationResult:
        if not self.enabled:
            return IntegrationResult(
                source=self.name,
                jobs=[],
                error="Wellfound API token not configured (WELLFOUND_API_TOKEN)",
            )

        try:
            client = await get_http_client()
            # Wellfound GraphQL endpoint (partner access)
            graphql_query = """
            query SearchJobs($query: String!) {
              jobListings(query: $query, page: 1) {
                id
                title
                slug
                location
                remote
                description
                company { name }
                url
              }
            }
            """
            response = await client.post(
                "https://api.wellfound.com/graphql",
                json={"query": graphql_query, "variables": {"query": params.query}},
                headers={
                    "Authorization": f"Bearer {settings.WELLFOUND_API_TOKEN}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()

            jobs: List[dict] = []
            listings = (data.get("data") or {}).get("jobListings") or []
            for item in listings:
                company = item.get("company") or {}
                raw = {
                    "title": item.get("title"),
                    "company": company.get("name") if isinstance(company, dict) else company,
                    "location": item.get("location") or "Remote",
                    "description": item.get("description"),
                    "url": item.get("url") or f"https://wellfound.com/role/l/{item.get('slug', '')}",
                    "external_id": item.get("id"),
                    "remote": item.get("remote", False),
                }
                jobs.append(normalize_job(raw, self.name))

            logger.info("Wellfound: %d jobs for '%s'", len(jobs), params.query)
            return IntegrationResult(source=self.name, jobs=jobs[: params.max_results])

        except Exception as e:
            logger.error("Wellfound integration failed: %s", e)
            return IntegrationResult(source=self.name, jobs=[], error=str(e))
