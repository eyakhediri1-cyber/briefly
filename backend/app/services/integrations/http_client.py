"""Shared HTTP client helper for job integrations."""

from typing import Optional

import httpx

_shared_client: Optional[httpx.AsyncClient] = None


async def get_http_client(timeout: float = 20.0) -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": "Brieflyy/1.0 (job-search-aggregator; +https://brieflyy.app)"},
            follow_redirects=True,
        )
    return _shared_client


async def close_http_client() -> None:
    global _shared_client
    if _shared_client and not _shared_client.is_closed:
        await _shared_client.aclose()
        _shared_client = None
