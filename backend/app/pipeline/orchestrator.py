"""
Pipeline Orchestrator — fast parallel pipeline for job search + fit + CV tailoring.
Agent 5 (strategy) skipped in fast mode. Real APIs only — no mock data.
"""

import asyncio
import time
import logging
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import update, select

from app.config import settings
from app.database import async_session_factory
from app.models.job_search_session import JobSearchSession
from app.models.job_posting import JobPosting
from app.models.fit_analysis import FitAnalysis
from app.models.strategy import Strategy as StrategyModel
from app.agents.agent2_job_search import job_search_agent
from app.agents.agent3_job_analyzer import job_analyzer
from app.agents.agent4_fit_engine import fit_engine
from app.agents.agent5_strategy_planner import strategy_planner
from app.schemas.job import SearchFilters, RawJobPosting
from app.services.tailoring_service import tailor_and_store
from app.services.redis_service import redis_service
from app.utils.agent_logger import log_agent_start, log_agent_complete, log_agent_error
from app.utils.fast_fit import compute_fit_fast, extract_requirements_fast

logger = logging.getLogger(__name__)

_STATUS_TO_AGENT = {
    "AGENT_2_RUNNING": "Job Searcher",
    "AGENT_3_RUNNING": "Job Analyzer",
    "AGENT_4_RUNNING": "Fit Reasoning Engine",
    "AGENT_6_RUNNING": "CV Tailoring Engine",
}


async def update_session_status(
    session_id: str,
    status: str,
    progress: int,
    step: str = "",
    jobs_found: Optional[int] = None,
    jobs_analyzed: Optional[int] = None,
):
    step = (step or "")[:200]
    async with async_session_factory() as db:
        stmt = (
            update(JobSearchSession)
            .where(JobSearchSession.id == uuid.UUID(session_id))
            .values(
                status=status,
                progress_percent=progress,
                current_step=step,
                completed_at=datetime.utcnow() if status == "COMPLETED" else None,
            )
        )
        await db.execute(stmt)
        await db.commit()

    payload = {
        "status": status,
        "progress_percent": progress,
        "current_step": step,
        "current_agent": _STATUS_TO_AGENT.get(status),
        "jobs_found": jobs_found,
        "jobs_analyzed": jobs_analyzed,
    }
    await redis_service.set_json(f"session_status:{session_id}", payload, ex=3600)
    logger.info("Pipeline [%s]: %s (%d%%) — %s", session_id[:8], status, progress, step)


async def _tailor_job(
    db,
    job: JobPosting,
    cv_profile: dict,
    user_id: uuid.UUID,
    cv_profile_id: uuid.UUID,
) -> bool:
    if not job.structured_requirements:
        return False
    job_data = {
        "title": job.title,
        "required_skills": job.structured_requirements.get("required_skills", []),
        "ats_keywords": job.structured_requirements.get("ats_keywords", []),
    }
    cv_data = {
        "structured_data": cv_profile.get("structured_data", cv_profile),
        "raw_text": cv_profile.get("raw_text", ""),
    }
    result = await tailor_and_store(
        db,
        user_id=user_id,
        cv_profile_id=cv_profile_id,
        job_posting_id=job.id,
        cv_data=cv_data,
        job_data=job_data,
    )
    return result is not None


async def _run_pipeline_inner(
    session_id: str,
    cv_profile: dict,
    target_role: str,
    filters: dict,
    user_id: str,
    cv_profile_id: str,
):
    search_filters = SearchFilters(**filters) if filters else SearchFilters()
    if search_filters.max_results < settings.JOB_SEARCH_MIN_RESULTS:
        search_filters.max_results = settings.JOB_SEARCH_MIN_RESULTS

    # ─── Agent 2: Job Search (target <10s) ───
    log_agent_start("Job Searcher", f"target role: {target_role}")
    await update_session_status(session_id, "AGENT_2_RUNNING", 15, "Searching job boards...")

    try:
        raw_jobs = await asyncio.wait_for(
            job_search_agent.run(target_role, cv_profile, search_filters),
            timeout=getattr(settings, 'JOB_SEARCH_TIMEOUT_SECONDS', 20),
        )
    except asyncio.TimeoutError:
        logger.warning("Job search timed out after %ss", getattr(settings, 'JOB_SEARCH_TIMEOUT_SECONDS', 20))
        raw_jobs = []

    jobs_found = len(raw_jobs)
    log_agent_complete("Job Searcher", f"found {jobs_found} jobs")

    if jobs_found == 0:
        msg = "No matches. Try different keywords."
        await update_session_status(session_id, "COMPLETED", 100, msg, jobs_found=0, jobs_analyzed=0)
        logger.warning("Pipeline: zero jobs — no mock fallback")
        return

    max_jobs = settings.PIPELINE_MAX_JOBS
    jobs_to_process = raw_jobs[:max_jobs]

    # Store jobs in DB first
    await update_session_status(
        session_id, "AGENT_3_RUNNING", 35,
        f"Analyzing {len(jobs_to_process)} jobs...",
        jobs_found=jobs_found,
    )

    async with async_session_factory() as db:
        try:
            # Upsert raw jobs
            rows = []
            for job in raw_jobs:
                rows.append({
                    "id": job.id,
                    "session_id": uuid.UUID(session_id),
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "contract_type": job.contract_type,
                    "description": job.description,
                    "url": job.url,
                    "source": job.source,
                    "posted_at": job.posted_at,
                })
            
            if rows:
                from sqlalchemy.dialects.postgresql import insert as pg_insert
                table = JobPosting.__table__
                ins = pg_insert(table).values(rows)
                update_cols = {c.name: ins.excluded[c.name] for c in table.columns if c.name not in ['id']}
                upsert_stmt = ins.on_conflict_do_update(index_elements=["id"], set_=update_cols)
                await db.execute(upsert_stmt)
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to upsert jobs: {e}")
            await db.rollback()

    # ─── Agent 3: Job Analyzer (Deep Analysis) ───
    if not settings.PIPELINE_FAST_MODE:
        logger.info("Orchestrator: Running Deep Analysis (Agent 3)")
        analyzed_jobs = await job_analyzer.run(jobs_to_process)
    else:
        logger.info("Orchestrator: Running Fast Analysis (Agent 3 Fallback)")
        analyzed_jobs = []
        for job in jobs_to_process:
            reqs = extract_requirements_fast(job)
            from app.schemas.job import AnalyzedJobPosting
            analyzed_jobs.append(AnalyzedJobPosting(
                id=uuid.uuid4(),
                raw_posting_id=job.id,
                title=job.title,
                company=job.company,
                location=job.location,
                description=job.description,
                url=job.url,
                source=job.source,
                required_skills=reqs["required_skills"],
                nice_to_have_skills=reqs["nice_to_have_skills"],
                seniority_level=reqs["seniority_level"],
                ats_keywords=reqs["ats_keywords"],
                role_summary=reqs["role_summary"]
            ))

    # Update DB with analyzed requirements
    async with async_session_factory() as db:
        for aj in analyzed_jobs:
            await db.execute(
                update(JobPosting)
                .where(JobPosting.id == aj.raw_posting_id)
                .values(structured_requirements=aj.model_dump(exclude={'id', 'raw_posting_id', 'skill_embeddings', 'summary_embedding'}))
            )
        await db.commit()

    # ─── Agent 4: Fit Reasoning Engine ───
    await update_session_status(session_id, "AGENT_4_RUNNING", 55, "Computing deep fit analysis...")
    
    if not settings.PIPELINE_FAST_MODE:
        logger.info("Orchestrator: Running Deep Fit (Agent 4)")
        fit_analyses = await fit_engine.run(cv_profile, analyzed_jobs)
    else:
        logger.info("Orchestrator: Running Fast Fit (Agent 4 Fallback)")
        fit_analyses = []
        for aj in analyzed_jobs:
            # Need a RawJobPosting for compute_fit_fast
            raw_job = next((j for j in jobs_to_process if j.id == aj.raw_posting_id), None)
            if raw_job:
                fit = compute_fit_fast(cv_profile, raw_job, aj.model_dump())
                fit_analyses.append(fit)

    # Store fit analyses
    async with async_session_factory() as db:
        for fa in fit_analyses:
            db.add(FitAnalysis(
                id=uuid.UUID(fa["id"]),
                session_id=uuid.UUID(session_id),
                job_posting_id=uuid.UUID(fa["job_posting_id"]),
                fit_percentage=fa["fit_percentage"],
                fit_category=fa["fit_category"],
                skill_breakdown=fa.get("skill_breakdown", []),
                strengths=fa.get("strengths", []),
                gaps=fa.get("gaps", []),
                transferable_skills=fa.get("transferable_skills", []),
                overall_reasoning=fa.get("overall_reasoning", ""),
            ))
        await db.commit()

    # ─── Agent 5: Strategy Planner ───
    await update_session_status(session_id, "AGENT_5_RUNNING", 80, "Generating job search strategy...")
    
    if not settings.PIPELINE_FAST_MODE:
        logger.info("Orchestrator: Running Strategy Planner (Agent 5)")
        strategy_data = await strategy_planner.run(fit_analyses)
    else:
        logger.info("Orchestrator: Running Fast Strategy (Agent 5 Fallback)")
        # Fast strategy: categorize all fit analyses into proper groups
        quick_wins = sorted(
            [f for f in fit_analyses if f["fit_category"] == "STRONG_FIT"],
            key=lambda x: x["fit_percentage"], reverse=True
        )
        stretch_goals = sorted(
            [f for f in fit_analyses if f["fit_category"] == "PARTIAL_FIT"],
            key=lambda x: x["fit_percentage"], reverse=True
        )
        develop_first = sorted(
            [f for f in fit_analyses if f["fit_category"] in ("STRETCH_GOAL", "DEVELOP_FIRST")],
            key=lambda x: x["fit_percentage"], reverse=True
        )
        
        # If no strong fits, just show all jobs in stretch goals
        if not quick_wins and not stretch_goals and not develop_first:
            quick_wins = sorted(fit_analyses, key=lambda x: x["fit_percentage"], reverse=True)
        
        strategy_data = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "quick_wins": [strategy_planner._to_job_with_fit(f) for f in quick_wins[:10]],
            "stretch_goals": [strategy_planner._to_job_with_fit(f) for f in stretch_goals[:10]],
            "develop_first": [strategy_planner._to_job_with_fit(f) for f in develop_first[:10]],
            "executive_summary": f"Found {jobs_found} jobs. Top {len(fit_analyses)} ranked by match.",
            "week_1_actions": ["Review top matches", "Apply to quick wins"],
            "week_2_actions": [],
            "month_1_goal": "Submit 10 applications",
            "skills_to_upskill": [],
            "top_recommendation": quick_wins[0]["title"] if quick_wins else (stretch_goals[0]["title"] if stretch_goals else ""),
            "generated_at": datetime.utcnow().isoformat(),
        }

    # Store strategy
    await redis_service.set_json(f"strategy:{session_id}", strategy_data, ex=3600)
    async with async_session_factory() as db:
        db.add(StrategyModel(
            id=uuid.UUID(strategy_data["id"]),
            session_id=uuid.UUID(session_id),
            quick_wins=strategy_data["quick_wins"],
            stretch_goals=strategy_data.get("stretch_goals", []),
            develop_first=strategy_data.get("develop_first", []),
            executive_summary=strategy_data["executive_summary"],
            week_1_actions=strategy_data["week_1_actions"],
            week_2_actions=strategy_data.get("week_2_actions", []),
            month_1_goal=strategy_data.get("month_1_goal", ""),
            skills_to_upskill=strategy_data.get("skills_to_upskill", []),
            top_recommendation=strategy_data.get("top_recommendation", ""),
        ))
        await db.commit()

    jobs_analyzed = len(fit_analyses)

    # ─── Mark as COMPLETED first so frontend can proceed ───
    await update_session_status(
        session_id, "COMPLETED", 100,
        f"Found {jobs_found} jobs — tailoring CVs in background...",
        jobs_found=jobs_found, jobs_analyzed=jobs_analyzed,
    )
    logger.info("Pipeline main tasks complete, frontend can now fetch results")

    # ─── Agent 6: Schedule CV tailoring in background (fire-and-forget) ───
    log_agent_start("CV Tailoring Engine", f"scheduling {jobs_analyzed} jobs in background")

    async def _background_tailoring(jobs_list):
        logger.info("Background tailoring started for session %s (%d jobs)", session_id, len(jobs_list))
        sem_local = asyncio.Semaphore(5)
        tailored_local = 0
        async def _task(job_obj):
            nonlocal tailored_local
            async with sem_local:
                async with async_session_factory() as db:
                    job_result = await db.execute(select(JobPosting).where(JobPosting.id == job_obj.id))
                    job_rec = job_result.scalar_one_or_none()
                    if not job_rec:
                        return
                    try:
                        ok = await _tailor_job(db, job_rec, cv_profile, uuid.UUID(user_id), uuid.UUID(cv_profile_id))
                        if ok:
                            tailored_local += 1
                        await db.commit()
                    except Exception as e:
                        logger.exception("Background tailoring failed for job %s: %s", job_obj.id, e)

        tasks = [asyncio.create_task(_task(j)) for j in jobs_list]
        try:
            await asyncio.gather(*tasks)
        except Exception:
            logger.exception("Background tailoring encountered errors")

        logger.info("Background tailoring complete for session %s: %d tailored", session_id, tailored_local)
        log_agent_complete("CV Tailoring Engine", f"{tailored_local} tailored CVs ready")

    try:
        asyncio.create_task(_background_tailoring(jobs_to_process))
    except Exception:
        logger.exception("Failed to schedule background tailoring")
        log_agent_complete("CV Tailoring Engine", "scheduling failed")


async def run_pipeline(
    session_id: str,
    cv_profile: dict,
    target_role: str,
    filters: dict,
    user_id: str = "",
    cv_profile_id: str = "",
):
    try:
        logger.info("Pipeline: Starting fast mode for session %s", session_id)
        await asyncio.wait_for(
            _run_pipeline_inner(session_id, cv_profile, target_role, filters, user_id, cv_profile_id),
            timeout=settings.PIPELINE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        msg = f"Pipeline timed out after {settings.PIPELINE_TIMEOUT_SECONDS}s"
        log_agent_error("Pipeline", msg)
        await update_session_status(session_id, "FAILED", 0, msg)
    except Exception as e:
        log_agent_error("Pipeline", str(e))
        logger.exception("Pipeline failed for session %s", session_id)
        await update_session_status(session_id, "FAILED", 0, f"Error: {str(e)[:90]}")
