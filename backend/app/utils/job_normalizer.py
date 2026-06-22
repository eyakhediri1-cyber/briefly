"""Normalize job postings from heterogeneous APIs into a standard schema."""

import re
import uuid
from datetime import datetime, timezone
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
    """Parse various datetime inputs and return a naive UTC datetime.

    - If `value` is None or can't be parsed, return current UTC (naive).
    - If `value` is timezone-aware, convert to UTC and strip tzinfo (naive).
    - If `value` is naive, assume it's already UTC and return as-is.
    """
    if not value:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    if isinstance(value, datetime):
        dt = value
    else:
        try:
            # Support ISO strings with Z or offsets
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return datetime.now(timezone.utc).replace(tzinfo=None)

    # If timezone-aware, convert to UTC and drop tzinfo to make it naive
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)

    # Assume naive datetimes are already UTC
    return dt


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


def _query_terms(query: str) -> List[str]:
    """Extract searchable terms; include single broad role words like 'developer'."""
    terms = [t.lower() for t in query.split() if len(t) > 2]
    broad = {"developer", "engineer", "designer", "analyst", "manager", "intern"}
    for word in query.lower().split():
        if word in broad and word not in terms:
            terms.append(word)
    return terms


def _matches_contract_type(haystack: str, contract_type: str, job: Dict[str, Any]) -> bool:
    ct = contract_type.lower()
    if ct == "internship":
        entry_markers = ("intern", "graduate", "junior", "entry", "trainee", "placement", "co-op", "coop")
        return any(marker in haystack for marker in entry_markers)
    return ct in haystack or ct in (job.get("contract_type") or "").lower()


def filter_jobs(
    jobs: List[Dict[str, Any]],
    *,
    query: str,
    location: Optional[str] = None,
    contract_type: Optional[str] = None,
    remote: Optional[bool] = None,
    strict: bool = True,
) -> List[Dict[str, Any]]:
    """Client-side filter when APIs lack native filtering."""
    query_terms = _query_terms(query)
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

        if contract_type and strict:
            if not _matches_contract_type(haystack, contract_type, job):
                continue

        if remote is True and not job.get("remote"):
            loc = (job.get("location") or "").lower()
            if "remote" not in loc:
                continue

        filtered.append(job)

    return filtered


def filter_jobs_with_fallback(
    jobs: List[Dict[str, Any]],
    *,
    query: str,
    location: Optional[str] = None,
    contract_type: Optional[str] = None,
    remote: Optional[bool] = None,
) -> tuple[List[Dict[str, Any]], str]:
    """
    Apply filters with progressive relaxation when APIs return data but filters remove everything.
    Returns (filtered_jobs, filter_mode).
    """
    strict = filter_jobs(
        jobs, query=query, location=location, contract_type=contract_type, remote=remote, strict=True
    )
    if strict:
        return strict, "strict"

    if contract_type:
        relaxed_contract = filter_jobs(
            jobs, query=query, location=location, contract_type=None, remote=remote, strict=True
        )
        if relaxed_contract:
            return relaxed_contract, "relaxed_contract_type"

    if query:
        broad_terms = _query_terms(query)
        if len(broad_terms) > 1:
            broad = [
                job
                for job in jobs
                if any(
                    term in " ".join(
                        [
                            job.get("title", ""),
                            job.get("description", ""),
                            " ".join(job.get("tags") or []),
                        ]
                    ).lower()
                    for term in broad_terms[-1:]
                )
            ]
            if broad:
                return broad, "broad_query"

    if jobs:
        return jobs[:80], "unfiltered_fallback"

    return [], "empty"
