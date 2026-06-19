"""
Findwork.dev API — developer job listings (successor spirit to deprecated GitHub Jobs).

https://findwork.dev/developers/
Requires FINDWORK_API_KEY.
"""

import logging
from typing import List

from app.config import settings
from app.services.integrations.base import IntegrationResult, JobSourceIntegration, SearchParams
from app.services.integrations.http_client import get_http_client
from app.utils.job_normalizer import normalize_job

logger = logging.getLogger(__name__)

_PLACEHOLDERS = frozenset({"", "your-findwork-api-key"})


class FindworkIntegration(JobSourceIntegration):
    name = "findwork"
    rate_limit_per_minute = 20

    @property
    def enabled(self) -> bool:
        return settings.FINDWORK_API_KEY.strip() not in _PLACEHOLDERS

    async def search(self, params: SearchParams) -> IntegrationResult:
        if not self.enabled:
            return IntegrationResult(
                source=self.name,
                jobs=[],
                error="Findwork API key not configured (FINDWORK_API_KEY)",
            )

        try:
            client = await get_http_client()
            query_params = {
                "search": params.query,
                "location": params.location or "",
                "page": 1,
            }
            response = await client.get(
                "https://findwork.dev/api/jobs/",
                params=query_params,
                headers={"Authorization": f"Token {settings.FINDWORK_API_KEY}"},
            )
            response.raise_for_status()
            data = response.json()

            jobs: List[dict] = []
            for item in data.get("results", []):
                raw = {
                    "title": item.get("role"),
                    "company": item.get("company_name"),
                    "location": item.get("location"),
                    "description": item.get("description") or item.get("text"),
                    "url": item.get("url"),
                    "contract_type": item.get("employment_type"),
                    "posted_at": item.get("date_posted"),
                    "external_id": item.get("id"),
                    "remote": item.get("remote", False),
                    "tags": item.get("keywords") or [],
                }
                jobs.append(normalize_job(raw, self.name))

            logger.info("Findwork: %d jobs for '%s'", len(jobs), params.query)
            return IntegrationResult(source=self.name, jobs=jobs[: params.max_results])

        except Exception as e:
            logger.error("Findwork integration failed: %s", e)
            return IntegrationResult(source=self.name, jobs=[], error=str(e))
