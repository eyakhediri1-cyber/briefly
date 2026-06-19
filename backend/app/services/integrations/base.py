"""Base class for job platform integrations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SearchParams:
    """Parameters passed to every job source integration."""

    query: str
    location: Optional[str] = None
    contract_type: Optional[str] = None  # internship | fulltime | parttime
    remote: Optional[bool] = None
    max_results: int = 30


@dataclass
class IntegrationResult:
    """Result from a single platform query."""

    source: str
    jobs: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    from_cache: bool = False
    elapsed_ms: int = 0


class JobSourceIntegration(ABC):
    """
    Abstract job source handler.

  Each integration must use only official APIs or explicitly permitted
  endpoints. Web scraping of LinkedIn, Glassdoor, etc. is NOT implemented.
    """

    name: str = "base"
    rate_limit_per_minute: int = 30

    @property
    def enabled(self) -> bool:
        return True

    @abstractmethod
    async def search(self, params: SearchParams) -> IntegrationResult:
        """Fetch jobs from this platform. Never raise — return IntegrationResult with error."""

    async def close(self) -> None:
        pass
