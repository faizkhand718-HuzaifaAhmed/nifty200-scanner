"""
NSE trading-session calendar: regular session hours, weekends, and holidays.

Holiday dates are loaded from an external JSON file (same pattern as the
Phase 2 instrument universe file) so the calendar can be updated yearly
without touching code - see config/market_calendar/nse_holidays_2026.json.
"""
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Union
from zoneinfo import ZoneInfo

from app.market_data.enums import Timeframe
from app.market_data.schemas import MarketSessionState, MarketStatus

IST = ZoneInfo("Asia/Kolkata")

NSE_MARKET_OPEN = time(9, 15)
NSE_MARKET_CLOSE = time(15, 30)


class NSECalendar:
    def __init__(self, holidays: Optional[Dict[date, str]] = None):
        # date -> holiday name
        self.holidays: Dict[date, str] = holidays or {}

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "NSECalendar":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Holiday calendar file not found: {path}")
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        holidays = {
            date.fromisoformat(entry["date"]): entry.get("name", "Market holiday")
            for entry in data.get("holidays", [])
        }
        return cls(holidays)

    @classmethod
    def from_files(cls, paths: List[Union[str, Path]]) -> "NSECalendar":
        """Merge multiple yearly holiday files (e.g. 2026 + 2027) into one
        calendar so year boundaries don't need special-casing elsewhere."""
        merged: Dict[date, str] = {}
        for p in paths:
            cal = cls.from_file(p)
            merged.update(cal.holidays)
        return cls(merged)

    def is_holiday(self, d: date) -> bool:
        return d in self.holidays

    def holiday_name(self, d: date) -> Optional[str]:
        return self.holidays.get(d)

    def is_weekend(self, d: date) -> bool:
        return d.weekday() >= 5  # Saturday=5, Sunday=6

    def is_trading_day(self, d: date) -> bool:
        return not self.is_weekend(d) and not self.is_holiday(d)

    def session_open(self, d: date) -> datetime:
        return datetime.combine(d, NSE_MARKET_OPEN, tzinfo=IST)

    def session_close(self, d: date) -> datetime:
        return datetime.combine(d, NSE_MARKET_CLOSE, tzinfo=IST)

    def next_trading_day(self, from_date: date) -> date:
        d = from_date + timedelta(days=1)
        while not self.is_trading_day(d):
            d += timedelta(days=1)
        return d

    def previous_trading_day(self, from_date: date) -> date:
        d = from_date - timedelta(days=1)
        while not self.is_trading_day(d):
            d -= timedelta(days=1)
        return d

    def trading_days_between(self, start: date, end: date) -> List[date]:
        if end < start:
            return []
        days = []
        d = start
        while d <= end:
            if self.is_trading_day(d):
                days.append(d)
            d += timedelta(days=1)
        return days

    def session_timestamps(self, d: date, timeframe: Timeframe) -> List[datetime]:
        """The expected candle-open timestamps for a trading day at a given
        timeframe. For DAY, this is a single timestamp at session open,
        used as the canonical timestamp for the daily bar. Returns an
        empty list if `d` is not a trading day."""
        if not self.is_trading_day(d):
            return []

        if timeframe is Timeframe.DAY:
            return [self.session_open(d)]

        step_minutes = timeframe.minutes
        assert step_minutes is not None
        ts = self.session_open(d)
        close = self.session_close(d)
        timestamps = []
        while ts <= close:
            timestamps.append(ts)
            ts += timedelta(minutes=step_minutes)
        return timestamps

    def get_market_status(
        self, as_of: Optional[datetime] = None, exchange: str = "NSE"
    ) -> MarketStatus:
        as_of = (as_of or datetime.now(IST)).astimezone(IST)
        today = as_of.date()

        if not self.is_trading_day(today):
            reason = "Weekend" if self.is_weekend(today) else (self.holiday_name(today) or "Market holiday")
            return MarketStatus(
                exchange=exchange,
                state=MarketSessionState.HOLIDAY,
                as_of=as_of,
                reason=reason,
                next_open=self.session_open(self.next_trading_day(today)),
            )

        open_dt = self.session_open(today)
        close_dt = self.session_close(today)

        if as_of < open_dt:
            return MarketStatus(
                exchange=exchange, state=MarketSessionState.PRE_OPEN, as_of=as_of, next_open=open_dt
            )
        if as_of > close_dt:
            return MarketStatus(
                exchange=exchange,
                state=MarketSessionState.CLOSED,
                as_of=as_of,
                next_open=self.session_open(self.next_trading_day(today)),
            )
        return MarketStatus(
            exchange=exchange, state=MarketSessionState.OPEN, as_of=as_of, next_close=close_dt
        )
