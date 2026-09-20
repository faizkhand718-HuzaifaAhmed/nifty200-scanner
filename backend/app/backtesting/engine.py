"""
BacktestEngine: the top-level entry point tying together historical data
(Phase 3), indicators (Phase 4), setup detection (Phase 5), scoring
(Phase 6), and the entry/risk/reward engine (Phase 10) into a full
historical backtest.

CRITICAL - NO LOOK-AHEAD BIAS: `run_symbol`/`run_universe` consume
already-computed indicators_df/setup_df/scoring_df and process them
STRICTLY in chronological row order via SymbolBacktestTracker.step(),
exactly mirroring how TradeLifecycle.run() works in Phase 10. The
indicator/setup/score values themselves are safe to precompute over the
whole date range in one call (Phase 4/5/6 each already prove, in their
own no-lookahead tests, that a value at row T depends only on rows <= T -
computing them "all at once" over a full DataFrame produces byte-identical
results to computing them incrementally). What must NEVER happen, and
does not happen here, is a trade's entry/exit decision being evaluated
using a future row's price - the tracker only ever sees ind_row/prev_ind_row/
setup_row/scoring_row for the CURRENT bar being stepped, one at a time.
See tests/test_backtest_no_lookahead.py for the proof: a trade recorded
within a shorter date range is byte-identical to the same trade recorded
within a longer range that includes more future data.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

from app.backtesting.config import BacktestConfig
from app.backtesting.metrics import BacktestReport, compute_report
from app.backtesting.tracker import SymbolBacktestTracker
from app.backtesting.trade_record import TradeRecord


def run_symbol(
    symbol: str,
    indicators_df: pd.DataFrame,
    setup_df: pd.DataFrame,
    scoring_df: Optional[pd.DataFrame],
    config: BacktestConfig,
) -> Tuple[List[TradeRecord], Optional[TradeRecord]]:
    """Runs one symbol's full historical sequence and returns
    (completed_trades, open_trade_or_None)."""
    if len(indicators_df) != len(setup_df):
        raise ValueError("indicators_df and setup_df must have the same number of rows")
    if scoring_df is not None and len(scoring_df) != len(indicators_df):
        raise ValueError("scoring_df must have the same number of rows as indicators_df")

    tracker = SymbolBacktestTracker(symbol, config)
    prev_ind_row: Optional[pd.Series] = None
    for i in range(len(indicators_df)):
        ind_row = indicators_df.iloc[i]
        setup_row = setup_df.iloc[i]
        scoring_row = scoring_df.iloc[i] if scoring_df is not None else None
        tracker.step(ind_row, prev_ind_row, setup_row, scoring_row)
        prev_ind_row = ind_row
    tracker.finalize()

    return tracker.completed_trades, tracker.open_trade


def run_universe(
    symbol_data: Dict[str, Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]],
    config: BacktestConfig,
) -> Tuple[List[TradeRecord], List[TradeRecord], BacktestReport]:
    """
    Runs the backtest across multiple symbols (the "NIFTY 200" option -
    pass every universe symbol's data here) and aggregates into one
    report. `symbol_data` maps symbol -> (indicators_df, setup_df,
    scoring_df); each symbol is tracked completely independently (its own
    SymbolBacktestTracker), matching how these would actually trade as
    unrelated positions.

    Returns (all_completed_trades, all_open_trades, aggregated_report).
    """
    config.validate()
    all_trades: List[TradeRecord] = []
    all_open: List[TradeRecord] = []

    for symbol, (indicators_df, setup_df, scoring_df) in symbol_data.items():
        trades, open_trade = run_symbol(symbol, indicators_df, setup_df, scoring_df, config)
        all_trades.extend(trades)
        if open_trade is not None:
            all_open.append(open_trade)

    report = compute_report(all_trades, open_trades=all_open)
    return all_trades, all_open, report
