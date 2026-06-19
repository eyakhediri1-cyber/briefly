"""
AIESEC opportunities — international internships and volunteer programs.

Uses AIESEC's public opportunities API where available.
Falls back gracefully when the endpoint is unreachable.
"""

import logging
from typing import List

from app.services.integrations.base import IntegrationResult, JobSourceIntegration, SearchParams
from app.services.integrations.http_client import get_http_client
from app.utils.job_normalizer import filter_jobs, normalize_job

logger = logging.getLogger(__name__)

# AIESEC EXP API (public read endpoints used by aiesec.org)
AIESEC_OPPORTUNITIES_URL = "https://gis-api.aiesec.org/v2/opportunities"


class AIESECIntegration(JobSourceIntegration):
    name = "aiesec"
    rate_limit_per_minute = 15

    async def search(self, params: SearchParams) -> IntegrationResult:
        try:
            client = await get_http_client()
            query_params = {
                "per_page": min(params.max_results, 30),
                "page": 1,
                "filters[status]": "open",
            }
            if params.query:
                query_params["q"] = params.query

            response = await client.get(AIESEC_OPPORTUNITIES_URL, params=query_params)
            if response.status_code == 404:
                return IntegrationResult(
                    source=self.name,
                    jobs=[],
                    error="AIESEC API endpoint unavailable",
                )
            response.raise_for_status()
            data = response.json()

            items = data if isinstance(data, list) else data.get("data", data.get("opportunities", []))
            jobs: List[dict] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                host = item.get("host_lc") or item.get("branch") or {}
                location = ""
                if isinstance(host, dict):
                    location = host.get("name") or host.get("country") or ""

                raw = {
                    "title": item.get("title") or item.get("role") or "AIESEC Opportunity",
                    "company": "AIESEC",
                    "location": location or item.get("location", "International"),
                    "description": item.get("description") or item.get("experiences", ""),
                    "url": item.get("url") or f"https://www.aiesec.org/opportunity/{item.get('id', '')}",
                    "contract_type": "internship",
                    "posted_at": item.get("created_at") or item.get("date_opened"),
                    "external_id": item.get("id"),
                    "remote": False,
                    "tags": ["internship", "international", "aiesec"],
                }
                jobs.append(normalize_job(raw, self.name))

            jobs = filter_jobs(
                jobs,
                query=params.query,
                location=params.location,
                contract_type=params.contract_type or "internship",
            )

            logger.info("AIESEC: %d opportunities for '%s'", len(jobs), params.query)
            return IntegrationResult(source=self.name, jobs=jobs[: params.max_results])

        except Exception as e:
            logger.warning("AIESEC integration unavailable: %s", e)
            return IntegrationResult(source=self.name, jobs=[], error=str(e))
