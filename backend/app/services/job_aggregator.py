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

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.config import settings
from app.schemas.job import RawJobPosting, SearchFilters
from app.services.embedding_service import EmbeddingAPIError, embedding_service
from app.services.integrations import ALL_INTEGRATIONS
from app.services.integrations.base import IntegrationResult, JobSourceIntegration, SearchParams
from app.services.redis_service import redis_service
from app.utils.job_normalizer import dedupe_key, filter_jobs, to_raw_job_posting

logger = logging.getLogger(__name__)


class JobAggregatorService:
    """Multi-source job search with caching and semantic ranking (real APIs only)."""

    def __init__(self):
        self._integrations: List[JobSourceIntegration] = [
            cls() for cls in ALL_INTEGRATIONS
        ]

    def _integrations_for_search(self) -> List[JobSourceIntegration]:
        """Return only explicitly enabled integrations."""
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
        """
        Aggregate jobs from enabled platforms. Returns empty list if no APIs return data.
        """
        started = time.monotonic()
        cache_key = self._cache_key(queries, filters)
        cached = await redis_service.get_json(cache_key)
        if cached is not None and "jobs" in cached:
            logger.info("Job aggregator: cache hit for %s (%d jobs)", cache_key, len(cached["jobs"]))
            postings = [RawJobPosting(**j) for j in cached["jobs"]]
            meta = cached.get("meta", {"from_cache": True})
            meta["cache_hit"] = True
            return postings, meta

        all_normalized: List[dict] = []
        source_stats: Dict[str, dict] = {}
        integrations = self._integrations_for_search()

        if not integrations:
            logger.error("No job sources enabled. Set ENABLED_JOB_SOURCES in .env")
            return [], {"error": "No job sources configured", "sources": {}}

        print(
            f"[Brieflyy] Job Aggregator querying {len(integrations)} sources: "
            f"{[i.name for i in integrations]}",
            flush=True,
        )

        for query in queries[:3]:
            params = SearchParams(
                query=query,
                location=filters.location,
                contract_type=filters.contract_type,
                remote=filters.remote,
                max_results=min(40, filters.max_results),
            )
            results = await self._query_all_sources(integrations, params)
            for result in results:
                stat = source_stats.setdefault(
                    result.source,
                    {"count": 0, "errors": [], "response_times_ms": []},
                )
                stat["count"] += len(result.jobs)
                if result.error:
                    stat["errors"].append(result.error)
                if hasattr(result, "elapsed_ms"):
                    stat["response_times_ms"].append(result.elapsed_ms)
                all_normalized.extend(result.jobs)

        seen = set()
        unique_jobs: List[dict] = []
        for job in all_normalized:
            key = dedupe_key(job)
            if key not in seen and key[0]:
                seen.add(key)
                unique_jobs.append(job)

        primary_query = queries[0] if queries else ""
        unique_jobs = filter_jobs(
            unique_jobs,
            query=primary_query,
            location=filters.location,
            contract_type=filters.contract_type,
            remote=filters.remote,
        )

        ranked_jobs = await self._rank_by_cv_relevance(unique_jobs, cv_profile, primary_query)
        ranked_jobs = ranked_jobs[: filters.max_results]
        postings = [to_raw_job_posting(j) for j in ranked_jobs]

        elapsed_ms = int((time.monotonic() - started) * 1000)
        meta = {
            "from_cache": False,
            "total_raw": len(all_normalized),
            "total_unique": len(unique_jobs),
            "total_returned": len(postings),
            "sources": source_stats,
            "queries_used": queries[:3],
            "elapsed_ms": elapsed_ms,
        }

        await redis_service.set_json(
            cache_key,
            {"jobs": [p.model_dump(mode="json") for p in postings], "meta": meta},
            ex=settings.JOB_CACHE_TTL_SECONDS,
        )

        print(
            f"[Brieflyy] Job Aggregator complete — {len(postings)} real jobs "
            f"in {elapsed_ms}ms from {len(source_stats)} sources",
            flush=True,
        )
        for source, stat in source_stats.items():
            times = stat.get("response_times_ms", [])
            avg_ms = int(sum(times) / len(times)) if times else 0
            logger.info(
                "Source %s: %d jobs, errors=%d, avg_response_ms=%d",
                source, stat["count"], len(stat.get("errors", [])), avg_ms,
            )

        return postings, meta

    async def _query_all_sources(
        self,
        integrations: List[JobSourceIntegration],
        params: SearchParams,
    ) -> List[IntegrationResult]:
        async def _safe_search(integration: JobSourceIntegration) -> IntegrationResult:
            t0 = time.monotonic()
            try:
                print(f"[Brieflyy] API → {integration.name} query='{params.query}'", flush=True)
                result = await integration.search(params)
                result.elapsed_ms = int((time.monotonic() - t0) * 1000)
                print(
                    f"[Brieflyy] API ← {integration.name}: {len(result.jobs)} jobs "
                    f"in {result.elapsed_ms}ms"
                    + (f" ERROR: {result.error}" if result.error else ""),
                    flush=True,
                )
                return result
            except Exception as e:
                elapsed_ms = int((time.monotonic() - t0) * 1000)
                logger.error("%s integration raised after %dms: %s", integration.name, elapsed_ms, e)
                result = IntegrationResult(source=integration.name, jobs=[], error=str(e))
                result.elapsed_ms = elapsed_ms
                return result

        return list(await asyncio.gather(*[_safe_search(i) for i in integrations]))

    async def _rank_by_cv_relevance(
        self,
        jobs: List[dict],
        cv_profile: Optional[dict],
        query: str,
    ) -> List[dict]:
        if not jobs:
            return jobs

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
            logger.warning("Semantic ranking skipped (embeddings unavailable): %s", e)
        except Exception as e:
            logger.warning("Semantic ranking failed, keeping API order: %s", e)

        return jobs

    async def close(self) -> None:
        from app.services.integrations.http_client import close_http_client
        await close_http_client()
        for integration in self._integrations:
            await integration.close()


job_aggregator = JobAggregatorService()
