"""
Jooble REST API — international job search including MENA region.

https://jooble.org/api/about-rest-api
Requires JOOBLE_API_KEY.
"""

import logging
from typing import List

from app.config import settings
from app.services.integrations.base import IntegrationResult, JobSourceIntegration, SearchParams
from app.services.integrations.http_client import get_http_client
from app.utils.job_normalizer import normalize_job

logger = logging.getLogger(__name__)

_PLACEHOLDERS = frozenset({"", "your-jooble-api-key"})


class JoobleIntegration(JobSourceIntegration):
    name = "jooble"
    rate_limit_per_minute = 20

    @property
    def enabled(self) -> bool:
        return settings.JOOBLE_API_KEY.strip() not in _PLACEHOLDERS

    async def search(self, params: SearchParams) -> IntegrationResult:
        if not self.enabled:
            return IntegrationResult(
                source=self.name,
                jobs=[],
                error="Jooble API key not configured (JOOBLE_API_KEY)",
            )

        try:
            client = await get_http_client()
            payload = {
                "keywords": params.query,
                "location": params.location or "",
                "page": 1,
            }
            response = await client.post(
                f"https://jooble.org/api/{settings.JOOBLE_API_KEY}",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            jobs: List[dict] = []
            for item in data.get("jobs", []):
                raw = {
                    "title": item.get("title"),
                    "company": item.get("company"),
                    "location": item.get("location"),
                    "description": item.get("snippet"),
                    "url": item.get("link"),
                    "contract_type": item.get("type"),
                    "posted_at": item.get("updated"),
                    "external_id": item.get("id"),
                    "remote": "remote" in (item.get("location") or "").lower(),
                }
                jobs.append(normalize_job(raw, self.name))

            logger.info("Jooble: %d jobs for '%s'", len(jobs), params.query)
            return IntegrationResult(source=self.name, jobs=jobs[: params.max_results])

        except Exception as e:
            logger.error("Jooble integration failed: %s", e)
            return IntegrationResult(source=self.name, jobs=[], error=str(e))
