"""Tests for fast CV text extraction fallback."""

from app.utils.cv_text_parser import extract_basic_profile


def test_extract_basic_profile_finds_email_and_skills():
    text = """Jane Smith
jane@example.com
Skills: Python, FastAPI, Docker, React
Experience
Software Engineer at Acme Corp
Built REST APIs with Python and PostgreSQL.
Projects
Brieflyy - Job search app using FastAPI and Angular
"""
    profile = extract_basic_profile(text)
    assert profile["full_name"] == "Jane Smith"
    assert profile["email"] == "jane@example.com"
    assert "python" in [s.lower() for s in profile["skills"]["technical"]]
    assert len(profile["experience"]) >= 1
    assert len(profile["projects"]) >= 1
