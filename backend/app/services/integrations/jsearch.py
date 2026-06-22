"""JSearch (RapidAPI) integration for extra job source."""

import logging
from typing import List, Dict
import os

import httpx

from app.config import settings
from app.services.integrations.base import IntegrationResult, JobSourceIntegration, SearchParams
from app.utils.job_normalizer import normalize_job, filter_jobs

logger = logging.getLogger(__name__)


class JSearchIntegration(JobSourceIntegration):
    name = "jsearch"
    rate_limit_per_minute = 60

    def __init__(self):
        self.api_key = settings.JSEARCH_API_KEY or os.getenv("JSEARCH_API_KEY")
        self.base_url = "https://jsearch.p.rapidapi.com/search"

    async def search(self, params: SearchParams) -> IntegrationResult:
        if not self.api_key:
            logger.warning("[JSearch] API key not configured")
            return IntegrationResult(source=self.name, jobs=[], error="no_api_key")

        try:
            timeout = float(getattr(settings, "JOB_API_TIMEOUT_PER_SOURCE", 5))
            async with httpx.AsyncClient(timeout=timeout) as client:
                qparams = {
                    "query": params.query,
                    "page": 1,
                    "num_pages": 1,
                    "country": "US",
                }
                if params.location and params.location.lower() != "remote":
                    # best-effort map simple location to country code
                    qparams["country"] = self._location_to_country(params.location)

                headers = {
                    "X-RapidAPI-Key": self.api_key,
                    "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
                }

                resp = await client.get(self.base_url, params=qparams, headers=headers)
                resp.raise_for_status()
                data = resp.json()

                items = data.get("data", []) if isinstance(data, dict) else []
                jobs: List[Dict] = []
                for item in items:
                    raw = {
                        "title": item.get("job_title") or item.get("title"),
                        "company": item.get("employer_name") or item.get("company_name"),
                        "location": item.get("job_city") or item.get("location"),
                        "description": item.get("job_description") or item.get("snippet"),
                        "url": item.get("job_apply_link") or item.get("url"),
                        "contract_type": item.get("job_employment_type"),
                        "external_id": item.get("job_id"),
                        "tags": item.get("tags") or [],
                    }
                    jobs.append(normalize_job(raw, self.name))

                raw_count = len(jobs)
                # Do not pre-filter here; return retrieved jobs for downstream
                # relevance scoring.
                result = IntegrationResult(source=self.name, jobs=jobs[: params.max_results])
                result.raw_count = raw_count
                logger.info("[JSearch] Fetched %d jobs for '%s' (no pre-filter)", raw_count, params.query)
                return result

        except Exception as e:
            logger.warning("[JSearch] Error: %s", e)
            return IntegrationResult(source=self.name, jobs=[], error=str(e))

    def _location_to_country(self, location: str) -> str:
        if not location:
            return "US"
        loc = location.lower()
        mapping = {
            "paris": "FR",
            "france": "FR",
            "london": "GB",
            "uk": "GB",
            "berlin": "DE",
            "germany": "DE",
        }
        return mapping.get(loc, "US")
