"""Test Agent 4 — Fit Reasoning Engine."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.agent4_fit_engine import fit_engine
from app.schemas.job import AnalyzedJobPosting


@pytest.mark.asyncio
async def test_fit_percentage_computation():
    """Verify that fit percentage and categorization matches expectations."""
    cv_profile = {
        "structured_data": {
            "skills": {
                "technical": ["Python", "FastAPI", "SQL"],
                "frameworks": ["React"],
                "tools": ["Docker"],
            }
        }
    }

    job = AnalyzedJobPosting(
        id=uuid.uuid4(),
        raw_posting_id=uuid.uuid4(),
        title="Python Developer",
        company="TechCorp",
        required_skills=["Python", "FastAPI", "SQL", "Kubernetes"],
        role_summary="Looking for a Python Developer proficient in backend design.",
    )

    mock_embedding = [0.1] * 768

    with patch("app.agents.agent4_fit_engine.embedding_service") as mock_embed:
        mock_embed.embed_text = AsyncMock(return_value=mock_embedding)
        mock_embed.load_faiss_index = lambda path: None
        analyses = await fit_engine.run(cv_profile, [job])

    assert len(analyses) == 1
    analysis = analyses[0]
    assert "fit_percentage" in analysis
    assert "fit_category" in analysis
    assert analysis["fit_percentage"] >= 0
