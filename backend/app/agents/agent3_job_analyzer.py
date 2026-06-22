"""
Agent 3 — Job Analyzer
Extracts structured requirements from raw job postings using Gemini.
Generates skill and summary embeddings for semantic matching.
Processes postings in batches to respect API rate limits.
"""

import asyncio
import json
import logging
import uuid
from typing import List, Dict

from app.schemas.job import RawJobPosting, AnalyzedJobPosting
from app.services.gemini_service import gemini_service
from app.services.embedding_service import embedding_service
from app.utils.agent_logger import log_agent_start, log_agent_complete

logger = logging.getLogger(__name__)

JOB_ANALYSIS_PROMPT = """Analyze this job posting and extract requirements in JSON format:
{{
  "required_skills": ["skill1", "skill2"],
  "nice_to_have_skills": ["skill3"],
  "seniority_level": "junior|mid|senior|internship",
  "experience_years_min": null,
  "soft_skills": ["communication", "teamwork"],
  "ats_keywords": ["keyword1", "keyword2"],
  "role_summary": "One sentence description of the role",
  "main_responsibilities": ["responsibility1", "responsibility2"]
}}
Return ONLY valid JSON.

Job posting:
{description}"""

BATCH_SIZE = 10


class JobAnalyzerAgent:
    """Agent 3: Analyzes job postings to extract structured requirements."""

    async def run(self, raw_postings: List[RawJobPosting]) -> List[AnalyzedJobPosting]:
        """
        Analyze all raw job postings in batches.
        
        Args:
            raw_postings: List of raw job posting data
            
        Returns:
            List of analyzed postings with structured requirements and embeddings
        """
        log_agent_start("Job Analyzer", f"{len(raw_postings)} postings")
        logger.info(f"Agent 3: Analyzing {len(raw_postings)} job postings")
        analyzed = []

        # Process in batches
        for i in range(0, len(raw_postings), BATCH_SIZE):
            batch = raw_postings[i:i + BATCH_SIZE]
            logger.info(f"Agent 3: Processing batch {i // BATCH_SIZE + 1} ({len(batch)} postings)")

            tasks = [self._analyze_single(posting) for posting in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Agent 3: Failed to analyze posting: {result}")
                    continue
                if result:
                    analyzed.append(result)

        log_agent_complete("Job Analyzer", f"{len(analyzed)} analyzed")
        logger.info(f"Agent 3: Successfully analyzed {len(analyzed)} postings")
        return analyzed

    async def _analyze_single(self, posting: RawJobPosting) -> AnalyzedJobPosting:
        """Analyze a single job posting."""
        try:
            # Step 1: Extract requirements via Gemini
            prompt = JOB_ANALYSIS_PROMPT.format(description=posting.description[:3000])
            requirements = await gemini_service.generate_json(prompt)

            # Step 2: Generate embeddings for required skills
            skill_embeddings = {}
            required_skills = requirements.get("required_skills", [])
            for skill in required_skills[:10]:  # Limit to top 10
                emb = await embedding_service.embed_text(skill)
                skill_embeddings[skill] = emb

            # Step 3: Generate summary embedding
            summary_text = f"{posting.title} {requirements.get('role_summary', '')} {' '.join(required_skills)}"
            summary_embedding = await embedding_service.embed_text(summary_text)

            return AnalyzedJobPosting(
                id=uuid.uuid4(),
                raw_posting_id=posting.id,
                title=posting.title,
                company=posting.company,
                location=posting.location,
                contract_type=posting.contract_type,
                description=posting.description,
                url=posting.url,
                source=posting.source,
                required_skills=required_skills,
                nice_to_have_skills=requirements.get("nice_to_have_skills", []),
                seniority_level=requirements.get("seniority_level", "internship"),
                soft_skills=requirements.get("soft_skills", []),
                ats_keywords=requirements.get("ats_keywords", []),
                role_summary=requirements.get("role_summary", ""),
                main_responsibilities=requirements.get("main_responsibilities", []),
                skill_embeddings=skill_embeddings,
                summary_embedding=summary_embedding,
            )

        except Exception as e:
            logger.error(f"Failed to analyze '{posting.title}': {e}")
            # Return a basic analysis without LLM
            return AnalyzedJobPosting(
                id=uuid.uuid4(),
                raw_posting_id=posting.id,
                title=posting.title,
                company=posting.company,
                location=posting.location,
                contract_type=posting.contract_type,
                description=posting.description,
                url=posting.url,
                source=posting.source,
                required_skills=[],
                nice_to_have_skills=[],
                seniority_level="internship",
                role_summary=posting.title,
            )


# Singleton
job_analyzer = JobAnalyzerAgent()
