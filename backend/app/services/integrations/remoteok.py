"""RemoteOK public API — https://remoteok.com/api (official JSON feed)."""

import logging
from typing import List

from app.services.feed_cache import get_or_fetch_feed
from app.services.integrations.base import IntegrationResult, JobSourceIntegration, SearchParams
from app.services.integrations.http_client import get_http_client
from app.utils.job_normalizer import filter_jobs, normalize_job

logger = logging.getLogger(__name__)


class RemoteOKIntegration(JobSourceIntegration):
    name = "remoteok"
    rate_limit_per_minute = 10

    async def _fetch_feed(self) -> list:
        client = await get_http_client()
        response = await client.get(
            "https://remoteok.com/api",
            headers={"User-Agent": "Brieflyy/1.0"},
        )
        response.raise_for_status()
        logger.info("RemoteOK API: status=%d body_len=%d", response.status_code, len(response.text))
        return response.json()

    async def search(self, params: SearchParams) -> IntegrationResult:
        try:
            data = await get_or_fetch_feed(self.name, self._fetch_feed)
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

            raw_count = len(jobs)
            # Return all jobs fetched from the feed — do not pre-filter by
            # query here. Let the aggregator / fit-analyzer handle scoring and
            # filtering so we don't inadvertently drop many results.
            logger.info("API RemoteOK fetched %d jobs (no pre-filter)", raw_count)
            print(f"[Brieflyy] API RemoteOK fetched {raw_count} jobs", flush=True)

            result = IntegrationResult(source=self.name, jobs=jobs[: params.max_results])
            result.raw_count = raw_count
            return result

        except Exception as e:
            logger.error("API RemoteOK FAILED: %s", e)
            print(f"[Brieflyy] API RemoteOK FAILED: {e}", flush=True)
            return IntegrationResult(source=self.name, jobs=[], error=str(e))
