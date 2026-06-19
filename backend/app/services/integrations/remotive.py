"""Remotive public API — https://remotive.com/api/remote-jobs"""

import logging
from typing import List

from app.services.integrations.base import IntegrationResult, JobSourceIntegration, SearchParams
from app.services.integrations.http_client import get_http_client
from app.utils.job_normalizer import normalize_job

logger = logging.getLogger(__name__)


class RemotiveIntegration(JobSourceIntegration):
    name = "remotive"
    rate_limit_per_minute = 20

    async def search(self, params: SearchParams) -> IntegrationResult:
        try:
            client = await get_http_client()
            query_params = {"search": params.query}
            if params.contract_type == "internship":
                query_params["search"] = f"{params.query} intern"

            response = await client.get(
                "https://remotive.com/api/remote-jobs",
                params=query_params,
            )
            response.raise_for_status()
            data = response.json()

            jobs: List[dict] = []
            for item in data.get("jobs", []):
                raw = {
                    "title": item.get("title"),
                    "company": item.get("company_name"),
                    "location": item.get("candidate_required_location") or "Remote",
                    "description": item.get("description"),
                    "url": item.get("url"),
                    "contract_type": item.get("job_type"),
                    "posted_at": item.get("publication_date"),
                    "external_id": item.get("id"),
                    "remote": True,
                    "tags": item.get("tags") or [],
                }
                jobs.append(normalize_job(raw, self.name))

            logger.info("Remotive: %d jobs for '%s'", len(jobs), params.query)
            return IntegrationResult(source=self.name, jobs=jobs[: params.max_results])

        except Exception as e:
            logger.error("Remotive integration failed: %s", e)
            return IntegrationResult(source=self.name, jobs=[], error=str(e))
