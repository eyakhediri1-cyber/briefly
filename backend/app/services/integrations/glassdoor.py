"""
Glassdoor — no public job search API for third parties.

Brieflyy does NOT scrape Glassdoor (violates Terms of Service).
Use Adzuna, Jooble, or Indeed partner APIs for similar coverage.
"""

from app.services.integrations.base import IntegrationResult, JobSourceIntegration, SearchParams


class GlassdoorIntegration(JobSourceIntegration):
    name = "glassdoor"
    rate_limit_per_minute = 0

    @property
    def enabled(self) -> bool:
        return False

    async def search(self, params: SearchParams) -> IntegrationResult:
        return IntegrationResult(
            source=self.name,
            jobs=[],
            error="Glassdoor scraping is disabled. Use official partner APIs instead.",
        )
