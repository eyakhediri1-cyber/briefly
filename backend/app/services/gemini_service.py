"""
Gemini Service — Wrapper for Google Gemini / Vertex AI API calls.
Requires valid GCP credentials. No mock or synthetic responses.
"""

import json
import logging
import time
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class GeminiAPIError(Exception):
    """Raised when Gemini API is unavailable or returns an error."""


class GeminiService:
    """Service for making Gemini LLM API calls via Vertex AI."""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    def _endpoint(self) -> str:
        return (
            f"https://{settings.VERTEX_AI_LOCATION}-aiplatform.googleapis.com/v1/"
            f"projects/{settings.GOOGLE_CLOUD_PROJECT}/locations/{settings.VERTEX_AI_LOCATION}/"
            f"publishers/google/models/{settings.GEMINI_MODEL}:generateContent"
        )

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def _get_auth_token(self) -> str:
        if not settings.gcp_enabled:
            raise GeminiAPIError(
                "Vertex AI / Gemini is not configured. Set GOOGLE_CLOUD_PROJECT to a valid GCP project."
            )
        # Try explicit service account file first (recommended)
        try:
            import os
            from google.oauth2 import service_account

            cred_path = settings.GOOGLE_APPLICATION_CREDENTIALS or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
            if cred_path:
                logger.info("Gemini auth: attempting service account file at %s", cred_path)
                creds = service_account.Credentials.from_service_account_file(
                    cred_path, scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
                # Use requests transport to refresh token
                import google.auth.transport.requests as tr
                req = tr.Request()
                creds.refresh(req)
                logger.info("Gemini auth: using service account file authentication")
                return creds.token
        except Exception as e:
            logger.warning("Gemini auth: service account file auth failed: %s", e)

        # Fallback to default credentials (metadata server) with retries/backoff
        try:
            import google.auth
            import google.auth.transport.requests

            max_retries = 3
            backoff = 1.0
            last_err = None
            for attempt in range(1, max_retries + 1):
                try:
                    credentials, _ = google.auth.default(
                        scopes=["https://www.googleapis.com/auth/cloud-platform"]
                    )
                    auth_req = google.auth.transport.requests.Request()
                    credentials.refresh(auth_req)
                    logger.info("Gemini auth: using default credentials (attempt %d)", attempt)
                    return credentials.token
                except Exception as e:
                    last_err = e
                    logger.warning("Gemini auth attempt %d failed: %s", attempt, e)
                    if attempt < max_retries:
                        await __import__('asyncio').sleep(backoff)
                        backoff *= 2

            # if we reached here, all attempts failed
            raise last_err
        except Exception as e:
            raise GeminiAPIError(f"Failed to authenticate with Google Cloud: {e}") from e

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.2,
        timeout: float = 60.0,
    ) -> str:
        """Generate text from Gemini. Raises GeminiAPIError on failure or timeout."""
        if not settings.gcp_enabled:
            logger.warning("Gemini: GCP not configured, returning empty response")
            return ""
        
        started = time.monotonic()
        token = await self._get_auth_token()
        client = await self._get_client()

        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": system_prompt}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I will follow these instructions."}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 2048,
            },
        }

        logger.info("Gemini API call start: model=%s prompt_len=%d", settings.GEMINI_MODEL, len(prompt))
        try:
            import asyncio
            response = await asyncio.wait_for(
                client.post(
                    self._endpoint(),
                    json=payload,
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError as e:
            elapsed = time.monotonic() - started
            logger.warning("Gemini API timed out after %.1fs (limit=%ss)", elapsed, timeout)
            raise GeminiAPIError(f"Gemini timed out after {timeout}s") from e

        elapsed = time.monotonic() - started
        if elapsed > settings.CV_PARSE_GEMINI_WARN_SECONDS:
            logger.warning("Gemini API slow: %.1fs (>%ss)", elapsed, settings.CV_PARSE_GEMINI_WARN_SECONDS)

        response.raise_for_status()
        result = response.json()
        text = result["candidates"][0]["content"]["parts"][0]["text"]
        logger.info("Gemini API done in %.1fs — %d chars", elapsed, len(text))
        return text.strip()

    async def generate_json(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.1,
        timeout: float = 60.0,
    ) -> dict:
        """Generate and parse a JSON response from Gemini."""
        raw = await self.generate(prompt, system_prompt, temperature, timeout=timeout)

        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Gemini JSON: %s", cleaned[:200])
            retry_prompt = f"Return ONLY valid JSON, no commentary:\n{prompt}"
            raw2 = await self.generate(retry_prompt, system_prompt, 0.0, timeout=timeout)
            cleaned2 = raw2.strip().strip("`").strip()
            if cleaned2.startswith("json"):
                cleaned2 = cleaned2[4:].strip()
            try:
                return json.loads(cleaned2)
            except json.JSONDecodeError as e2:
                raise GeminiAPIError(f"Gemini returned invalid JSON: {e2}") from e2

    async def close(self):
        if self._client:
            await self._client.aclose()


gemini_service = GeminiService()
