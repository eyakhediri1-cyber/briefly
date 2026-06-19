"""
Agent 1 — Profile Parser
Extracts structured CV data from PDF files using pdfplumber + Gemini LLM.
Generates semantic embeddings and stores results in PostgreSQL + Redis + FAISS.
"""

import json
import logging
import uuid
import os
from datetime import datetime
from typing import Optional

from app.config import settings
from app.middleware.error_handler import CVParsingError
from app.schemas.cv import CVParsedProfile, CVProfileResponse
from app.services.gemini_service import gemini_service
from app.services.embedding_service import embedding_service
from app.services.redis_service import redis_service
from app.services.gcs_service import gcs_service
from app.utils.agent_logger import log_agent_start, log_agent_complete

logger = logging.getLogger(__name__)

CV_PARSER_SYSTEM_PROMPT = """You are a professional CV parser. Extract structured information from this CV into a JSON object with EXACTLY this schema:
{
  "full_name": "string",
  "email": "string or null",
  "phone": "string or null",
  "location": "string or null",
  "languages": ["language1", "language2"],
  "education": [{"institution": "", "degree": "", "field": "", "start_year": null, "end_year": null}],
  "experience": [{"title": "", "company": "", "start_date": "", "end_date": "", "description": "", "technologies": []}],
  "projects": [{"name": "", "description": "", "technologies": [], "achievements": []}],
  "skills": {"technical": [], "frameworks": [], "tools": [], "soft": []},
  "certifications": [{"name": "", "issuer": "", "year": null}]
}
Return ONLY valid JSON, no markdown, no commentary."""

SIMPLE_EXTRACTION_PROMPT = """Extract the following from this CV text and return as JSON:
- full_name, email, skills (as a list), experience (as a list of job titles)
Return ONLY valid JSON."""


class ProfileParserAgent:
    """Agent 1: Parses CVs from PDF to structured profile data."""

    async def run(self, file_content: bytes, filename: str, user_id: str) -> dict:
        """
        Process a CV file end-to-end.
        
        Args:
            file_content: Raw bytes of the uploaded PDF
            filename: Original filename
            user_id: UUID of the user
            
        Returns:
            Dict with structured profile data
        """
        log_agent_start("CV Parser", f"user {user_id}, file {filename}")
        logger.info(f"Agent 1: Starting CV parsing for user {user_id}")

        # Step 1: Extract raw text from PDF
        raw_text = await self._extract_text(file_content, filename)

        if len(raw_text.strip()) < 100:
            raise CVParsingError("CV appears empty or unreadable. Please upload a PDF with readable text content.")

        # Step 2: Upload original file to storage
        file_path = await gcs_service.upload_file(file_content, filename)

        # Step 3: Send to Gemini for structured extraction
        structured = await self._parse_with_gemini(raw_text)

        # Step 4: Generate embeddings for key sections
        embedding_path = await self._generate_embeddings(structured, user_id)

        # Step 5: Build the profile result
        profile_data = {
            "user_id": user_id,
            "raw_text": raw_text,
            "structured_data": structured,
            "embedding_index_path": embedding_path,
            "file_path": file_path,
            "parsed_at": datetime.utcnow().isoformat(),
        }

        # Step 6: Cache in Redis
        await redis_service.set_json(f"cv_profile:{user_id}", profile_data, ex=86400)

        skills_data = structured.get("skills", {})
        if isinstance(skills_data, dict):
            skill_total = len(
                skills_data.get("technical", [])
                + skills_data.get("frameworks", [])
                + skills_data.get("tools", [])
            )
        else:
            skill_total = len(skills_data) if isinstance(skills_data, list) else 0
        log_agent_complete(
            "CV Parser",
            f"{skill_total} skills, {len(structured.get('experience', []))} experiences",
        )
        logger.info(f"Agent 1: CV parsed successfully for user {user_id}")
        return profile_data

    async def _extract_text(self, file_content: bytes, filename: str) -> str:
        """Extract text from PDF using pdfplumber."""
        if filename.lower().endswith(".pdf"):
            try:
                import pdfplumber
                import io

                with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                    pages_text = []
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            pages_text.append(text)
                    return "\n\n".join(pages_text)
            except Exception as e:
                logger.error(f"PDF extraction failed: {e}")
                raise CVParsingError(f"Failed to extract text from PDF: {str(e)}")
        else:
            # Assume plain text
            try:
                return file_content.decode("utf-8")
            except UnicodeDecodeError:
                return file_content.decode("latin-1")

    async def _parse_with_gemini(self, raw_text: str) -> dict:
        """Send CV text to Gemini for structured extraction."""
        try:
            result = await gemini_service.generate_json(
                prompt=f"Parse this CV:\n\n{raw_text}",
                system_prompt=CV_PARSER_SYSTEM_PROMPT,
                temperature=0.1,
            )
            # Validate using Pydantic
            parsed = CVParsedProfile(**result)
            return parsed.model_dump()
        except json.JSONDecodeError:
            logger.warning("First Gemini parse failed, retrying with simpler prompt")
            try:
                result = await gemini_service.generate_json(
                    prompt=f"{SIMPLE_EXTRACTION_PROMPT}\n\n{raw_text}",
                    temperature=0.0,
                )
                return result
            except Exception as e:
                logger.error(f"All Gemini parsing attempts failed: {e}")
                # Return partial profile from raw text
                return self._extract_partial(raw_text)
        except Exception as e:
            logger.error(f"Gemini parsing error: {e}")
            return self._extract_partial(raw_text)

    def _extract_partial(self, raw_text: str) -> dict:
        """Last resort: extract whatever we can from raw text."""
        lines = raw_text.strip().split("\n")
        return {
            "full_name": lines[0] if lines else "Unknown",
            "email": None,
            "phone": None,
            "location": None,
            "languages": [],
            "education": [],
            "experience": [],
            "projects": [],
            "skills": {"technical": [], "frameworks": [], "tools": [], "soft": []},
            "certifications": [],
        }

    async def _generate_embeddings(self, structured: dict, user_id: str) -> str:
        """Generate and store FAISS embeddings for CV sections."""
        texts_to_embed = []

        # Skills
        skills = structured.get("skills", {})
        all_skills = (
            skills.get("technical", []) +
            skills.get("frameworks", []) +
            skills.get("tools", [])
        )
        if all_skills:
            texts_to_embed.append("Skills: " + ", ".join(all_skills))

        # Experience
        for exp in structured.get("experience", []):
            text = f"{exp.get('title', '')} at {exp.get('company', '')}: {exp.get('description', '')}"
            texts_to_embed.append(text)

        # Projects
        for proj in structured.get("projects", []):
            text = f"Project {proj.get('name', '')}: {proj.get('description', '')}"
            texts_to_embed.append(text)

        # Education
        for edu in structured.get("education", []):
            text = f"{edu.get('degree', '')} in {edu.get('field', '')} from {edu.get('institution', '')}"
            texts_to_embed.append(text)

        if not texts_to_embed:
            return ""

        try:
            embeddings = await embedding_service.embed_texts(texts_to_embed)
            index = embedding_service.create_faiss_index(embeddings)

            index_path = os.path.join(settings.upload_dir, f"faiss_index_{user_id}.bin")
            os.makedirs(settings.upload_dir, exist_ok=True)
            embedding_service.save_faiss_index(index, index_path)

            return index_path
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return ""


# Singleton
profile_parser = ProfileParserAgent()
