"""Verify job aggregator never uses synthetic data."""

import pytest
from unittest.mock import AsyncMock, patch

from app.schemas.job import SearchFilters
from app.services.job_aggregator import JobAggregatorService
from app.services.integrations.base import IntegrationResult


@pytest.mark.asyncio
async def test_aggregator_returns_empty_when_all_apis_fail():
    aggregator = JobAggregatorService()

    async def empty_search(params):
        return IntegrationResult(source="remoteok", jobs=[], error="API unavailable")

    with patch.object(aggregator, "_integrations_for_search") as mock_integrations:
        mock_integration = AsyncMock()
        mock_integration.name = "remoteok"
        mock_integration.search = empty_search
        mock_integrations.return_value = [mock_integration]

        with patch("app.services.job_aggregator.redis_service") as mock_redis:
            mock_redis.get_json = AsyncMock(return_value=None)
            mock_redis.set_json = AsyncMock(return_value=True)

            postings, meta = await aggregator.search(
                queries=["software engineer"],
                filters=SearchFilters(max_results=20),
            )

    assert postings == []
    assert meta["total_returned"] == 0
    assert "synthetic" not in str(meta).lower()


@pytest.mark.asyncio
async def test_aggregator_has_no_synthetic_fallback_method():
    assert not hasattr(JobAggregatorService, "_load_synthetic_fallback")
