"""
Internshala — popular internships platform in India/MENA.

No official public API. Brieflyy does NOT scrape Internshala.
This integration is disabled until Internshala partner API credentials are provided.
Set INTERNSHALA_API_KEY if/when available.
"""

import logging

from app.config import settings
from app.services.integrations.base import IntegrationResult, JobSourceIntegration, SearchParams

logger = logging.getLogger(__name__)

_PLACEHOLDERS = frozenset({"", "your-internshala-api-key"})


class InternshalaIntegration(JobSourceIntegration):
    name = "internshala"
    rate_limit_per_minute = 10

    @property
    def enabled(self) -> bool:
        return settings.INTERNSHALA_API_KEY.strip() not in _PLACEHOLDERS

    async def search(self, params: SearchParams) -> IntegrationResult:
        if not self.enabled:
            return IntegrationResult(
                source=self.name,
                jobs=[],
                error=(
                    "Internshala has no public API. "
                    "Brieflyy does not scrape — contact Internshala for partnership access."
                ),
            )

        logger.warning("Internshala: API key set but partner endpoint not yet implemented")
        return IntegrationResult(
            source=self.name,
            jobs=[],
            error="Internshala partner API endpoint pending implementation",
        )
