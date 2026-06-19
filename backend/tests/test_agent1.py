"""Test Agent 1 — Profile Parser Agent."""

import pytest
from unittest.mock import AsyncMock, patch

from app.agents.agent1_profile_parser import profile_parser
from app.middleware.error_handler import CVParsingError

MOCK_PARSED_CV = {
    "full_name": "John Doe",
    "email": "john@example.com",
    "phone": None,
    "location": "Tunis",
    "languages": ["English", "French"],
    "education": [{"institution": "ESPRIT", "degree": "BSc", "field": "CS", "start_year": 2021, "end_year": 2025}],
    "experience": [{"title": "Software Engineer", "company": "Tech Corp", "start_date": "2024-01", "end_date": "Present", "description": "Built APIs", "technologies": ["Python"]}],
    "projects": [{"name": "Brieflyy", "description": "Job search app", "technologies": ["FastAPI"], "achievements": []}],
    "skills": {"technical": ["Python", "FastAPI"], "frameworks": ["Angular"], "tools": ["Docker"], "soft": []},
    "certifications": [],
}


@pytest.mark.asyncio
async def test_empty_cv_raises_error():
    with pytest.raises(CVParsingError):
        await profile_parser.run(b"", "empty.pdf", "test-user-id")


@pytest.mark.asyncio
async def test_text_cv_parsing():
    raw_text = (
        b"John Doe\nSoftware Engineer\nSkills: Python, FastAPI, Docker, Kubernetes, "
        b"AWS, PostgreSQL, Git\nWork Experience: 3 years as a Software Engineer at "
        b"Tech Corp building backend REST APIs and microservices using Python."
    )

    with patch.object(profile_parser, "_parse_with_gemini", new_callable=AsyncMock) as mock_parse:
        mock_parse.return_value = MOCK_PARSED_CV
        with patch.object(profile_parser, "_generate_embeddings", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = ""
            profile = await profile_parser.run(raw_text, "resume.txt", "test-user-id")

    assert profile["user_id"] == "test-user-id"
    assert "John Doe" in profile["raw_text"]
    assert profile["structured_data"]["full_name"] == "John Doe"
