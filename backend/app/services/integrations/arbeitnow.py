"""ArbeitNow free Job Board API — https://www.arbeitnow.com/api/job-board-api"""

import logging
from typing import List

from app.services.feed_cache import get_or_fetch_feed
from app.services.integrations.base import IntegrationResult, JobSourceIntegration, SearchParams
from app.services.integrations.http_client import get_http_client
from app.utils.job_normalizer import filter_jobs, normalize_job

logger = logging.getLogger(__name__)


class ArbeitnowIntegration(JobSourceIntegration):
    name = "arbeitnow"
    rate_limit_per_minute = 30

    async def _fetch_feed(self) -> dict:
        client = await get_http_client()
        response = await client.get("https://www.arbeitnow.com/api/job-board-api")
        response.raise_for_status()
        logger.info("ArbeitNow API: status=%d body_len=%d", response.status_code, len(response.text))
        return response.json()

    async def search(self, params: SearchParams) -> IntegrationResult:
        try:
            data = await get_or_fetch_feed(self.name, self._fetch_feed)
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

            raw_count = len(jobs)
            # Do not filter by query here — return the raw feed and let the
            # aggregator / analyzer handle relevance scoring.
            logger.info("API ArbeitNow fetched %d jobs (no pre-filter)", raw_count)
            print(f"[Brieflyy] API ArbeitNow fetched {raw_count} jobs", flush=True)

            result = IntegrationResult(source=self.name, jobs=jobs[: params.max_results])
            result.raw_count = raw_count
            return result

        except Exception as e:
            logger.error("API ArbeitNow FAILED: %s", e)
            print(f"[Brieflyy] API ArbeitNow FAILED: {e}", flush=True)
            return IntegrationResult(source=self.name, jobs=[], error=str(e))
