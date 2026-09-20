"""
Builds (features, label) training examples directly from Phase 12's
actual backtest trades - not an invented parallel universe of hypothetical
entries. Each example's features are computed from data available AT the
trade's entry bar (already-causal); its label is the trade's REAL eventual
outcome, which necessarily depends on future bars - that is expected and
correct for a supervised-learning label (a label is allowed to look
forward; a feature never is).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

import pandas as pd

from app.backtesting.trade_record import TradeRecord
from app.ml.features import FEATURE_NAMES, extract_features, realized_volatility

# Fields that must NEVER appear in a feature dict - if any of these leak in,
# the model would be training on the future. Checked explicitly by
# tests/test_ml_no_leakage.py, not just asserted here in a docstring.
FORBIDDEN_FEATURE_KEYS = {
    "exit_price", "exit_time", "exit_reason", "net_pnl", "gross_pnl",
    "r_multiple", "pnl", "pnl_pct", "target_price", "is_win",
}


@dataclass
class TrainingExample:
    symbol: str
    entry_time: Any
    features: dict
    label: int  # 1 = win (net P&L > 0), 0 = loss


def build_training_examples(
    trades: List[TradeRecord],
    indicators_df: pd.DataFrame,
    setup_df: pd.DataFrame,
    scoring_df: pd.DataFrame,
    direction: str,
    nifty_indicators_df: Optional[pd.DataFrame] = None,
    volatility_window: int = 20,
) -> List[TrainingExample]:
    """
    Only CLOSED trades produce a training example (an open trade has no
    known label yet - including it would require guessing an outcome).
    A trade whose entry-bar features can't be fully computed (e.g. too
    early for indicator warm-up) is skipped, not imputed.
    """
    indicators_df = indicators_df.reset_index(drop=True)
    setup_df = setup_df.reset_index(drop=True)
    scoring_df = scoring_df.reset_index(drop=True)

    ts_to_index = {ts: i for i, ts in enumerate(indicators_df["timestamp"])}
    vol_series = realized_volatility(indicators_df["close"], window=volatility_window)

    nifty_by_ts = None
    if nifty_indicators_df is not None:
        nifty_indicators_df = nifty_indicators_df.reset_index(drop=True)
        nifty_by_ts = {ts: i for i, ts in enumerate(nifty_indicators_df["timestamp"])}

    examples: List[TrainingExample] = []
    for trade in trades:
        if not trade.is_closed or trade.net_pnl is None:
            continue

        idx = ts_to_index.get(trade.entry_time)
        if idx is None:
            continue

        nifty_row = None
        if nifty_by_ts is not None:
            nifty_idx = nifty_by_ts.get(trade.entry_time)
            if nifty_idx is not None:
                nifty_row = nifty_indicators_df.iloc[nifty_idx]

        features = extract_features(
            ind_row=indicators_df.iloc[idx],
            setup_row=setup_df.iloc[idx],
            scoring_row=scoring_df.iloc[idx],
            direction=direction,
            nifty_ind_row=nifty_row,
            realized_vol=vol_series.iloc[idx],
        )
        if features is None:
            continue

        examples.append(
            TrainingExample(
                symbol=trade.symbol,
                entry_time=trade.entry_time,
                features=features,
                label=1 if trade.net_pnl > 0 else 0,
            )
        )

    return examples


def to_feature_matrix(examples: List[TrainingExample]):
    """Returns (X, y) as plain lists of lists / ints, in FEATURE_NAMES
    column order - kept as plain Python here so this module has no hard
    dependency on numpy/sklearn; model.py does the array conversion."""
    X = [[ex.features[name] for name in FEATURE_NAMES] for ex in examples]
    y = [ex.label for ex in examples]
    return X, y
