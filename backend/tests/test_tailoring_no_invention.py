"""Verify CV tailoring never invents content."""

from app.agents.validation import validate_no_invention


def test_no_new_skills_invented():
    original_cv = {
        "skills": {"technical": ["React"], "frameworks": [], "tools": [], "soft": []},
        "experience": [],
        "projects": [],
    }
    tailored_cv = {
        "skills": {"technical": ["React", "Python"], "frameworks": [], "tools": [], "soft": []},
        "experience": [],
        "projects": [],
    }

    is_valid, violations = validate_no_invention(original_cv, tailored_cv)

    assert not is_valid
    assert any("NEW SKILLS" in v for v in violations)


def test_rewordings_allowed():
    original_cv = {
        "skills": {"technical": ["React"], "frameworks": [], "tools": [], "soft": []},
        "experience": [{
            "title": "Frontend Developer",
            "company": "TechCorp",
            "description": "Built UI components",
            "technologies": [],
        }],
        "projects": [],
    }
    tailored_cv = {
        "skills": {"technical": ["React"], "frameworks": [], "tools": [], "soft": []},
        "experience": [{
            "title": "Frontend Developer",
            "company": "TechCorp",
            "description": "Architected React component library with reusable patterns",
            "technologies": [],
        }],
        "projects": [],
    }

    is_valid, violations = validate_no_invention(original_cv, tailored_cv)

    assert is_valid
    assert len(violations) == 0


def test_no_new_experiences_invented():
    original_cv = {
        "skills": {"technical": [], "frameworks": [], "tools": [], "soft": []},
        "experience": [{"title": "Intern", "company": "A", "description": "Work"}],
        "projects": [],
    }
    tailored_cv = {
        "skills": {"technical": [], "frameworks": [], "tools": [], "soft": []},
        "experience": [
            {"title": "Intern", "company": "A", "description": "Work"},
            {"title": "Senior Engineer", "company": "B", "description": "Fake role"},
        ],
        "projects": [],
    }

    is_valid, violations = validate_no_invention(original_cv, tailored_cv)

    assert not is_valid
    assert any("NEW EXPERIENCES" in v for v in violations)
