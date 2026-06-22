"""
Agent 1 — Profile Parser (fast path)
Upload → extract text → parse essentials → show summary.
Embeddings and full file storage deferred for speed.
"""

import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime
from typing import Optional

from app.config import settings
from app.middleware.error_handler import CVParsingError
from app.schemas.cv import CVParsedProfile
from app.services.gemini_service import GeminiAPIError, gemini_service
from app.services.redis_service import redis_service
from app.utils.agent_logger import log_agent_start, log_agent_complete
from app.utils.cv_text_parser import extract_basic_profile

logger = logging.getLogger(__name__)

# Essential fields only — smaller prompt, faster Gemini response
CV_PARSER_ESSENTIAL_PROMPT = """Extract essential CV data as JSON with this schema:
{
  "full_name": "string",
  "email": "string or null",
  "phone": "string or null",
  "location": "string or null",
  "skills": {"technical": [], "frameworks": [], "tools": [], "soft": []},
  "experience": [{"title": "", "company": "", "start_date": "", "end_date": "", "description": "", "technologies": []}],
  "projects": [{"name": "", "description": "", "technologies": [], "achievements": []}]
}
Return ONLY valid JSON. Keep descriptions under 120 chars each."""


class ProfileParserAgent:
    """Agent 1: Fast CV parsing — cache, timeout, basic fallback."""

    def _cache_key(self, content_hash: str) -> str:
        return f"cv_parse:{content_hash}"

    async def run(self, file_content: bytes, filename: str, user_id: str) -> dict:
        started = time.monotonic()
        content_hash = hashlib.sha256(file_content).hexdigest()
        log_agent_start("CV Parser", f"user={user_id} file={filename}")
        logger.info("[CV Upload] Parsing started for user=%s file=%s hash=%s", user_id, filename, content_hash[:12])

        # Cache hit — same file uploaded again
        cached = await redis_service.get_json(self._cache_key(content_hash))
        if cached and cached.get("structured_data"):
            elapsed_ms = int((time.monotonic() - started) * 1000)
            logger.info("[CV Upload] Cache HIT — returning parsed CV in %dms", elapsed_ms)
            log_agent_complete("CV Parser", f"cache hit ({elapsed_ms}ms)")
            return {
                "user_id": user_id,
                "raw_text": cached.get("raw_text", ""),
                "structured_data": cached["structured_data"],
                "embedding_index_path": "",
                "file_path": "",
                "parsed_at": datetime.utcnow().isoformat(),
                "from_cache": True,
            }

        # Step 1: Extract text from PDF
        t0 = time.monotonic()
        logger.info("[CV Upload] Step 1/3: Extracting text from PDF...")
        raw_text = await self._extract_text(file_content, filename)
        extract_ms = int((time.monotonic() - t0) * 1000)
        logger.info("[CV Upload] Step 1 done — %d chars in %dms", len(raw_text), extract_ms)

        if len(raw_text.strip()) < 100:
            raise CVParsingError("CV appears empty or unreadable. Please upload a PDF with readable text content.")

        # Step 2: Structure with Gemini (10s timeout → basic fallback)
        t1 = time.monotonic()
        logger.info("[CV Upload] Step 2/3: Structuring data with Gemini...")
        structured = await self._parse_with_gemini(raw_text)
        parse_ms = int((time.monotonic() - t1) * 1000)
        logger.info("[CV Upload] Step 2 done — structured profile in %dms", parse_ms)

        # Step 3: Skip embeddings on upload (generated during job search if needed)
        embedding_path = ""
        if not settings.SKIP_CV_EMBEDDINGS_ON_UPLOAD:
            logger.info("[CV Upload] Step 3/3: Generating embeddings...")
            embedding_path = await self._generate_embeddings(structured, user_id)
        else:
            logger.info("[CV Upload] Step 3/3: Skipped embeddings (deferred to job search)")

        profile_data = {
            "user_id": user_id,
            "raw_text": raw_text,
            "structured_data": structured,
            "embedding_index_path": embedding_path,
            "file_path": "",
            "parsed_at": datetime.utcnow().isoformat(),
            "from_cache": False,
        }

        await redis_service.set_json(
            self._cache_key(content_hash),
            {"raw_text": raw_text, "structured_data": structured},
            ex=settings.CV_CACHE_TTL_SECONDS,
        )
        await redis_service.set_json(f"cv_profile:{user_id}", profile_data, ex=settings.CV_CACHE_TTL_SECONDS)

        elapsed_ms = int((time.monotonic() - started) * 1000)
        skills_data = structured.get("skills", {})
        skill_total = 0
        if isinstance(skills_data, dict):
            skill_total = len(
                skills_data.get("technical", [])
                + skills_data.get("frameworks", [])
                + skills_data.get("tools", [])
            )
        log_agent_complete("CV Parser", f"{skill_total} skills in {elapsed_ms}ms")
        logger.info("[CV Upload] Complete in %dms — skills=%d exp=%d projects=%d",
                    elapsed_ms, skill_total,
                    len(structured.get("experience", [])),
                    len(structured.get("projects", [])))
        return profile_data

    async def _extract_text(self, file_content: bytes, filename: str) -> str:
        if not filename.lower().endswith(".pdf"):
            try:
                return file_content.decode("utf-8")
            except UnicodeDecodeError:
                return file_content.decode("latin-1")

        try:
            import io
            import pdfplumber

            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                pages_text = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages_text.append(text)
                return "\n\n".join(pages_text)
        except Exception as e:
            logger.error("PDF extraction failed: %s", e)
            raise CVParsingError(f"Failed to extract text from PDF: {str(e)}") from e

    async def _parse_with_gemini(self, raw_text: str) -> dict:
        """Parse essentials via Gemini with timeout; fall back to basic extraction."""
        truncated = raw_text[: settings.CV_GEMINI_MAX_CHARS]
        timeout = settings.CV_PARSE_TIMEOUT_SECONDS

        if not settings.gcp_enabled:
            logger.warning("[CV Upload] Gemini not configured — using basic text extraction")
            return self._normalize_profile(extract_basic_profile(raw_text))

        gemini_started = time.monotonic()
        try:
            result = await gemini_service.generate_json(
                prompt=f"Parse this CV:\n\n{truncated}",
                system_prompt=CV_PARSER_ESSENTIAL_PROMPT,
                temperature=0.1,
                timeout=timeout,
            )
            elapsed = time.monotonic() - gemini_started
            if elapsed > settings.CV_PARSE_GEMINI_WARN_SECONDS:
                logger.warning("[CV Upload] Gemini slow: %.1fs — consider basic fallback next time", elapsed)

            parsed = CVParsedProfile(**self._merge_essential(result))
            return parsed.model_dump()
        except (GeminiAPIError, asyncio.TimeoutError, json.JSONDecodeError) as e:
            elapsed = time.monotonic() - gemini_started
            logger.warning(
                "[CV Upload] Gemini failed/timed out after %.1fs (%s) — using basic extraction",
                elapsed, e,
            )
            return self._normalize_profile(extract_basic_profile(raw_text))
        except Exception as e:
            logger.error("[CV Upload] Gemini error: %s — using basic extraction", e)
            return self._normalize_profile(extract_basic_profile(raw_text))

    def _merge_essential(self, result: dict) -> dict:
        """Ensure full schema with defaults for fields not in essential prompt."""
        skills = result.get("skills") or {}
        if isinstance(skills, list):
            skills = {"technical": skills, "frameworks": [], "tools": [], "soft": []}
        return {
            "full_name": result.get("full_name", ""),
            "email": result.get("email"),
            "phone": result.get("phone"),
            "location": result.get("location"),
            "languages": result.get("languages", []),
            "education": result.get("education", []),
            "experience": result.get("experience", []),
            "projects": result.get("projects", []),
            "skills": {
                "technical": skills.get("technical", []) if isinstance(skills, dict) else [],
                "frameworks": skills.get("frameworks", []) if isinstance(skills, dict) else [],
                "tools": skills.get("tools", []) if isinstance(skills, dict) else [],
                "soft": skills.get("soft", []) if isinstance(skills, dict) else [],
            },
            "certifications": result.get("certifications", []),
        }

    def _normalize_profile(self, data: dict) -> dict:
        """Validate via Pydantic, tolerating partial data."""
        try:
            return CVParsedProfile(**data).model_dump()
        except Exception:
            return CVParsedProfile(
                full_name=data.get("full_name", "Unknown"),
                email=data.get("email"),
                experience=data.get("experience", []),
                projects=data.get("projects", []),
                skills=data.get("skills", {"technical": [], "frameworks": [], "tools": [], "soft": []}),
            ).model_dump()

    async def _generate_embeddings(self, structured: dict, user_id: str) -> str:
        """Deferred — only when SKIP_CV_EMBEDDINGS_ON_UPLOAD is False."""
        import os
        from app.services.embedding_service import embedding_service

        texts_to_embed = []
        skills = structured.get("skills", {})
        all_skills = (
            skills.get("technical", [])
            + skills.get("frameworks", [])
            + skills.get("tools", [])
        )
        if all_skills:
            texts_to_embed.append("Skills: " + ", ".join(all_skills))
        for exp in structured.get("experience", []):
            texts_to_embed.append(
                f"{exp.get('title', '')} at {exp.get('company', '')}: {exp.get('description', '')}"
            )
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
            logger.error("Embedding generation failed: %s", e)
            return ""


profile_parser = ProfileParserAgent()
