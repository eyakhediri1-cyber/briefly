"""Test REST API endpoints."""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_endpoint():
    """Verify that health check returns 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "brieflyy-api"}

def test_auth_routes_protected():
    """Verify protected routes return 401 Unauthorized without token."""
    response = client.get("/cv/profile")
    assert response.status_code == 401
    
    response = client.post("/search/start", json={"target_role": "Software Engineer"})
    assert response.status_code == 401
