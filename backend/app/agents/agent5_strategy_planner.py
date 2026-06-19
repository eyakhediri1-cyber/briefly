"""
Agent 5 — Strategy Planner
Categorizes job postings by fit level, generates personalized action plans,
and produces an executive strategy narrative via Gemini.
"""

import logging
import uuid
from datetime import datetime
from typing import List, Dict

from app.services.gemini_service import gemini_service
from app.utils.agent_logger import log_agent_start, log_agent_complete

logger = logging.getLogger(__name__)

STRATEGY_PROMPT = """You are a career advisor. Based on this student's job search analysis:

QUICK WINS (apply this week): {quick_wins_summary}
STRETCH GOALS (prepare then apply): {stretch_goals_summary}
SKILLS TO DEVELOP: {top_gaps}

Generate a personalized job search strategy in JSON:
{{
  "executive_summary": "3-4 sentences motivating and directing the student",
  "week_1_actions": ["action1", "action2", "action3"],
  "week_2_actions": ["action1", "action2"],
  "month_1_goal": "string",
  "skills_to_upskill": [{{"skill": "React", "reason": "...", "resource_type": "course|project|tutorial"}}],
  "top_recommendation": "One specific posting to apply to first, with brief reasoning"
}}
Be encouraging but honest. Be specific, not generic."""


class StrategyPlannerAgent:
    """Agent 5: Generates personalized job search strategy from fit analyses."""

    async def run(self, fit_analyses: List[dict]) -> dict:
        """
        Generate a complete job search strategy.
        
        Args:
            fit_analyses: List of fit analysis dicts from Agent 4
            
        Returns:
            Strategy dict with categorized jobs and action plan
        """
        log_agent_start("Strategy Planner", f"{len(fit_analyses)} fit analyses")
        logger.info(f"Agent 5: Generating strategy from {len(fit_analyses)} analyses")

        # Step 5.1: Categorize postings
        quick_wins = [f for f in fit_analyses if f.get("fit_category") == "STRONG_FIT"]
        partial_fits = [f for f in fit_analyses if f.get("fit_category") == "PARTIAL_FIT"]
        stretch_goals = [f for f in fit_analyses if f.get("fit_category") == "STRETCH_GOAL"]
        develop_first = [f for f in fit_analyses if f.get("fit_category") == "DEVELOP_FIRST"]

        # Combine partial + stretch for the stretch_goals category
        all_stretch = partial_fits + stretch_goals

        # Step 5.2: Sort by fit percentage DESC
        quick_wins.sort(key=lambda x: x.get("fit_percentage", 0), reverse=True)
        all_stretch.sort(key=lambda x: x.get("fit_percentage", 0), reverse=True)
        develop_first.sort(key=lambda x: x.get("fit_percentage", 0), reverse=True)

        # Limit results
        quick_wins = quick_wins[:5]
        all_stretch = all_stretch[:5]
        develop_first = develop_first[:3]

        # Collect all gaps for upskilling advice
        all_gaps = []
        for analysis in fit_analyses:
            all_gaps.extend(analysis.get("gaps", []))
        # Deduplicate and get top gaps
        gap_counts = {}
        for g in all_gaps:
            gap_counts[g] = gap_counts.get(g, 0) + 1
        top_gaps = sorted(gap_counts.keys(), key=lambda x: gap_counts[x], reverse=True)[:5]

        # Step 5.3: Generate LLM narrative
        narrative = await self._generate_narrative(quick_wins, all_stretch, top_gaps)

        # Build strategy
        strategy = {
            "id": str(uuid.uuid4()),
            "quick_wins": [self._to_job_with_fit(f) for f in quick_wins],
            "stretch_goals": [self._to_job_with_fit(f) for f in all_stretch],
            "develop_first": [self._to_job_with_fit(f) for f in develop_first],
            "executive_summary": narrative.get("executive_summary", "Your job search analysis is complete."),
            "week_1_actions": narrative.get("week_1_actions", ["Review your top matches", "Update your LinkedIn"]),
            "week_2_actions": narrative.get("week_2_actions", ["Follow up on applications"]),
            "month_1_goal": narrative.get("month_1_goal", "Submit 10+ targeted applications"),
            "skills_to_upskill": narrative.get("skills_to_upskill", []),
            "top_recommendation": narrative.get("top_recommendation", ""),
            "generated_at": datetime.utcnow().isoformat(),
        }

        log_agent_complete(
            "Strategy Planner",
            f"{len(quick_wins)} quick wins, {len(all_stretch)} stretch, {len(develop_first)} develop",
        )
        logger.info(f"Agent 5: Strategy generated - {len(quick_wins)} quick wins, "
                     f"{len(all_stretch)} stretch goals, {len(develop_first)} develop first")
        return strategy

    async def _generate_narrative(self, quick_wins: List[dict],
                                   stretch_goals: List[dict],
                                   top_gaps: List[str]) -> dict:
        """Generate strategy narrative using Gemini."""
        try:
            qw_summary = ", ".join(
                f"{j.get('job_title', 'Role')} at {j.get('company', 'Company')} ({j.get('fit_percentage', 0)}%)"
                for j in quick_wins[:3]
            ) or "None found yet"

            sg_summary = ", ".join(
                f"{j.get('job_title', 'Role')} at {j.get('company', 'Company')} ({j.get('fit_percentage', 0)}%)"
                for j in stretch_goals[:3]
            ) or "None found"

            prompt = STRATEGY_PROMPT.format(
                quick_wins_summary=qw_summary,
                stretch_goals_summary=sg_summary,
                top_gaps=", ".join(top_gaps) or "None identified",
            )
            return await gemini_service.generate_json(prompt)
        except Exception as e:
            logger.error(f"Strategy narrative generation failed: {e}")
            return {
                "executive_summary": "Your job search analysis is complete. Review your matches below and start applying to your Quick Wins this week.",
                "week_1_actions": ["Apply to your top 3 Quick Win positions", "Update your LinkedIn profile", "Prepare answers for common interview questions"],
                "week_2_actions": ["Follow up on submitted applications", "Start working on identified skill gaps"],
                "month_1_goal": "Submit 10+ targeted applications and begin one upskilling activity",
                "skills_to_upskill": [{"skill": g, "reason": "Frequently required in target roles", "resource_type": "course"} for g in top_gaps[:3]],
                "top_recommendation": "Start with your highest-scoring Quick Win.",
            }

    def _to_job_with_fit(self, analysis: dict) -> dict:
        """Convert fit analysis to JobWithFit format."""
        strengths = analysis.get("strengths", [])
        gaps = analysis.get("gaps", [])

        return {
            "job_id": analysis.get("job_posting_id", str(uuid.uuid4())),
            "title": analysis.get("job_title", ""),
            "company": analysis.get("company", ""),
            "location": analysis.get("location", ""),
            "contract_type": analysis.get("contract_type", ""),
            "url": analysis.get("url", ""),
            "source": analysis.get("source", ""),
            "fit_percentage": analysis.get("fit_percentage", 0),
            "fit_category": analysis.get("fit_category", ""),
            "top_matched_skills": strengths[:3],
            "top_gaps": gaps[:2],
        }


# Singleton
strategy_planner = StrategyPlannerAgent()
