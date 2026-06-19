"""Tests for job normalizer and aggregator utilities."""

from app.utils.job_normalizer import (
    dedupe_key,
    filter_jobs,
    normalize_job,
    to_raw_job_posting,
)


def test_normalize_job_maps_fields():
    raw = {
        "position": "Backend Engineer",
        "company_name": "Acme",
        "location": "Remote",
        "description": "<p>Build APIs</p>",
        "url": "https://example.com/job",
        "tags": ["python", "fastapi"],
    }
    job = normalize_job(raw, "remoteok")
    assert job["title"] == "Backend Engineer"
    assert job["company"] == "Acme"
    assert job["source"] == "remoteok"
    assert "Build APIs" in job["description"]
    assert "<p>" not in job["description"]


def test_dedupe_key_case_insensitive():
    a = normalize_job({"title": "Dev", "company": "Co", "location": "Paris"}, "x")
    b = normalize_job({"title": "dev", "company": "CO", "location": "paris"}, "y")
    assert dedupe_key(a) == dedupe_key(b)


def test_filter_jobs_by_query():
    jobs = [
        normalize_job({"title": "Python Developer", "company": "A", "description": "Django"}, "a"),
        normalize_job({"title": "Sales Rep", "company": "B", "description": "B2B"}, "b"),
    ]
    filtered = filter_jobs(jobs, query="python developer")
    assert len(filtered) == 1
    assert filtered[0]["title"] == "Python Developer"


def test_filter_internships():
    jobs = [
        normalize_job({"title": "Software Intern", "company": "A", "description": ""}, "a"),
        normalize_job({"title": "Senior Engineer", "company": "B", "description": ""}, "b"),
    ]
    filtered = filter_jobs(jobs, query="", contract_type="internship")
    assert len(filtered) == 1
    assert "Intern" in filtered[0]["title"]


def test_to_raw_job_posting():
    norm = normalize_job(
        {"title": "Role", "company": "Co", "description": "Desc", "location": "Remote"},
        "remotive",
    )
    posting = to_raw_job_posting(norm)
    assert posting.title == "Role"
    assert posting.source == "remotive"
    assert posting.description == "Desc"
