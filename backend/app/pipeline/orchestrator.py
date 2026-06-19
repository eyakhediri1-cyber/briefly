"""
Pipeline Orchestrator — Coordinates the 6 AI agents in sequence.
Runs as a FastAPI background task with status updates stored in PostgreSQL + Redis.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.schemas.job import SearchFilters
from app.services.redis_service import redis_service
from app.utils.agent_logger import log_agent_start, log_agent_complete, log_agent_error

logger = logging.getLogger(__name__)

_STATUS_TO_AGENT = {
    "AGENT_2_RUNNING": "Job Searcher",
    "AGENT_3_RUNNING": "Job Analyzer",
    "AGENT_4_RUNNING": "Fit Reasoning Engine",
    "AGENT_5_RUNNING": "Strategy Planner",
}


async def update_session_status(
    session_id: str,
    status: str,
    progress: int,
    step: str = "",
    jobs_found: Optional[int] = None,
    jobs_analyzed: Optional[int] = None,
):
    """Update pipeline session status in database and cache."""
    step = (step or "")[:100]
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
    logger.info("Pipeline status [%s]: %s (%d%%) — %s", session_id[:8], status, progress, step)


async def _run_pipeline_inner(
    session_id: str,
    cv_profile: dict,
    target_role: str,
    filters: dict,
):
    """Core pipeline logic (wrapped by timeout in run_pipeline)."""
    search_filters = SearchFilters(**filters) if filters else SearchFilters()

    # ─── Agent 2: Job Search ───
    log_agent_start("Job Searcher", f"target role: {target_role}")
    await update_session_status(
        session_id, "AGENT_2_RUNNING", 10, "Searching job boards..."
    )
    raw_jobs = await job_search_agent.run(target_role, cv_profile, search_filters)
    jobs_found = len(raw_jobs)
    log_agent_complete("Job Searcher", f"found {jobs_found} jobs")
    logger.info("Pipeline: Agent 2 response — %d raw jobs", jobs_found)

    if jobs_found == 0:
        await update_session_status(
            session_id,
            "COMPLETED",
            100,
            "No matches found. Try different keywords or locations.",
            jobs_found=0,
            jobs_analyzed=0,
        )
        logger.info("Pipeline: No jobs found from any API source — completed with empty results")
        return

    # Store all discovered jobs in database
    async with async_session_factory() as db:
        for job in raw_jobs:
            db_job = JobPosting(
                id=job.id,
                session_id=uuid.UUID(session_id),
                title=job.title,
                company=job.company,
                location=job.location,
                contract_type=job.contract_type,
                description=job.description,
                url=job.url,
                source=job.source,
                posted_at=job.posted_at,
            )
            db.add(db_job)
        await db.commit()

    # Limit jobs sent to heavy analysis agents (3–5)
    max_jobs = settings.PIPELINE_MAX_JOBS
    jobs_to_analyze = raw_jobs[:max_jobs]
    if jobs_found > max_jobs:
        logger.info(
            "Pipeline: analyzing top %d of %d jobs (PIPELINE_MAX_JOBS)",
            max_jobs,
            jobs_found,
        )

    await update_session_status(
        session_id,
        "AGENT_2_RUNNING",
        20,
        f"Found {jobs_found} jobs — preparing analysis...",
        jobs_found=jobs_found,
    )

    # ─── Agent 3: Job Analyzer ───
    log_agent_start("Job Analyzer", f"{len(jobs_to_analyze)} postings")
    await update_session_status(
        session_id,
        "AGENT_3_RUNNING",
        30,
        f"Analyzing requirements for {len(jobs_to_analyze)} jobs...",
        jobs_found=jobs_found,
    )
    analyzed_jobs = await job_analyzer.run(jobs_to_analyze)
    jobs_analyzed = len(analyzed_jobs)
    log_agent_complete("Job Analyzer", f"analyzed {jobs_analyzed} jobs")
    logger.info("Pipeline: Agent 3 response — %d analyzed jobs", jobs_analyzed)

    async with async_session_factory() as db:
        for aj in analyzed_jobs:
            stmt = (
                update(JobPosting)
                .where(JobPosting.id == aj.raw_posting_id)
                .values(
                    structured_requirements={
                        "required_skills": aj.required_skills,
                        "nice_to_have_skills": aj.nice_to_have_skills,
                        "seniority_level": aj.seniority_level,
                        "ats_keywords": aj.ats_keywords,
                        "role_summary": aj.role_summary,
                    }
                )
            )
            await db.execute(stmt)
        await db.commit()

    # ─── Agent 4: Fit Reasoning ───
    log_agent_start("Fit Reasoning Engine", f"{jobs_analyzed} jobs × CV profile")
    await update_session_status(
        session_id,
        "AGENT_4_RUNNING",
        55,
        f"Computing fit scores for {jobs_analyzed} jobs...",
        jobs_found=jobs_found,
        jobs_analyzed=jobs_analyzed,
    )
    fit_analyses = await fit_engine.run(cv_profile, analyzed_jobs)
    log_agent_complete("Fit Reasoning Engine", f"{len(fit_analyses)} fit scores")
    logger.info("Pipeline: Agent 4 response — %d fit analyses", len(fit_analyses))

    async with async_session_factory() as db:
        for fa in fit_analyses:
            job_posting_id = fa.get("job_posting_id")
            if not job_posting_id:
                continue
            db_fit = FitAnalysis(
                id=uuid.UUID(fa["id"]),
                session_id=uuid.UUID(session_id),
                job_posting_id=uuid.UUID(job_posting_id),
                fit_percentage=fa["fit_percentage"],
                fit_category=fa["fit_category"],
                skill_breakdown=fa.get("skill_breakdown", []),
                strengths=fa.get("strengths", []),
                gaps=fa.get("gaps", []),
                transferable_skills=fa.get("transferable_skills", []),
                overall_reasoning=fa.get("overall_reasoning", ""),
            )
            db.add(db_fit)
        await db.commit()

    # ─── Agent 5: Strategy Planner ───
    log_agent_start("Strategy Planner", f"from {len(fit_analyses)} analyses")
    await update_session_status(
        session_id,
        "AGENT_5_RUNNING",
        80,
        "Building your personalized strategy...",
        jobs_found=jobs_found,
        jobs_analyzed=jobs_analyzed,
    )
    strategy = await strategy_planner.run(fit_analyses)
    strategy["session_id"] = session_id
    strategy["total_jobs_found"] = jobs_found
    strategy["total_jobs_analyzed"] = jobs_analyzed
    log_agent_complete("Strategy Planner", "strategy ready")
    logger.info("Pipeline: Agent 5 strategy — %s", {
        "quick_wins": len(strategy.get("quick_wins", [])),
        "stretch_goals": len(strategy.get("stretch_goals", [])),
        "develop_first": len(strategy.get("develop_first", [])),
    })

    async with async_session_factory() as db:
        db_strategy = StrategyModel(
            id=uuid.UUID(strategy["id"]),
            session_id=uuid.UUID(session_id),
            quick_wins=strategy.get("quick_wins", []),
            stretch_goals=strategy.get("stretch_goals", []),
            develop_first=strategy.get("develop_first", []),
            executive_summary=strategy.get("executive_summary", ""),
            week_1_actions=strategy.get("week_1_actions", []),
            week_2_actions=strategy.get("week_2_actions", []),
            month_1_goal=strategy.get("month_1_goal", ""),
            skills_to_upskill=strategy.get("skills_to_upskill", []),
            top_recommendation=strategy.get("top_recommendation", ""),
        )
        db.add(db_strategy)
        await db.commit()

    await redis_service.set_json(f"strategy:{session_id}", strategy, ex=3600)

    await update_session_status(
        session_id,
        "COMPLETED",
        100,
        f"Done! Analyzed {jobs_analyzed} of {jobs_found} jobs found.",
        jobs_found=jobs_found,
        jobs_analyzed=jobs_analyzed,
    )
    logger.info("Pipeline: Completed for session %s", session_id)


async def run_pipeline(
    session_id: str,
    cv_profile: dict,
    target_role: str,
    filters: dict,
):
    """
    Execute the full agent pipeline as a background task.

    Pipeline: Agent 2 → Agent 3 → Agent 4 → Agent 5
    (Agent 1 runs separately during CV upload, Agent 6 runs on-demand)
    """
    try:
        logger.info("Pipeline: Starting for session %s", session_id)
        await asyncio.wait_for(
            _run_pipeline_inner(session_id, cv_profile, target_role, filters),
            timeout=settings.PIPELINE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        msg = f"Pipeline timed out after {settings.PIPELINE_TIMEOUT_SECONDS}s"
        log_agent_error("Pipeline", msg)
        await update_session_status(session_id, "FAILED", 0, msg)
    except Exception as e:
        log_agent_error("Pipeline", str(e))
        logger.exception("Pipeline failed for session %s", session_id)
        await update_session_status(
            session_id, "FAILED", 0, f"Error: {str(e)[:90]}"
        )
