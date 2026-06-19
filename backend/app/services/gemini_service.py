"""
Gemini Service — Wrapper for Google Gemini / Vertex AI API calls.
Requires valid GCP credentials. No mock or synthetic responses.
"""

import json
import logging
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
        try:
            import google.auth
            import google.auth.transport.requests

            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            auth_req = google.auth.transport.requests.Request()
            credentials.refresh(auth_req)
            return credentials.token
        except Exception as e:
            raise GeminiAPIError(f"Failed to authenticate with Google Cloud: {e}") from e

    async def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.2) -> str:
        """Generate text from Gemini. Raises GeminiAPIError on failure."""
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
                "maxOutputTokens": 4096,
            },
        }

        logger.info("Gemini API call: model=%s, prompt_len=%d", settings.GEMINI_MODEL, len(prompt))
        response = await client.post(
            self._endpoint(),
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        response.raise_for_status()
        result = response.json()
        text = result["candidates"][0]["content"]["parts"][0]["text"]
        logger.info("Gemini API response: %d chars", len(text))
        return text.strip()

    async def generate_json(self, prompt: str, system_prompt: str = "", temperature: float = 0.1) -> dict:
        """Generate and parse a JSON response from Gemini."""
        raw = await self.generate(prompt, system_prompt, temperature)

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
            raw2 = await self.generate(retry_prompt, system_prompt, 0.0)
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
