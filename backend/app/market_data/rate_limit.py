"""
Utilities real provider adapters use to respect upstream API rate limits and
retry transient failures with backoff. MockDataProvider doesn't need real
limiting, but exposes hooks (see providers/mock_provider.py) to simulate
rate-limit/API-error conditions so the rest of the app can be tested against
failures without needing a live, flaky API.
"""
from __future__ import annotations

import random
import time
from functools import wraps
from typing import Callable, Tuple, Type, TypeVar

from app.market_data.exceptions import ProviderAPIError, ProviderRateLimitError

T = TypeVar("T")


class TokenBucketRateLimiter:
    """Simple token-bucket limiter: `max_calls` calls allowed per
    `per_seconds` window, refilling continuously."""

    def __init__(self, max_calls: int, per_seconds: float):
        if max_calls <= 0 or per_seconds <= 0:
            raise ValueError("max_calls and per_seconds must be positive")
        self.max_calls = max_calls
        self.per_seconds = per_seconds
        self._tokens = float(max_calls)
        self._last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed > 0:
            self._tokens = min(self.max_calls, self._tokens + elapsed * (self.max_calls / self.per_seconds))
            self._last_refill = now

    def try_acquire(self) -> bool:
        self._refill()
        if self._tokens >= 1:
            self._tokens -= 1
            return True
        return False

    def acquire_or_raise(self) -> None:
        if not self.try_acquire():
            raise ProviderRateLimitError("Rate limit exceeded", retry_after_seconds=self.per_seconds / self.max_calls)


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay_seconds: float = 0.5,
    retry_on: Tuple[Type[BaseException], ...] = (ProviderAPIError,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator: retries the wrapped call up to `max_attempts` times with
    exponential backoff + jitter when it raises one of `retry_on`. Does not
    retry ProviderRateLimitError by default - a rate limit needs the caller
    to actually wait `retry_after_seconds`, not be hammered again quickly."""

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @wraps(fn)
        def wrapper(*args, **kwargs) -> T:
            attempt = 0
            while True:
                try:
                    return fn(*args, **kwargs)
                except retry_on:
                    attempt += 1
                    if attempt >= max_attempts:
                        raise
                    delay = base_delay_seconds * (2 ** (attempt - 1)) + random.uniform(0, 0.1)
                    time.sleep(delay)

        return wrapper

    return decorator
