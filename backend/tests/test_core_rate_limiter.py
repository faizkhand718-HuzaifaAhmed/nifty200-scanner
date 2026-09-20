import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.rate_limiter import InMemorySlidingWindowRateLimiter  # noqa: E402


def test_requests_within_limit_are_allowed():
    limiter = InMemorySlidingWindowRateLimiter(requests_per_minute=5, burst=0)
    for i in range(5):
        result = limiter.check("client-1", now=float(i))
        assert result.allowed is True


def test_requests_beyond_limit_are_blocked():
    limiter = InMemorySlidingWindowRateLimiter(requests_per_minute=3, burst=0)
    for i in range(3):
        assert limiter.check("client-1", now=float(i)).allowed is True
    blocked = limiter.check("client-1", now=3.0)
    assert blocked.allowed is False
    assert blocked.remaining == 0
    assert blocked.retry_after_seconds > 0


def test_burst_allows_extra_requests_above_steady_rate():
    limiter = InMemorySlidingWindowRateLimiter(requests_per_minute=3, burst=2)
    for i in range(5):
        assert limiter.check("client-1", now=float(i)).allowed is True
    assert limiter.check("client-1", now=5.0).allowed is False


def test_window_slides_old_requests_expire():
    limiter = InMemorySlidingWindowRateLimiter(requests_per_minute=2, burst=0)
    limiter.check("client-1", now=0.0)
    limiter.check("client-1", now=1.0)
    assert limiter.check("client-1", now=2.0).allowed is False

    result = limiter.check("client-1", now=61.5)
    assert result.allowed is True


def test_different_keys_have_independent_limits():
    limiter = InMemorySlidingWindowRateLimiter(requests_per_minute=1, burst=0)
    assert limiter.check("client-A", now=0.0).allowed is True
    assert limiter.check("client-B", now=0.0).allowed is True
    assert limiter.check("client-A", now=0.1).allowed is False


def test_reset_clears_a_keys_history():
    limiter = InMemorySlidingWindowRateLimiter(requests_per_minute=1, burst=0)
    limiter.check("client-1", now=0.0)
    assert limiter.check("client-1", now=0.1).allowed is False
    limiter.reset("client-1")
    assert limiter.check("client-1", now=0.2).allowed is True


def test_rejects_non_positive_config():
    with pytest.raises(ValueError):
        InMemorySlidingWindowRateLimiter(requests_per_minute=0, burst=1)
    with pytest.raises(ValueError):
        InMemorySlidingWindowRateLimiter(requests_per_minute=1, burst=-1)
