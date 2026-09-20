"""
Backtest report: computes every requested statistic from a list of
CLOSED TradeRecords. Trades still open at the end of the backtest period
are excluded from every statistic here (their outcome is genuinely
unknown) - pass them separately if you want their count reported.

"Winning"/"losing" are determined by NET P&L (after costs), not by which
lifecycle state a trade exited in - see trade_record.py's docstring for
why that distinction matters.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from app.backtesting.trade_record import TradeRecord


@dataclass
class BacktestReport:
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Optional[float]        # winning_trades / total_trades, None if total_trades == 0
    average_win: Optional[float]     # mean net P&L of winning trades (currency)
    average_loss: Optional[float]    # mean net P&L of losing trades (currency, negative)
    profit_factor: Optional[float]   # gross profit / gross loss; None if there were no losses (undefined, not infinite)
    max_drawdown: float              # largest peak-to-trough decline in cumulative equity (currency, >= 0)
    average_r: Optional[float]       # mean R-multiple across closed trades with a defined R
    expectancy: Optional[float]      # mean net P&L per trade (currency) - equals total_pnl / total_trades
    total_pnl: float                 # sum of net P&L across all closed trades
    open_trades_count: int = 0       # trades still active at period end - informational only, excluded above


def compute_report(trades: List[TradeRecord], open_trades: Optional[List[TradeRecord]] = None) -> BacktestReport:
    closed = [t for t in trades if t.is_closed]
    open_count = len(open_trades) if open_trades else 0

    total_trades = len(closed)
    if total_trades == 0:
        return BacktestReport(
            total_trades=0, winning_trades=0, losing_trades=0, win_rate=None,
            average_win=None, average_loss=None, profit_factor=None, max_drawdown=0.0,
            average_r=None, expectancy=None, total_pnl=0.0, open_trades_count=open_count,
        )

    wins = [t for t in closed if t.net_pnl is not None and t.net_pnl > 0]
    losses = [t for t in closed if t.net_pnl is not None and t.net_pnl <= 0]

    total_pnl = sum(t.net_pnl for t in closed if t.net_pnl is not None)
    gross_profit = sum(t.net_pnl for t in wins)
    gross_loss = sum(t.net_pnl for t in losses)  # negative or zero

    win_rate = len(wins) / total_trades
    average_win = (gross_profit / len(wins)) if wins else None
    average_loss = (gross_loss / len(losses)) if losses else None
    profit_factor = (gross_profit / abs(gross_loss)) if gross_loss < 0 else None

    r_values = [t.r_multiple for t in closed if t.r_multiple is not None]
    average_r = (sum(r_values) / len(r_values)) if r_values else None

    expectancy = total_pnl / total_trades

    max_drawdown = _max_drawdown(closed)

    return BacktestReport(
        total_trades=total_trades,
        winning_trades=len(wins),
        losing_trades=len(losses),
        win_rate=win_rate,
        average_win=average_win,
        average_loss=average_loss,
        profit_factor=profit_factor,
        max_drawdown=max_drawdown,
        average_r=average_r,
        expectancy=expectancy,
        total_pnl=total_pnl,
        open_trades_count=open_count,
    )


def _max_drawdown(closed_trades: List[TradeRecord]) -> float:
    """Builds a chronological (by exit time) equity curve from cumulative
    net P&L and returns the largest peak-to-trough decline. Sorting by
    exit time matters for portfolio-level (multi-symbol) backtests, where
    trades from different symbols interleave in time - P&L is realized
    when a trade CLOSES, not when it opens."""
    ordered = sorted((t for t in closed_trades if t.net_pnl is not None), key=lambda t: t.exit_time)
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in ordered:
        equity += t.net_pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd
