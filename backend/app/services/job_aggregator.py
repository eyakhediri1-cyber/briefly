"""
Job Aggregator — queries real job platform APIs only.
No synthetic data, no mock fallbacks. Empty results when APIs return nothing.
"""

import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.schemas.job import RawJobPosting, SearchFilters
from app.services.embedding_service import EmbeddingAPIError, embedding_service
from app.services.integrations import ALL_INTEGRATIONS
from app.services.integrations.base import IntegrationResult, JobSourceIntegration, SearchParams
from app.services.redis_service import redis_service
from app.utils.job_normalizer import dedupe_key, filter_jobs_with_fallback, to_raw_job_posting

logger = logging.getLogger(__name__)


class JobAggregatorService:
    """Multi-source job search with caching — real APIs only, target <10s."""

    def __init__(self):
        self._integrations: List[JobSourceIntegration] = [
            cls() for cls in ALL_INTEGRATIONS
        ]
        # Simple in-memory circuit breaker state: failure counts per integration
        self._failure_counts: dict = {}
        self._failure_window_seconds = 60
        self._failure_threshold = 3

    def _integrations_for_search(self) -> List[JobSourceIntegration]:
        enabled_names = settings.enabled_job_sources_set
        return [i for i in self._integrations if i.name in enabled_names]

    def _cache_key(self, queries: List[str], filters: SearchFilters) -> str:
        payload = {
            "queries": sorted(queries),
            "location": filters.location,
            "contract_type": filters.contract_type,
            "remote": filters.remote,
            "max_results": filters.max_results,
            "sources": sorted(settings.enabled_job_sources_list),
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
        return f"job_agg:{digest}"

    async def search(
        self,
        queries: List[str],
        filters: SearchFilters,
        cv_profile: Optional[dict] = None,
    ) -> Tuple[List[RawJobPosting], Dict[str, Any]]:
        """Aggregate jobs from enabled platforms.

        Note: do not wrap the inner search in an outer asyncio.wait_for() which
        would abort the whole operation and return an empty result on timeout.
        Per-source timeouts and a bounded global collection loop provide
        partial results when slow sources fail to return in time.
        """
        try:
            return await self._search_inner(queries, filters, cv_profile)
        except Exception as e:
            # Defensive fallback: surface error but avoid returning a silent empty list
            logger.exception("Job search failed: %s", e)
            return [], {"error": str(e), "api_failures": [str(e)], "sources": {}, "elapsed_ms": 0}

    async def _search_inner(
        self,
        queries: List[str],
        filters: SearchFilters,
        cv_profile: Optional[dict],
    ) -> Tuple[List[RawJobPosting], Dict[str, Any]]:
        started = time.monotonic()
        cache_key = self._cache_key(queries, filters)
        cached = await redis_service.get_json(cache_key)
        if cached is not None and "jobs" in cached:
            logger.info("Job aggregator: cache hit (%d jobs)", len(cached["jobs"]))
            postings = [RawJobPosting(**j) for j in cached["jobs"]]
            meta = cached.get("meta", {"from_cache": True})
            meta["cache_hit"] = True
            return postings, meta

        integrations = self._integrations_for_search()
        if not integrations:
            logger.error("No job sources enabled. Set ENABLED_JOB_SOURCES in .env")
            return [], {"error": "No job sources configured", "sources": {}, "api_failures": ["config: no sources enabled"]}

        print(f"[Brieflyy] Querying {len(integrations)} sources in parallel: {[i.name for i in integrations]}", flush=True)

        # Fire ALL source×query requests in parallel (feed cache makes repeat fetches instant)
        search_queries = queries[:3]
        tasks = []
        task_labels: Dict[asyncio.Task, tuple] = {}
        # Per-source timeout (seconds) — keep individual sources quick while allowing
        # a slightly longer global wait below. Ensure per-source timeout is
        # strictly smaller than the global deadline so task exceptions can be
        # diagnosed (rather than all tasks hitting the global deadline at once).
        global_timeout = settings.JOB_SEARCH_TIMEOUT_SECONDS or 20
        per_source_default = settings.JOB_API_TIMEOUT_PER_SOURCE or 10
        # leave 2s headroom for collection/processing; clamp to at least 1s
        per_source_timeout = min(per_source_default, max(1, global_timeout - 2))
        created_tasks: List[asyncio.Task] = []
        for query in search_queries:
            params = SearchParams(
                query=query,
                location=filters.location,
                contract_type=filters.contract_type,
                remote=filters.remote,
                max_results=min(40, filters.max_results),
            )
            for integration in integrations:
                # create a task that will be bounded by per-source timeout
                coro = asyncio.wait_for(self._query_source(integration, params), timeout=per_source_timeout)
                t = asyncio.create_task(coro)
                created_tasks.append(t)
                task_labels[t] = (integration.name, query)

        # Collect task results as they arrive (streaming). Respect a global
        # deadline but don't fail hard if the deadline is reached — return
        # partial results instead.
        pending = set(created_tasks)
        done = set()
        global_deadline = time.monotonic() + (settings.JOB_SEARCH_TIMEOUT_SECONDS or 20)

        logger.info(
            "JobAggregator: launched %d tasks (per_source_timeout=%ss, global_deadline=%ss)",
            len(created_tasks), per_source_timeout, global_timeout,
        )

        while pending and time.monotonic() < global_deadline:
            timeout = max(0.1, min(1.0, global_deadline - time.monotonic()))
            d, pending = await asyncio.wait(pending, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
            if not d:
                # nothing completed within the short wait — loop and check deadline
                continue
            done.update(d)

        all_normalized: List[dict] = []
        source_stats: Dict[str, dict] = {}
        api_failures: List[str] = []

        # Process completed tasks (may include per-source timeouts as exceptions)
        for t in done:
            source_name, query = task_labels.get(t, ("unknown", ""))
            try:
                result: IntegrationResult = t.result()
            except asyncio.CancelledError:
                # Shouldn't normally happen for 'done' set, but handle defensively
                api_failures.append(f"{source_name}: cancelled")
                stat = source_stats.setdefault(
                    source_name, {"count": 0, "jobs_returned": 0, "raw_fetched": 0, "errors": [], "response_times_ms": [], "sample_titles": []}
                )
                stat["errors"].append(f"{query}: cancelled")
                continue
            except Exception as e:
                # Per-source timeout or other error — record and continue
                # asyncio.TimeoutError tends to have an empty str(), so render
                # a clearer message for timeouts for easier debugging.
                if isinstance(e, asyncio.TimeoutError):
                    msg = f"Timeout after {per_source_timeout}s"
                else:
                    msg = f"{type(e).__name__}: {repr(e)}"

                api_failures.append(f"{source_name}: {msg}")
                stat = source_stats.setdefault(
                    source_name, {"count": 0, "jobs_returned": 0, "raw_fetched": 0, "errors": [], "response_times_ms": [], "sample_titles": []}
                )
                stat["errors"].append(f"{query}: {msg}")
                logger.warning("JobAggregator: task for %s query=%s failed: %s", source_name, query, msg)
                logger.debug("Task exception detail for %s: %s", source_name, repr(e), exc_info=True)
                continue

            stat = source_stats.setdefault(
                source_name,
                {"count": 0, "jobs_returned": 0, "raw_fetched": 0, "errors": [], "response_times_ms": [], "sample_titles": []},
            )
            stat["count"] += len(result.jobs)
            stat["jobs_returned"] = max(stat["jobs_returned"], len(result.jobs))
            stat["raw_fetched"] = max(stat.get("raw_fetched", 0), getattr(result, "raw_count", 0))
            if result.error:
                stat["errors"].append(f"{query}: {result.error}")
                api_failures.append(f"{source_name}: {result.error}")
            if result.elapsed_ms:
                stat["response_times_ms"].append(result.elapsed_ms)
            for job in result.jobs[:2]:
                title = job.get("title", "")
                if title and title not in stat["sample_titles"]:
                    stat["sample_titles"].append(title)
            all_normalized.extend(result.jobs)

        logger.info("JobAggregator: collected %d raw jobs from completed tasks", len(all_normalized))

        # Cancel any remaining pending tasks (they exceeded the global deadline)
        for t in list(pending):
            source_name, query = task_labels.get(t, ("unknown", ""))
            try:
                t.cancel()
            except Exception:
                pass
            api_failures.append(f"{source_name}: cancelled/global-timeout")
            stat = source_stats.setdefault(source_name, {"count": 0, "jobs_returned": 0, "raw_fetched": 0, "errors": [], "response_times_ms": [], "sample_titles": []})
            stat["errors"].append(f"{query}: cancelled/global-timeout")

        seen = set()
        unique_jobs: List[dict] = []
        for job in all_normalized:
            key = dedupe_key(job)
            # Only dedupe when we have at least one identifying field (title/company/location)
            if key not in seen and any(key):
                seen.add(key)
                unique_jobs.append(job)
            else:
                # keep jobs with no canonical key but with external_id or url
                if not any(key) and (job.get('external_id') or job.get('url')):
                    uid = (job.get('external_id') or job.get('url'))
                    if uid not in seen:
                        seen.add(uid)
                        unique_jobs.append(job)

        # Do NOT apply strict keyword/location filters here — return whatever
        # jobs the APIs provided and let the downstream fit analyzer score
        # and filter. This avoids returning zero results when one source
        # (e.g. RemoteOK) has many matches but other sources or filters drop
        # everything.
        primary_query = queries[0] if queries else "developer"

        if settings.SKIP_SEMANTIC_RANKING:
            ranked_jobs = unique_jobs
        else:
            ranked_jobs = await self._rank_by_cv_relevance(unique_jobs, cv_profile, primary_query)

        # Do not truncate results here; return all unique jobs provided by
        # the integrations (consumer can request pagination if needed).
        postings = [to_raw_job_posting(j) for j in ranked_jobs]

        elapsed_ms = int((time.monotonic() - started) * 1000)
        meta = {
            "from_cache": False,
            "total_raw": len(all_normalized),
            "total_unique": len(unique_jobs),
            "total_returned": len(postings),
            "sources": source_stats,
            "queries_used": search_queries,
            "filter_mode": "none",
            "api_failures": api_failures,
            "elapsed_ms": elapsed_ms,
        }

        await redis_service.set_json(
            cache_key,
            {"jobs": [p.model_dump(mode="json") for p in postings], "meta": meta},
            ex=settings.JOB_CACHE_TTL_SECONDS,
        )

        print(
            f"[Brieflyy] Job search done — {len(postings)} real jobs in {elapsed_ms}ms "
            f"(failures: {len(api_failures)})",
            flush=True,
        )
        for source, stat in source_stats.items():
            err_msg = stat["errors"][-1] if stat["errors"] else "OK"
            logger.info(
                "API %s: returned %d jobs, raw=%s, status=%s",
                source, stat["jobs_returned"], stat.get("raw_fetched", "?"), err_msg[:80],
            )
            if stat["jobs_returned"] == 0:
                logger.warning("API %s returned 0 jobs — %s", source, err_msg)

        if len(postings) == 0:
            logger.error("ZERO jobs from all APIs. Failures: %s", api_failures or "no jobs returned")

        return postings, meta

    async def _query_source(
        self,
        integration: JobSourceIntegration,
        params: SearchParams,
    ) -> IntegrationResult:
        t0 = time.monotonic()
        name = integration.name

        # Simple circuit breaker: if integration has failed more than threshold
        # within the window, short-circuit and return an error quickly.
        fc = self._failure_counts.get(name, [])
        # prune old entries
        fc = [ts for ts in fc if ts + self._failure_window_seconds > time.time()]
        self._failure_counts[name] = fc
        if len(fc) >= self._failure_threshold:
            msg = f"circuit-open: {name} has {len(fc)} recent failures"
            logger.warning(msg)
            return IntegrationResult(source=name, jobs=[], error=msg)

        # Retry loop with exponential backoff for transient failures/timeouts
        max_retries = 3
        backoff = 1.0
        last_err = None
        for attempt in range(1, max_retries + 1):
            try:
                print(f"[Brieflyy] API → {name} query='{params.query}' (attempt {attempt})", flush=True)
                result = await integration.search(params)
                result.elapsed_ms = int((time.monotonic() - t0) * 1000)
                count = len(result.jobs)
                status = f"ERROR: {result.error}" if result.error else "OK"
                print(f"[Brieflyy] API {name} returned {count} jobs ({status})", flush=True)
                # success -> clear recent failures
                self._failure_counts[name] = []
                return result
            except Exception as e:
                last_err = e
                elapsed_ms = int((time.monotonic() - t0) * 1000)
                logger.error("API %s attempt %d failed after %dms: %s", name, attempt, elapsed_ms, e)
                print(f"[Brieflyy] API {name} FAILED (attempt {attempt}): {e}", flush=True)
                # record failure timestamp
                self._failure_counts.setdefault(name, []).append(time.time())
                if attempt < max_retries:
                    await asyncio.sleep(backoff)
                    backoff *= 2

        # All retries exhausted
        result = IntegrationResult(source=name, jobs=[], error=str(last_err))
        result.elapsed_ms = int((time.monotonic() - t0) * 1000)
        return result

    async def _rank_by_cv_relevance(
        self,
        jobs: List[dict],
        cv_profile: Optional[dict],
        query: str,
    ) -> List[dict]:
        if not jobs:
            return jobs

        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity

        query_text = query
        if cv_profile:
            structured = cv_profile.get("structured_data", cv_profile)
            skills = structured.get("skills", {})
            skill_list = []
            if isinstance(skills, dict):
                for cat in ("technical", "frameworks", "tools"):
                    skill_list.extend(skills.get(cat, []))
            elif isinstance(skills, list):
                skill_list = skills
            if skill_list:
                query_text = f"{query}. Skills: {', '.join(skill_list[:15])}"

        try:
            query_embedding = await embedding_service.embed_text(query_text)
            index_path = (cv_profile or {}).get("embedding_index_path", "")
            if index_path:
                embedding_service.load_faiss_index(index_path)

            for job in jobs:
                job_text = f"{job['title']} at {job['company']}. {job.get('description', '')[:500]}"
                job_embedding = await embedding_service.embed_text(job_text)
                sim = cosine_similarity(
                    np.array(query_embedding).reshape(1, -1),
                    np.array(job_embedding).reshape(1, -1),
                )[0][0]
                job["_relevance_score"] = float(sim)

            jobs.sort(key=lambda j: j.get("_relevance_score", 0), reverse=True)
        except EmbeddingAPIError as e:
            logger.warning("Semantic ranking skipped: %s", e)
        except Exception as e:
            logger.warning("Semantic ranking failed: %s", e)

        return jobs

    async def close(self) -> None:
        from app.services.integrations.http_client import close_http_client
        await close_http_client()
        for integration in self._integrations:
            await integration.close()


job_aggregator = JobAggregatorService()
