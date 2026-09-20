"""
DailyRiskState: the mutable state RiskManager consults and updates -
open positions (for duplicate detection and the open-positions limit),
trades taken today (for the daily trade-count limit), and realized P&L
today (for the daily-loss limit). Kept as a separate, small, fully-
testable class rather than baked into RiskManager directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Set


@dataclass
class DailyRiskState:
    current_date: date
    open_position_symbols: Set[str] = field(default_factory=set)
    trades_taken_today: int = 0
    realized_pnl_today: float = 0.0

    def has_open_position(self, symbol: str) -> bool:
        return symbol in self.open_position_symbols

    def record_trade_opened(self, symbol: str) -> None:
        self.open_position_symbols.add(symbol)
        self.trades_taken_today += 1

    def record_trade_closed(self, symbol: str, realized_pnl: float) -> None:
        self.open_position_symbols.discard(symbol)
        self.realized_pnl_today += realized_pnl

    def reset_for_new_day(self, new_date: date) -> None:
        """Resets the DAILY counters only. Open positions are NOT
        cleared - a position genuinely still open when a new day begins
        is still open; that's a separate concern (e.g. an intraday
        system might force-close at EOD elsewhere, but that's not this
        class's job to assume)."""
        self.current_date = new_date
        self.trades_taken_today = 0
        self.realized_pnl_today = 0.0
