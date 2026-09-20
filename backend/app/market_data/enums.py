"""
Supported OHLCV timeframes. This is the single place the set of supported
intervals is defined - indicators, ingestion, and providers all import this
enum rather than each declaring their own string literals.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional


class Timeframe(str, Enum):
    ONE_MIN = "1m"
    THREE_MIN = "3m"
    FIVE_MIN = "5m"
    TEN_MIN = "10m"
    FIFTEEN_MIN = "15m"
    THIRTY_MIN = "30m"
    DAY = "1d"

    @property
    def minutes(self) -> Optional[int]:
        """Interval length in minutes, or None for DAY (a daily bar has no
        sub-session interval length)."""
        return {
            Timeframe.ONE_MIN: 1,
            Timeframe.THREE_MIN: 3,
            Timeframe.FIVE_MIN: 5,
            Timeframe.TEN_MIN: 10,
            Timeframe.FIFTEEN_MIN: 15,
            Timeframe.THIRTY_MIN: 30,
            Timeframe.DAY: None,
        }[self]

    @property
    def is_intraday(self) -> bool:
        return self is not Timeframe.DAY
