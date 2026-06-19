"""
LinkedIn Job Search — official API only.

LinkedIn prohibits unauthorized scraping. Use Marketing/Recruiter APIs with
approved partner access. Set LINKEDIN_ACCESS_TOKEN when available.
"""

import logging

from app.config import settings
from app.services.integrations.base import IntegrationResult, JobSourceIntegration, SearchParams

logger = logging.getLogger(__name__)

_PLACEHOLDERS = frozenset({"", "your-linkedin-access-token"})


class LinkedInIntegration(JobSourceIntegration):
    name = "linkedin"
    rate_limit_per_minute = 10

    @property
    def enabled(self) -> bool:
        return settings.LINKEDIN_ACCESS_TOKEN.strip() not in _PLACEHOLDERS

    async def search(self, params: SearchParams) -> IntegrationResult:
        if not self.enabled:
            return IntegrationResult(
                source=self.name,
                jobs=[],
                error=(
                    "LinkedIn API token not configured. "
                    "Brieflyy does not scrape LinkedIn — use official LinkedIn Talent API."
                ),
            )

        logger.warning("LinkedIn: token configured but partner Job Search API requires additional setup")
        return IntegrationResult(
            source=self.name,
            jobs=[],
            error="LinkedIn Job Search API requires LinkedIn Talent Solutions partner access",
        )
