"""
GitHub Jobs integration — routes to Findwork.dev.

The GitHub Jobs API was officially shut down in May 2021.
This handler uses Findwork (developer-focused) when configured,
otherwise returns an informative empty result.
"""

import logging

from app.config import settings
from app.services.integrations.base import IntegrationResult, JobSourceIntegration, SearchParams
from app.services.integrations.findwork import FindworkIntegration

logger = logging.getLogger(__name__)


class GitHubJobsIntegration(JobSourceIntegration):
    name = "github_jobs"
    rate_limit_per_minute = 20

    def __init__(self):
        self._findwork = FindworkIntegration()

    @property
    def enabled(self) -> bool:
        return self._findwork.enabled

    async def search(self, params: SearchParams) -> IntegrationResult:
        if not self.enabled:
            return IntegrationResult(
                source=self.name,
                jobs=[],
                error=(
                    "GitHub Jobs API was deprecated in 2021. "
                    "Set FINDWORK_API_KEY to search developer roles via Findwork.dev."
                ),
            )

        result = await self._findwork.search(params)
        # Re-tag source for transparency in UI
        for job in result.jobs:
            job["source"] = self.name
        result.source = self.name
        logger.info("GitHub Jobs (via Findwork): %d jobs", len(result.jobs))
        return result
