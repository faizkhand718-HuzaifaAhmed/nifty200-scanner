"""
Deterministic, synthetic market-data provider so the rest of the
application can be built and tested without any real API credentials.

Design notes:
  - Prices are a seeded random walk anchored at a fixed epoch date, so
    price(symbol, date) is always the same value regardless of which date
    range a caller happens to query it through - two different calls (or
    two different MockDataProvider instances with the same seed) never
    disagree about what a given day's close was.
  - This is SYNTHETIC data: plausible OHLCV shape, not calibrated to real
    historical prices. Never treat it as real market data.
  - `set_clock()` lets tests fix "now" instead of the real wall clock, so
    intraday/incomplete-candle behavior is deterministic and testable.
  - `simulate_next_call_failure()` lets tests exercise error-handling and
    retry logic deterministically instead of via random chance.
"""
from __future__ import annotations

import hashlib
import random
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from app.market_data.base import MarketDataProvider
from app.market_data.calendar import IST, NSECalendar
from app.market_data.enums import Timeframe
from app.market_data.exceptions import SymbolNotFoundError
from app.market_data.schemas import (
    Candle,
    IndexQuote,
    MarketStatus,
    OptionChain,
    OptionContract,
    OptionType,
    Quote,
)

_EPOCH = date(2020, 1, 1)


class MockDataProvider(MarketDataProvider):
    def __init__(self, calendar: NSECalendar, seed: int = 42):
        self.calendar = calendar
        self.seed = seed
        self._clock_override: Optional[datetime] = None
        self._pending_failures: List[BaseException] = []
        self._price_cache: Dict[str, Dict[date, float]] = {}

    # -- test helpers ---------------------------------------------------
    def set_clock(self, dt: datetime) -> None:
        if dt.tzinfo is None:
            raise ValueError("clock override must be timezone-aware")
        self._clock_override = dt.astimezone(IST)

    def clear_clock(self) -> None:
        self._clock_override = None

    def simulate_next_call_failure(self, exc: BaseException) -> None:
        """Queue an exception to be raised on the NEXT provider call only."""
        self._pending_failures.append(exc)

    def _now(self) -> datetime:
        return self._clock_override or datetime.now(IST)

    def _maybe_raise_pending(self) -> None:
        if self._pending_failures:
            raise self._pending_failures.pop(0)

    # -- deterministic price chain, anchored at a fixed epoch ------------
    def _base_price(self, symbol: str) -> float:
        h = int(hashlib.sha256(symbol.encode()).hexdigest(), 16)
        return float(50 + (h % 4950))  # 50 - 5000

    def _day_rng(self, symbol: str, d: date) -> random.Random:
        seed_material = f"{self.seed}:{symbol}:{d.isoformat()}"
        seed = int(hashlib.sha256(seed_material.encode()).hexdigest(), 16) % (2**32)
        return random.Random(seed)

    def _extend_close_chain(self, symbol: str, upto: date) -> None:
        cache = self._price_cache.setdefault(symbol, {})
        if cache and max(cache.keys()) >= upto:
            return

        if cache:
            last_cached_day = max(cache.keys())
            start_day = self.calendar.next_trading_day(last_cached_day)
            price = cache[last_cached_day]
        else:
            start_day = _EPOCH if self.calendar.is_trading_day(_EPOCH) else self.calendar.next_trading_day(_EPOCH)
            price = self._base_price(symbol)

        for d in self.calendar.trading_days_between(start_day, upto):
            rng = self._day_rng(symbol, d)
            drift_pct = rng.uniform(-0.02, 0.02)  # +/- 2% day-over-day
            price = max(1.0, price * (1 + drift_pct))
            cache[d] = round(price, 2)

    def _close_on(self, symbol: str, d: date) -> float:
        self._extend_close_chain(symbol, d)
        return self._price_cache[symbol][d]

    def _prev_close_before(self, symbol: str, d: date) -> float:
        return self._close_on(symbol, self.calendar.previous_trading_day(d))

    def _generate_day_candles(
        self, symbol: str, exchange: str, timeframe: Timeframe, d: date
    ) -> List[Candle]:
        timestamps = self.calendar.session_timestamps(d, timeframe)
        if not timestamps:
            return []

        day_close = self._close_on(symbol, d)
        prev_close = self._prev_close_before(symbol, d)
        rng = self._day_rng(f"path:{symbol}", d)
        n = len(timestamps)
        step_target = (day_close - prev_close) / n if n else 0.0

        candles: List[Candle] = []
        price = prev_close
        for ts in timestamps:
            open_px = price
            noise = rng.uniform(-0.5, 0.5) * (open_px * 0.003 + 0.01)
            close_px = max(0.5, open_px + step_target + noise)
            high_px = max(open_px, close_px) + abs(rng.uniform(0, 0.002)) * open_px
            low_px = min(open_px, close_px) - abs(rng.uniform(0, 0.002)) * open_px
            volume = int(rng.uniform(1_000, 50_000))
            candles.append(
                Candle(
                    symbol=symbol,
                    exchange=exchange,
                    timeframe=timeframe,
                    timestamp=ts,
                    open=round(open_px, 2),
                    high=round(high_px, 2),
                    low=round(low_px, 2),
                    close=round(close_px, 2),
                    volume=volume,
                    is_complete=True,
                )
            )
            price = close_px
        # Force the last candle's close to exactly match the day's anchored
        # close so day-over-day continuity holds exactly, not approximately.
        if candles:
            last = candles[-1]
            candles[-1] = last.model_copy(update={"close": day_close})
        return candles

    # -- HistoricalOHLCVProvider -----------------------------------------
    def get_historical_candles(
        self, symbol: str, exchange: str, timeframe: Timeframe, start: date, end: date
    ) -> List[Candle]:
        self._maybe_raise_pending()
        if not symbol:
            raise SymbolNotFoundError("symbol must not be empty")
        candles: List[Candle] = []
        for d in self.calendar.trading_days_between(start, end):
            candles.extend(self._generate_day_candles(symbol, exchange, timeframe, d))
        return candles

    # -- IntradayOHLCVProvider --------------------------------------------
    def get_intraday_candles(
        self, symbol: str, exchange: str, timeframe: Timeframe, from_time: Optional[datetime] = None
    ) -> List[Candle]:
        self._maybe_raise_pending()
        now = self._now()
        today = now.date()
        if not self.calendar.is_trading_day(today):
            return []

        candles = self._generate_day_candles(symbol, exchange, timeframe, today)
        available = [c for c in candles if c.timestamp <= now]
        if not available:
            return []

        last = available[-1]
        step = timeframe.minutes
        still_forming = (
            now < last.timestamp + timedelta(minutes=step)
            if step is not None
            else now < self.calendar.session_close(today)
        )
        if still_forming:
            available[-1] = last.model_copy(update={"is_complete": False})

        if from_time is not None:
            available = [c for c in available if c.timestamp >= from_time]
        return available

    # -- LatestPriceProvider -----------------------------------------------
    def get_latest_price(self, symbol: str, exchange: str) -> Quote:
        self._maybe_raise_pending()
        now = self._now()
        today = now.date()

        if self.calendar.is_trading_day(today) and now >= self.calendar.session_open(today):
            intraday = self.get_intraday_candles(symbol, exchange, Timeframe.ONE_MIN)
            if intraday:
                volume_so_far = sum(c.volume for c in intraday)
                return Quote(symbol=symbol, exchange=exchange, ltp=intraday[-1].close, volume=volume_so_far, timestamp=now)

        ref_day = today if self.calendar.is_trading_day(today) else self.calendar.previous_trading_day(today)
        if self.calendar.is_trading_day(today) and now < self.calendar.session_open(today):
            ref_day = self.calendar.previous_trading_day(today)
        return Quote(symbol=symbol, exchange=exchange, ltp=self._close_on(symbol, ref_day), volume=0, timestamp=now)

    # -- VolumeProvider -------------------------------------------------------
    def get_volume(self, symbol: str, exchange: str) -> int:
        self._maybe_raise_pending()
        now = self._now()
        if not self.calendar.is_trading_day(now.date()):
            return 0
        return sum(c.volume for c in self.get_intraday_candles(symbol, exchange, Timeframe.ONE_MIN))

    # -- MarketStatusProvider -------------------------------------------------
    def get_market_status(self, exchange: str = "NSE") -> MarketStatus:
        self._maybe_raise_pending()
        return self.calendar.get_market_status(self._now(), exchange=exchange)

    # -- IndexDataProvider --------------------------------------------------
    def get_index_quote(self, index_name: str) -> IndexQuote:
        self._maybe_raise_pending()
        now = self._now()
        today = now.date()
        ref_day = today if self.calendar.is_trading_day(today) else self.calendar.previous_trading_day(today)
        key = f"INDEX:{index_name}"
        value = self._close_on(key, ref_day)
        prev_value = self._prev_close_before(key, ref_day)
        change = round(value - prev_value, 2)
        change_pct = round((change / prev_value) * 100, 3) if prev_value else 0.0
        return IndexQuote(index_name=index_name, value=value, change=change, change_pct=change_pct, timestamp=now)

    # -- OptionChainProvider (future capability) -----------------------------
    def get_option_chain(self, underlying: str, expiry: Optional[date] = None) -> OptionChain:
        """
        SYNTHETIC PLACEHOLDER. Strikes/premiums use a simplistic formula,
        NOT a real option-pricing model (no Black-Scholes, no real IV
        surface). Exists so the interface and downstream UI can be
        developed/tested against a plausible shape - do not use for
        anything resembling analysis.
        """
        self._maybe_raise_pending()
        now = self._now()
        spot = self.get_latest_price(underlying, "NSE").ltp

        if expiry is None:
            days_ahead = (3 - now.weekday()) % 7  # next Thursday, typical weekly expiry
            days_ahead = days_ahead or 7
            expiry = (now + timedelta(days=days_ahead)).date()

        strike_step = 50 if spot < 2000 else (100 if spot < 10000 else 500)
        atm_strike = round(spot / strike_step) * strike_step
        rng = self._day_rng(f"OPTCHAIN:{underlying}", now.date())

        contracts: List[OptionContract] = []
        for offset in range(-5, 6):
            strike = atm_strike + offset * strike_step
            moneyness = spot - strike
            # Liquidity realistically concentrates near the money and
            # thins out toward far strikes - this is what gives Phase 14's
            # liquidity filtering something meaningful to differentiate,
            # rather than every strike looking equally (un)tradeable.
            distance_factor = 1.0 / (1.0 + abs(offset))  # 1.0 at ATM, decreasing outward
            for opt_type, intrinsic in (
                (OptionType.CALL, max(0.0, moneyness)),
                (OptionType.PUT, max(0.0, -moneyness)),
            ):
                time_value = max(0.5, abs(rng.uniform(2, 40)) - abs(offset) * 2)
                premium = round(intrinsic + time_value, 2)

                base_oi = rng.uniform(50_000, 500_000) * distance_factor
                open_interest = int(base_oi)
                volume = int(base_oi * rng.uniform(0.1, 0.4))  # volume as a fraction of OI, a typical pattern
                change_in_oi = int(rng.uniform(-0.15, 0.25) * open_interest)

                spread_pct = 0.005 + (1 - distance_factor) * 0.06  # ~0.5% ATM widening toward ~6.5% far strikes
                half_spread = premium * spread_pct / 2
                bid = round(max(0.05, premium - half_spread), 2)
                ask = round(premium + half_spread, 2)

                contracts.append(
                    OptionContract(
                        underlying=underlying,
                        expiry=expiry,
                        strike=float(strike),
                        option_type=opt_type,
                        ltp=premium,
                        open_interest=open_interest,
                        implied_volatility=round(rng.uniform(12, 35), 2),
                        timestamp=now,
                        volume=volume,
                        bid=bid,
                        ask=ask,
                        change_in_open_interest=change_in_oi,
                    )
                )

        return OptionChain(underlying=underlying, expiry=expiry, spot_price=spot, timestamp=now, contracts=contracts)
