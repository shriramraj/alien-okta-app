"""API endpoint tests using httpx ASGI transport."""
import pytest
from app.security import verify_replay_store, verification_store


@pytest.fixture(autouse=True)
def reset_stores():
    """Reset in-memory stores before each test so tests don't interfere."""
    verify_replay_store.clear()
    verification_store.clear()
    yield


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy"}


def test_healthz_ready_demo_mode(client):
    r = client.get("/healthz/ready")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ready"
    assert data["demo_mode"] is True


def test_verify_human_success(client):
    r = client.post(
        "/api/verify-human",
        json={
            "email": "test@example.com",
            "attestation": "I am a human proof string",
            "nonce": "nonce-verify-1",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["human_verified"] is True
    assert data["verification_id"]
    assert data.get("expires_in_seconds") == 300


def test_verify_human_attestation_too_short(client):
    r = client.post(
        "/api/verify-human",
        json={
            "email": "test@example.com",
            "attestation": "short",
            "nonce": "nonce-short",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["human_verified"] is False
    assert data["reason"] == "attestation_too_short"


def test_verify_human_nonce_replay(client):
    payload = {
        "email": "test@example.com",
        "attestation": "I am a human proof string",
        "nonce": "nonce-replay",
    }
    r1 = client.post("/api/verify-human", json=payload)
    assert r1.status_code == 200
    r2 = client.post("/api/verify-human", json=payload)
    assert r2.status_code == 409
    assert r2.json().get("detail", {}).get("reason") == "nonce_reused"


def test_eligibility_demo_allowlist(client):
    r = client.post(
        "/api/eligibility",
        json={"email": "test@example.com", "nonce": "any"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["eligible"] is True
    assert data["email"] == "test@example.com"
    assert "okta_user_id" in data


def test_eligibility_not_in_allowlist(client):
    r = client.post(
        "/api/eligibility",
        json={"email": "not-in-list@example.com", "nonce": "any"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["eligible"] is False


def test_claim_without_verify_returns_403(client):
    r = client.post(
        "/api/claim",
        json={"email": "test@example.com", "nonce": "any", "amount": 100},
    )
    assert r.status_code == 403
    assert r.json().get("detail", {}).get("reason") == "human_not_verified"


def test_full_flow_verify_eligibility_claim(client):
    email = "test@example.com"
    nonce = "nonce-full-flow"
    # 1. Verify
    rv = client.post(
        "/api/verify-human",
        json={
            "email": email,
            "attestation": "I am a human proof string",
            "nonce": nonce,
        },
    )
    assert rv.status_code == 200
    assert rv.json()["human_verified"] is True
    # 2. Eligibility
    re = client.post("/api/eligibility", json={"email": email, "nonce": "any"})
    assert re.status_code == 200
    assert re.json()["eligible"] is True
    # 3. Claim
    rc = client.post("/api/claim", json={"email": email, "nonce": "any", "amount": 50})
    assert rc.status_code == 200
    data = rc.json()
    assert "claim_token" in data
    assert data["okta_user_id"]
    assert data["expires_in_seconds"] > 0
    # 4. Second claim with same verification should fail (one claim per verification)
    rc2 = client.post("/api/claim", json={"email": email, "nonce": "other", "amount": 25})
    assert rc2.status_code == 403
    assert rc2.json().get("detail", {}).get("reason") == "human_not_verified"


def test_claim_invalid_amount(client):
    # Verify first
    client.post(
        "/api/verify-human",
        json={
            "email": "test@example.com",
            "attestation": "I am a human proof string",
            "nonce": "nonce-amount",
        },
    )
    r = client.post(
        "/api/claim",
        json={"email": "test@example.com", "nonce": "any", "amount": 0},
    )
    assert r.status_code == 422  # Pydantic validation (ge=1)
