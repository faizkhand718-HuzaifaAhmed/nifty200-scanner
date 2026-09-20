"""
Paper-trading dashboard summary: the 4 requested metrics (Today's P&L,
Win rate, Average R, Maximum drawdown), computed from closed positions.
Deliberately small and independent from Phase 12's backtest metrics
module - different input shape (PaperPosition, not TradeRecord), and
keeping these decoupled is worth the tiny duplication.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from app.paper_trading.models import PaperPosition


@dataclass
class PaperTradingSummary:
    open_positions_count: int
    closed_positions_count: int
    todays_pnl: float
    win_rate: Optional[float]
    average_r: Optional[float]
    max_drawdown: float


def _exit_date(position: PaperPosition) -> Optional[date]:
    ts = position.exit_time
    if ts is None:
        return None
    if hasattr(ts, "date"):
        return ts.date()
    return None


def compute_todays_pnl(closed_positions: List[PaperPosition], as_of: date) -> float:
    """Sum of P&L for positions that CLOSED on `as_of` - deliberately an
    explicit parameter rather than reading the real clock internally, so
    this stays testable/deterministic."""
    return sum(
        p.pnl for p in closed_positions
        if p.pnl is not None and _exit_date(p) == as_of
    )


def compute_win_rate(closed_positions: List[PaperPosition]) -> Optional[float]:
    if not closed_positions:
        return None
    wins = sum(1 for p in closed_positions if p.is_win)
    return wins / len(closed_positions)


def compute_average_r(closed_positions: List[PaperPosition]) -> Optional[float]:
    r_values = [p.r_multiple for p in closed_positions if p.r_multiple is not None]
    if not r_values:
        return None
    return sum(r_values) / len(r_values)


def compute_max_drawdown(closed_positions: List[PaperPosition]) -> float:
    """Same approach as Phase 12's backtest max-drawdown: a chronological
    (by exit time) equity curve from cumulative P&L, largest peak-to-
    trough decline."""
    ordered = sorted(
        (p for p in closed_positions if p.pnl is not None and p.exit_time is not None),
        key=lambda p: p.exit_time,
    )
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in ordered:
        equity += p.pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def compute_summary(
    open_positions: List[PaperPosition],
    closed_positions: List[PaperPosition],
    as_of: date,
) -> PaperTradingSummary:
    return PaperTradingSummary(
        open_positions_count=len(open_positions),
        closed_positions_count=len(closed_positions),
        todays_pnl=compute_todays_pnl(closed_positions, as_of),
        win_rate=compute_win_rate(closed_positions),
        average_r=compute_average_r(closed_positions),
        max_drawdown=compute_max_drawdown(closed_positions),
    )
