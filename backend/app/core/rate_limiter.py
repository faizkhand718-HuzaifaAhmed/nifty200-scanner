"""
API rate limiting for THIS application's own endpoints - distinct from
Phase 3's provider-side outbound rate limiting (app/market_data/rate_limit.py),
which protects calls OUT to a market-data provider. This protects calls
IN to this app's API.

In-memory sliding-window implementation, single-process only. This is
the correct choice for a single-instance deployment; if you run multiple
backend instances behind a load balancer, each instance would enforce
its own independent limit (e.g. 4 instances effectively allow 4x the
configured rate). For multi-instance production, replace the storage
layer with Redis (INCR + EXPIRE, or a Redis-backed sliding window) behind
the same RateLimiter interface - the interface is deliberately storage-
agnostic to make that swap a single-class change, not a rewrite.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: float = 0.0


class InMemorySlidingWindowRateLimiter:
    def __init__(self, requests_per_minute: int, burst: int):
        if requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive")
        if burst < 0:
            raise ValueError("burst must be non-negative")
        self.requests_per_minute = requests_per_minute
        self.burst = burst
        self._window_seconds = 60.0
        self._history: Dict[str, Deque[float]] = {}

    def check(self, key: str, now: float) -> RateLimitResult:
        """`now` is an explicit parameter (never time.time() read
        internally) for the same testability reason every stateful
        engine in this codebase takes an explicit clock - see
        tests/test_rate_limiter.py."""
        history = self._history.setdefault(key, deque())

        cutoff = now - self._window_seconds
        while history and history[0] < cutoff:
            history.popleft()

        limit = self.requests_per_minute + self.burst
        if len(history) >= limit:
            oldest = history[0]
            retry_after = max(0.0, oldest + self._window_seconds - now)
            return RateLimitResult(allowed=False, remaining=0, retry_after_seconds=retry_after)

        history.append(now)
        return RateLimitResult(allowed=True, remaining=limit - len(history))

    def reset(self, key: str) -> None:
        self._history.pop(key, None)
