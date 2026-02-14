import secrets
import time
from datetime import datetime, timedelta
from typing import Dict

import jwt

from app.settings import settings

# TTL for verification session (5 minutes)
VERIFICATION_TTL_SECONDS = 300
CLAIM_TOKEN_EXPIRY_MINUTES = 5


class NonceStore:
    """One-time nonces for claim (consume on use)."""

    def __init__(self):
        self._store: Dict[str, float] = {}

    def generate(self) -> str:
        nonce = secrets.token_urlsafe(32)
        self._store[nonce] = time.time()
        return nonce

    def validate_and_consume(self, nonce: str) -> bool:
        if nonce not in self._store:
            return False
        del self._store[nonce]
        return True

    def cleanup_expired(self, max_age_seconds: int = 600):
        cutoff = time.time() - max_age_seconds
        expired = [n for n, t in self._store.items() if t < cutoff]
        for n in expired:
            del self._store[n]


class VerifyReplayStore:
    """Tracks nonces already used in verify-human (409 if reused)."""

    def __init__(self):
        self._used: set[str] = set()

    def is_replay(self, nonce: str) -> bool:
        return nonce in self._used

    def mark_used(self, nonce: str) -> None:
        self._used.add(nonce)

    def clear(self) -> None:
        """Reset (e.g. for tests)."""
        self._used.clear()


class VerificationStore:
    """In-memory store: email -> (verification_id, expiry_ts). TTL 5 min."""

    def __init__(self, ttl_seconds: int = VERIFICATION_TTL_SECONDS):
        self._store: Dict[str, tuple[str, float]] = {}
        self._ttl = ttl_seconds

    def set(self, email: str, verification_id: str) -> None:
        expiry = time.time() + self._ttl
        self._store[email.lower()] = (verification_id, expiry)

    def get_valid(self, email: str) -> str | None:
        email = email.lower()
        if email not in self._store:
            return None
        vid, expiry = self._store[email]
        if time.time() > expiry:
            del self._store[email]
            return None
        return vid

    def consume(self, email: str) -> None:
        """Remove verification for this email (one claim per verification)."""
        self._store.pop(email.lower(), None)

    def clear(self) -> None:
        """Reset (e.g. for tests)."""
        self._store.clear()

    def cleanup_expired(self) -> None:
        now = time.time()
        expired = [e for e, (_, ex) in self._store.items() if ex < now]
        for e in expired:
            del self._store[e]


nonce_store = NonceStore()
verify_replay_store = VerifyReplayStore()
verification_store = VerificationStore(ttl_seconds=VERIFICATION_TTL_SECONDS)


def mint_claim_token(okta_user_id: str, nonce: str, amount: int) -> tuple[str, int]:
    """Returns (jwt_string, expires_in_seconds)."""
    exp = datetime.utcnow() + timedelta(minutes=CLAIM_TOKEN_EXPIRY_MINUTES)
    payload = {
        "sub": okta_user_id,
        "nonce": nonce,
        "amount": amount,
        "exp": exp,
        "iat": datetime.utcnow(),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    expires_in_seconds = int((exp - datetime.utcnow()).total_seconds())
    return token, max(0, expires_in_seconds)
