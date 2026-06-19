"""Normalize job postings from heterogeneous APIs into a standard schema."""

import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.schemas.job import RawJobPosting

# Canonical fields every integration must map to
NORMALIZED_FIELDS = (
    "title",
    "company",
    "location",
    "contract_type",
    "description",
    "url",
    "posted_at",
    "source",
    "external_id",
    "remote",
    "tags",
)


def _clean_html(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"<[^>]+>", " ", text).strip()


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def normalize_job(raw: Dict[str, Any], source: str) -> Dict[str, Any]:
    """
    Map a platform-specific dict to the canonical normalized shape.

    Handlers should pre-map fields when possible; this function fills gaps
    and strips HTML from descriptions.
    """
    title = (raw.get("title") or raw.get("position") or "Untitled").strip()
    company = (
        raw.get("company")
        or raw.get("company_name")
        or raw.get("employer")
        or "Unknown"
    )
    if isinstance(company, dict):
        company = company.get("display_name") or company.get("name") or "Unknown"

    location = raw.get("location") or raw.get("city") or ""
    if isinstance(location, dict):
        location = location.get("display_name") or location.get("name") or ""

    description = _clean_html(
        raw.get("description") or raw.get("snippet") or raw.get("job_description") or ""
    )
    if not description and raw.get("tags"):
        tags = raw.get("tags")
        if isinstance(tags, list):
            description = f"Role involving: {', '.join(str(t) for t in tags)}"

    contract_type = (
        raw.get("contract_type")
        or raw.get("job_type")
        or raw.get("type")
        or ""
    )
    if isinstance(contract_type, list):
        contract_type = ", ".join(contract_type)

    url = raw.get("url") or raw.get("link") or raw.get("apply_url") or ""
    posted_at = _parse_datetime(
        raw.get("posted_at") or raw.get("date") or raw.get("created") or raw.get("pubDate")
    )

    remote = raw.get("remote")
    if remote is None:
        loc_lower = str(location).lower()
        remote = "remote" in loc_lower or raw.get("candidate_required_location") == "Worldwide"

    tags = raw.get("tags") or raw.get("skills") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    return {
        "title": title,
        "company": str(company).strip(),
        "location": str(location).strip(),
        "contract_type": str(contract_type).strip(),
        "description": description[:8000],
        "url": str(url).strip(),
        "posted_at": posted_at.isoformat() if posted_at else None,
        "source": source,
        "external_id": str(raw.get("external_id") or raw.get("id") or ""),
        "remote": bool(remote),
        "tags": tags if isinstance(tags, list) else [],
    }


def to_raw_job_posting(normalized: Dict[str, Any]) -> RawJobPosting:
    """Convert normalized dict to RawJobPosting schema."""
    posted = _parse_datetime(normalized.get("posted_at"))
    return RawJobPosting(
        id=uuid.uuid4(),
        title=normalized["title"],
        company=normalized["company"],
        location=normalized["location"],
        contract_type=normalized.get("contract_type", ""),
        description=normalized.get("description") or normalized["title"],
        url=normalized.get("url", ""),
        posted_at=posted,
        source=normalized.get("source", "unknown"),
    )


def dedupe_key(job: Dict[str, Any]) -> tuple:
    """Dedupe by title + company + location."""
    return (
        job.get("title", "").lower().strip(),
        job.get("company", "").lower().strip(),
        job.get("location", "").lower().strip(),
    )


def filter_jobs(
    jobs: List[Dict[str, Any]],
    *,
    query: str,
    location: Optional[str] = None,
    contract_type: Optional[str] = None,
    remote: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """Client-side filter when APIs lack native filtering."""
    query_terms = [t.lower() for t in query.split() if len(t) > 2]
    filtered = []

    for job in jobs:
        haystack = " ".join(
            [
                job.get("title", ""),
                job.get("company", ""),
                job.get("description", ""),
                " ".join(job.get("tags") or []),
            ]
        ).lower()

        if query_terms and not any(term in haystack for term in query_terms):
            continue

        if location:
            loc = location.lower()
            job_loc = (job.get("location") or "").lower()
            if loc not in job_loc and not job.get("remote"):
                continue

        if contract_type:
            ct = contract_type.lower()
            if ct == "internship":
                if "intern" not in haystack:
                    continue
            elif ct not in haystack and ct not in (job.get("contract_type") or "").lower():
                continue

        if remote is True and not job.get("remote"):
            loc = (job.get("location") or "").lower()
            if "remote" not in loc:
                continue

        filtered.append(job)

    return filtered
