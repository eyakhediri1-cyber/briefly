"""Adzuna official Job Search API — https://developer.adzuna.com"""

import logging
from typing import List

from app.config import settings
from app.services.integrations.base import IntegrationResult, JobSourceIntegration, SearchParams
from app.services.integrations.http_client import get_http_client
from app.utils.job_normalizer import normalize_job

logger = logging.getLogger(__name__)

_PLACEHOLDERS = frozenset({"", "your-adzuna-app-id", "your-adzuna-app-key"})


class AdzunaIntegration(JobSourceIntegration):
    name = "adzuna"
    rate_limit_per_minute = 25

    @property
    def enabled(self) -> bool:
        return (
            settings.ADZUNA_APP_ID.strip() not in _PLACEHOLDERS
            and settings.ADZUNA_APP_KEY.strip() not in _PLACEHOLDERS
        )

    async def search(self, params: SearchParams) -> IntegrationResult:
        if not self.enabled:
            return IntegrationResult(source=self.name, jobs=[], error="Adzuna API keys not configured")

        try:
            client = await get_http_client()
            url = f"https://api.adzuna.com/v1/api/jobs/{settings.ADZUNA_COUNTRY}/search/1"
            query_params = {
                "app_id": settings.ADZUNA_APP_ID,
                "app_key": settings.ADZUNA_APP_KEY,
                "results_per_page": min(params.max_results, 50),
                "what": params.query,
            }
            if params.location:
                query_params["where"] = params.location

            response = await client.get(url, params=query_params)
            response.raise_for_status()
            data = response.json()

            jobs: List[dict] = []
            for item in data.get("results", []):
                raw = {
                    "title": item.get("title"),
                    "company": item.get("company", {}),
                    "location": item.get("location", {}),
                    "description": item.get("description"),
                    "url": item.get("redirect_url"),
                    "contract_type": item.get("contract_type"),
                    "posted_at": item.get("created"),
                    "external_id": item.get("id"),
                }
                jobs.append(normalize_job(raw, self.name))

            logger.info("Adzuna: %d jobs for '%s'", len(jobs), params.query)
            return IntegrationResult(source=self.name, jobs=jobs[: params.max_results])

        except Exception as e:
            logger.error("Adzuna integration failed: %s", e)
            return IntegrationResult(source=self.name, jobs=[], error=str(e))
