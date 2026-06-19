"""Arbeitnow free Job Board API — https://www.arbeitnow.com/api/job-board-api"""

import logging
from typing import List

from app.services.integrations.base import IntegrationResult, JobSourceIntegration, SearchParams
from app.services.integrations.http_client import get_http_client
from app.utils.job_normalizer import filter_jobs, normalize_job

logger = logging.getLogger(__name__)


class ArbeitnowIntegration(JobSourceIntegration):
    name = "arbeitnow"
    rate_limit_per_minute = 30

    async def search(self, params: SearchParams) -> IntegrationResult:
        try:
            client = await get_http_client()
            response = await client.get("https://www.arbeitnow.com/api/job-board-api")
            response.raise_for_status()
            data = response.json()

            jobs: List[dict] = []
            for item in data.get("data", []):
                raw = {
                    "title": item.get("title"),
                    "company": item.get("company_name"),
                    "location": item.get("location"),
                    "description": item.get("description"),
                    "url": item.get("url"),
                    "contract_type": "internship" if item.get("visa_sponsorship") else "",
                    "posted_at": item.get("created_at"),
                    "external_id": item.get("slug"),
                    "remote": item.get("remote", False),
                    "tags": item.get("tags") or [],
                }
                jobs.append(normalize_job(raw, self.name))

            jobs = filter_jobs(
                jobs,
                query=params.query,
                location=params.location,
                contract_type=params.contract_type,
                remote=params.remote,
            )

            logger.info("Arbeitnow: %d jobs matched '%s'", len(jobs), params.query)
            return IntegrationResult(source=self.name, jobs=jobs[: params.max_results])

        except Exception as e:
            logger.error("Arbeitnow integration failed: %s", e)
            return IntegrationResult(source=self.name, jobs=[], error=str(e))
