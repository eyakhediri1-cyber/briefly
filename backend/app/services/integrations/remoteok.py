"""RemoteOK public API — https://remoteok.com/api (official JSON feed)."""

import logging
from typing import List

from app.services.integrations.base import IntegrationResult, JobSourceIntegration, SearchParams
from app.services.integrations.http_client import get_http_client
from app.utils.job_normalizer import filter_jobs, normalize_job

logger = logging.getLogger(__name__)


class RemoteOKIntegration(JobSourceIntegration):
    name = "remoteok"
    rate_limit_per_minute = 10  # API docs recommend conservative usage

    async def search(self, params: SearchParams) -> IntegrationResult:
        try:
            client = await get_http_client()
            # Official endpoint; tag filter via query when supported
            response = await client.get(
                "https://remoteok.com/api",
                headers={"User-Agent": "Brieflyy/1.0"},
            )
            response.raise_for_status()
            data = response.json()

            jobs: List[dict] = []
            for item in data:
                if not isinstance(item, dict) or "position" not in item:
                    continue
                raw = {
                    "title": item.get("position"),
                    "company": item.get("company"),
                    "location": item.get("location") or "Remote",
                    "description": item.get("description") or "",
                    "url": item.get("url") or item.get("apply_url"),
                    "contract_type": item.get("job_type", ""),
                    "posted_at": item.get("date"),
                    "external_id": item.get("id") or item.get("slug"),
                    "remote": True,
                    "tags": item.get("tags") or [],
                }
                jobs.append(normalize_job(raw, self.name))

            jobs = filter_jobs(
                jobs,
                query=params.query,
                location=params.location,
                contract_type=params.contract_type,
                remote=params.remote if params.remote is not None else True,
            )

            logger.info("RemoteOK: %d jobs matched '%s'", len(jobs), params.query)
            return IntegrationResult(source=self.name, jobs=jobs[: params.max_results])

        except Exception as e:
            logger.error("RemoteOK integration failed: %s", e)
            return IntegrationResult(source=self.name, jobs=[], error=str(e))
