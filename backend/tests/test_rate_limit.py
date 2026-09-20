import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.market_data.exceptions import ProviderAPIError, ProviderRateLimitError  # noqa: E402
from app.market_data.rate_limit import TokenBucketRateLimiter, retry_with_backoff  # noqa: E402


def test_rate_limiter_allows_up_to_max_calls():
    limiter = TokenBucketRateLimiter(max_calls=3, per_seconds=60)
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is False  # exhausted


def test_rate_limiter_raises_when_exhausted():
    limiter = TokenBucketRateLimiter(max_calls=1, per_seconds=60)
    limiter.acquire_or_raise()
    with pytest.raises(ProviderRateLimitError):
        limiter.acquire_or_raise()


def test_rate_limiter_rejects_bad_config():
    with pytest.raises(ValueError):
        TokenBucketRateLimiter(max_calls=0, per_seconds=60)


def test_retry_with_backoff_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr("app.market_data.rate_limit.time.sleep", lambda _: None)
    calls = {"count": 0}

    @retry_with_backoff(max_attempts=3, base_delay_seconds=0.01)
    def flaky():
        calls["count"] += 1
        if calls["count"] < 3:
            raise ProviderAPIError("transient")
        return "ok"

    assert flaky() == "ok"
    assert calls["count"] == 3


def test_retry_with_backoff_gives_up_after_max_attempts(monkeypatch):
    monkeypatch.setattr("app.market_data.rate_limit.time.sleep", lambda _: None)

    @retry_with_backoff(max_attempts=2, base_delay_seconds=0.01)
    def always_fails():
        raise ProviderAPIError("permanent")

    with pytest.raises(ProviderAPIError):
        always_fails()


def test_retry_with_backoff_does_not_catch_unrelated_exceptions(monkeypatch):
    monkeypatch.setattr("app.market_data.rate_limit.time.sleep", lambda _: None)

    @retry_with_backoff(max_attempts=3, base_delay_seconds=0.01, retry_on=(ProviderAPIError,))
    def raises_value_error():
        raise ValueError("not retryable by this decorator")

    with pytest.raises(ValueError):
        raises_value_error()
