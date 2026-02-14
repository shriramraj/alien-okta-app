"""In-memory per-IP rate limiter. No extra dependencies."""
import time
from collections import defaultdict


class RateLimiter:
    """Sliding window: max `max_requests` per `window_seconds` per key (e.g. IP)."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self._max = max_requests
        self._window = window_seconds
        self._timestamps: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        cutoff = now - self._window
        # keep only timestamps inside the window
        self._timestamps[key] = [t for t in self._timestamps[key] if t > cutoff]
        if len(self._timestamps[key]) >= self._max:
            return False
        self._timestamps[key].append(now)
        return True


# 60 requests per minute per IP
rate_limiter = RateLimiter(max_requests=60, window_seconds=60)
