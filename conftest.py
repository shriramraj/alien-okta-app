"""Pytest fixtures. Set demo env before importing app so tests don't need real Okta."""
import os

os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("DEMO_ALLOWLIST", "test@example.com,a@b.com")
os.environ.setdefault("JWT_SECRET", "test-secret-min-32-chars-long-for-hs256")

import pytest

# Import after env is set
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """FastAPI TestClient (sync, no server)."""
    with TestClient(app) as c:
        yield c
