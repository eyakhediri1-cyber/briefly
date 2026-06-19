"""
Indeed Publisher API — requires official partner approval.

https://opensource.indeedeng.io/api-documentation/
Set INDEED_PUBLISHER_ID and INDEED_API_KEY when approved.
"""

import logging

from app.config import settings
from app.services.integrations.base import IntegrationResult, JobSourceIntegration, SearchParams

logger = logging.getLogger(__name__)

_PLACEHOLDERS = frozenset({"", "your-indeed-publisher-id", "your-indeed-api-key"})


class IndeedIntegration(JobSourceIntegration):
    name = "indeed"
    rate_limit_per_minute = 10

    @property
    def enabled(self) -> bool:
        return (
            settings.INDEED_PUBLISHER_ID.strip() not in _PLACEHOLDERS
            and settings.INDEED_API_KEY.strip() not in _PLACEHOLDERS
        )

    async def search(self, params: SearchParams) -> IntegrationResult:
        if not self.enabled:
            return IntegrationResult(
                source=self.name,
                jobs=[],
                error=(
                    "Indeed Partner API not configured. "
                    "Apply at https://opensource.indeedeng.io/api-documentation/"
                ),
            )

        # Indeed's official API uses XML/JSON publisher endpoints per partner agreement.
        # Implementation placeholder — credentials gate activation.
        logger.warning("Indeed integration: credentials present but endpoint requires partner setup")
        return IntegrationResult(
            source=self.name,
            jobs=[],
            error="Indeed partner endpoint not yet wired — contact Indeed for API access",
        )
