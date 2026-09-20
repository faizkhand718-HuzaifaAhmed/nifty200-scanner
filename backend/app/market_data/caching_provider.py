"""
CachingProvider: wraps ANY provider implementing the base interfaces with
a simple TTL cache, keyed on (method name, arguments). Generic on
purpose - this has no NSE-specific knowledge, so it's reusable for any
future provider and fully testable with a fake inner provider (no
network, no `mcp` package needed).

WHY CACHING MATTERS HERE SPECIFICALLY: "respect the data freshness and
usage limitations specified by NSE" - NSE's own page doesn't publish a
numeric rate limit, so the TTLs below are a considered default, not a
number NSE gave us: CM Market Live is documented as itself only refreshing
every 1-3 minutes, so polling it more often than that is pointless
regardless of any rate limit; Bhavcopy updates once per trading day, so a
multi-hour cache is clearly safe. Both are configurable (see
app.core.config.Settings) if NSE's actual limits turn out to differ.
WHY THIS DOESN'T FORMALLY INHERIT FROM THE PROVIDER ABCs (app.market_data.base):
those ABCs import pydantic-based schema types (Candle, Quote) at module
level, and this caching logic has no actual need for that - it's a plain
dict-based memoization wrapper around whatever object it's given. Duck
typing (this class defines the same method names/signatures) is enough
for every real call site, which never does an isinstance() check. Not
formally inheriting is what makes it possible to test this file's actual
logic for real in a sandbox without pydantic installed - see
tests/test_caching_provider.py.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple


@dataclass
class _CacheEntry:
    value: Any
    cached_at: float


class CachingProvider:
    def __init__(
        self,
        inner,
        live_ttl_seconds: float = 60.0,
        historical_ttl_seconds: float = 6 * 3600.0,
        clock: Optional[Callable[[], float]] = None,
    ):
        if live_ttl_seconds <= 0 or historical_ttl_seconds <= 0:
            raise ValueError("TTLs must be positive")
        self.inner = inner
        self.live_ttl_seconds = live_ttl_seconds
        self.historical_ttl_seconds = historical_ttl_seconds
        self._clock = clock or time.monotonic
        self._cache: Dict[Tuple, _CacheEntry] = {}

    def _get_or_fetch(self, key: Tuple, ttl: float, fetch_fn: Callable[[], Any]) -> Any:
        now = self._clock()
        entry = self._cache.get(key)
        if entry is not None and (now - entry.cached_at) < ttl:
            return entry.value

        value = fetch_fn()
        self._cache[key] = _CacheEntry(value=value, cached_at=now)
        return value

    def cache_age_seconds(self, key: Tuple) -> Optional[float]:
        entry = self._cache.get(key)
        if entry is None:
            return None
        return self._clock() - entry.cached_at

    def clear(self) -> None:
        self._cache.clear()

    def get_latest_price(self, symbol: str, exchange: str):
        key = ("get_latest_price", symbol, exchange)
        return self._get_or_fetch(key, self.live_ttl_seconds, lambda: self.inner.get_latest_price(symbol, exchange))

    def get_volume(self, symbol: str, exchange: str):
        key = ("get_volume", symbol, exchange)
        return self._get_or_fetch(key, self.live_ttl_seconds, lambda: self.inner.get_volume(symbol, exchange))

    def get_historical_candles(self, symbol, exchange, timeframe, start, end):
        key = ("get_historical_candles", symbol, exchange, timeframe, start, end)
        return self._get_or_fetch(
            key, self.historical_ttl_seconds,
            lambda: self.inner.get_historical_candles(symbol, exchange, timeframe, start, end),
        )

    def get_intraday_candles(self, symbol, exchange, timeframe, from_time=None):
        key = ("get_intraday_candles", symbol, exchange, timeframe, from_time)
        return self._get_or_fetch(
            key, self.live_ttl_seconds,
            lambda: self.inner.get_intraday_candles(symbol, exchange, timeframe, from_time),
        )
