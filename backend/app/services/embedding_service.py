"""
Embedding Service — text-embedding-004 via Vertex AI.
Requires valid GCP credentials. No mock embeddings.
"""

import logging
import os
from typing import List, Optional

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 768


class EmbeddingAPIError(Exception):
    """Raised when the embedding API is unavailable."""


class EmbeddingService:
    """Service for generating text embeddings and managing FAISS indices."""

    def __init__(self):
        self._faiss_index = None

    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text string."""
        if not settings.gcp_enabled:
            raise EmbeddingAPIError(
                "Vertex AI embeddings not configured. Set GOOGLE_CLOUD_PROJECT."
            )

        import httpx
        import google.auth
        import google.auth.transport.requests

        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)

        url = (
            f"https://{settings.VERTEX_AI_LOCATION}-aiplatform.googleapis.com/v1/"
            f"projects/{settings.GOOGLE_CLOUD_PROJECT}/locations/{settings.VERTEX_AI_LOCATION}/"
            f"publishers/google/models/{settings.EMBEDDING_MODEL}:predict"
        )

        logger.info("Embedding API call: model=%s, text_len=%d", settings.EMBEDDING_MODEL, len(text))
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                json={"instances": [{"content": text}]},
                headers={
                    "Authorization": f"Bearer {credentials.token}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            result = response.json()
            values = result["predictions"][0]["embeddings"]["values"]
            logger.info("Embedding API response: dim=%d", len(values))
            return values

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        embeddings = []
        for text in texts:
            emb = await self.embed_text(text)
            embeddings.append(emb)
        return embeddings

    def create_faiss_index(self, embeddings: List[List[float]]) -> object:
        import faiss

        dim = len(embeddings[0]) if embeddings else EMBEDDING_DIM
        index = faiss.IndexFlatIP(dim)

        vectors = np.array(embeddings, dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1
        vectors = vectors / norms

        index.add(vectors)
        self._faiss_index = index
        return index

    def save_faiss_index(self, index, path: str):
        import faiss
        os.makedirs(os.path.dirname(path), exist_ok=True)
        faiss.write_index(index, path)

    def load_faiss_index(self, path: str):
        import faiss
        if not path or not os.path.exists(path):
            logger.warning("FAISS index not found at %s", path)
            return None
        self._faiss_index = faiss.read_index(path)
        logger.info("FAISS index loaded from %s (%d vectors)", path, self._faiss_index.ntotal)
        return self._faiss_index

    def search(self, query_embedding: List[float], k: int = 5) -> List[tuple]:
        if self._faiss_index is None:
            return []

        query = np.array([query_embedding], dtype=np.float32)
        query = query / np.linalg.norm(query)

        scores, indices = self._faiss_index.search(query, k)
        return list(zip(indices[0].tolist(), scores[0].tolist()))


embedding_service = EmbeddingService()
