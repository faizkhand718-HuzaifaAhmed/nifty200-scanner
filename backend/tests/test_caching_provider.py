import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.market_data.caching_provider import CachingProvider  # noqa: E402


class FakeInnerProvider:
    def __init__(self):
        self.call_count = 0

    def get_latest_price(self, symbol, exchange):
        self.call_count += 1
        return f"price-for-{symbol}-call-{self.call_count}"

    def get_volume(self, symbol, exchange):
        self.call_count += 1
        return self.call_count

    def get_historical_candles(self, symbol, exchange, timeframe, start, end):
        self.call_count += 1
        return f"candles-call-{self.call_count}"

    def get_intraday_candles(self, symbol, exchange, timeframe, from_time=None):
        self.call_count += 1
        return f"intraday-call-{self.call_count}"


def test_second_call_within_ttl_uses_cache_not_inner_provider():
    inner = FakeInnerProvider()
    clock = iter([0.0, 10.0])
    cache = CachingProvider(inner, live_ttl_seconds=60.0, clock=lambda: next(clock))

    first = cache.get_latest_price("RELIANCE", "NSE")
    second = cache.get_latest_price("RELIANCE", "NSE")

    assert first == second
    assert inner.call_count == 1


def test_call_after_ttl_expires_refetches():
    inner = FakeInnerProvider()
    clock = iter([0.0, 100.0])
    cache = CachingProvider(inner, live_ttl_seconds=60.0, clock=lambda: next(clock))

    first = cache.get_latest_price("RELIANCE", "NSE")
    second = cache.get_latest_price("RELIANCE", "NSE")

    assert first != second
    assert inner.call_count == 2


def test_different_symbols_cached_independently():
    inner = FakeInnerProvider()
    cache = CachingProvider(inner, live_ttl_seconds=60.0, clock=lambda: 0.0)

    cache.get_latest_price("RELIANCE", "NSE")
    cache.get_latest_price("TCS", "NSE")

    assert inner.call_count == 2


def test_historical_candles_use_the_historical_ttl_not_live_ttl():
    inner = FakeInnerProvider()
    clock = iter([0.0, 120.0])
    cache = CachingProvider(inner, live_ttl_seconds=60.0, historical_ttl_seconds=6 * 3600.0, clock=lambda: next(clock))

    import datetime
    first = cache.get_historical_candles("RELIANCE", "NSE", "1d", datetime.date(2026, 1, 1), datetime.date(2026, 1, 28))
    second = cache.get_historical_candles("RELIANCE", "NSE", "1d", datetime.date(2026, 1, 1), datetime.date(2026, 1, 28))

    assert first == second
    assert inner.call_count == 1


def test_a_raised_exception_is_never_cached():
    class FailingProvider:
        def __init__(self):
            self.call_count = 0

        def get_latest_price(self, symbol, exchange):
            self.call_count += 1
            raise RuntimeError("upstream failure")

        def get_volume(self, symbol, exchange):
            raise NotImplementedError

        def get_historical_candles(self, *a, **kw):
            raise NotImplementedError

        def get_intraday_candles(self, *a, **kw):
            raise NotImplementedError

    inner = FailingProvider()
    cache = CachingProvider(inner, clock=lambda: 0.0)

    with pytest.raises(RuntimeError):
        cache.get_latest_price("RELIANCE", "NSE")
    with pytest.raises(RuntimeError):
        cache.get_latest_price("RELIANCE", "NSE")

    assert inner.call_count == 2


def test_cache_age_seconds_reports_correctly():
    inner = FakeInnerProvider()
    clock = iter([0.0, 15.0])
    cache = CachingProvider(inner, clock=lambda: next(clock))

    cache.get_latest_price("RELIANCE", "NSE")
    age = cache.cache_age_seconds(("get_latest_price", "RELIANCE", "NSE"))
    assert age == pytest.approx(15.0)


def test_cache_age_seconds_none_for_unknown_key():
    cache = CachingProvider(FakeInnerProvider())
    assert cache.cache_age_seconds(("get_latest_price", "NEVER_FETCHED", "NSE")) is None


def test_clear_removes_all_entries():
    inner = FakeInnerProvider()
    cache = CachingProvider(inner, clock=lambda: 0.0)
    cache.get_latest_price("RELIANCE", "NSE")
    cache.clear()
    cache.get_latest_price("RELIANCE", "NSE")
    assert inner.call_count == 2


def test_rejects_non_positive_ttls():
    with pytest.raises(ValueError):
        CachingProvider(FakeInnerProvider(), live_ttl_seconds=0.0)
    with pytest.raises(ValueError):
        CachingProvider(FakeInnerProvider(), historical_ttl_seconds=-1.0)
