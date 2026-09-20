import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.backtesting.trade_record import TradeRecord  # noqa: E402
from app.ml.labels import FORBIDDEN_FEATURE_KEYS, build_training_examples, to_feature_matrix  # noqa: E402


def make_indicator_df():
    rows = []
    for i in range(30):
        ts = i
        close = 100.0 + i * 0.1
        rows.append({
            "timestamp": ts, "close": close, "vwap": close - 0.5,
            "ema_9": close + 0.2, "ema_20": close - 0.1, "ema_50": close - 0.3,
            "rsi": 55.0 + i, "adx": 20.0 + i * 0.1, "atr": 1.5, "relative_volume": 1.2,
            "relative_strength": 0.01,
        })
    return pd.DataFrame(rows)


def make_setup_df(n):
    return pd.DataFrame([{"long_breakout": True, "short_breakdown": False}] * n)


def make_scoring_df(n):
    return pd.DataFrame([{"long_score": 75.0, "short_score": 25.0}] * n)


def make_trade(entry_time, net_pnl, exit_reason="TARGET_HIT"):
    return TradeRecord(
        symbol="TEST", direction="LONG", entry_time=entry_time,
        entry_price_theoretical=100.0, entry_price_filled=100.1, stop_price=95.0, target_price=110.0,
        quantity=10, exit_time=entry_time + 5, exit_price_theoretical=105.0, exit_price_filled=104.9,
        exit_reason=exit_reason, gross_pnl=net_pnl, charges=0.0, net_pnl=net_pnl, r_multiple=net_pnl / 100,
    )


def test_build_training_examples_basic():
    ind_df = make_indicator_df()
    setup_df = make_setup_df(len(ind_df))
    scoring_df = make_scoring_df(len(ind_df))
    # entry times must be past the default 20-bar volatility warm-up window
    trades = [make_trade(22, 500.0), make_trade(25, -200.0, "STOP_LOSS_HIT")]

    examples = build_training_examples(trades, ind_df, setup_df, scoring_df, direction="LONG")

    assert len(examples) == 2
    assert examples[0].label == 1  # net_pnl=500 -> win
    assert examples[1].label == 0  # net_pnl=-200 -> loss


def test_build_training_examples_skips_open_trades():
    ind_df = make_indicator_df()
    setup_df = make_setup_df(len(ind_df))
    scoring_df = make_scoring_df(len(ind_df))
    open_trade = TradeRecord(
        symbol="TEST", direction="LONG", entry_time=5, entry_price_theoretical=100.0,
        entry_price_filled=100.1, stop_price=95.0, target_price=110.0, quantity=10,
    )
    examples = build_training_examples([open_trade], ind_df, setup_df, scoring_df, direction="LONG")
    assert examples == []


def test_build_training_examples_skips_trades_with_no_matching_bar():
    ind_df = make_indicator_df()
    setup_df = make_setup_df(len(ind_df))
    scoring_df = make_scoring_df(len(ind_df))
    trade = make_trade(entry_time=9999, net_pnl=500.0)  # entry_time not in ind_df
    examples = build_training_examples([trade], ind_df, setup_df, scoring_df, direction="LONG")
    assert examples == []


def test_no_forbidden_leakage_keys_in_any_feature_dict():
    """The central requirement: features must never contain post-entry
    (future) information."""
    ind_df = make_indicator_df()
    setup_df = make_setup_df(len(ind_df))
    scoring_df = make_scoring_df(len(ind_df))
    trades = [make_trade(t, 500.0 if t % 2 == 0 else -200.0) for t in range(5, 25)]

    examples = build_training_examples(trades, ind_df, setup_df, scoring_df, direction="LONG")
    assert len(examples) > 0

    for example in examples:
        leaked = set(example.features.keys()) & FORBIDDEN_FEATURE_KEYS
        assert not leaked, f"leaked keys found: {leaked}"


def test_to_feature_matrix_shape_and_order():
    ind_df = make_indicator_df()
    setup_df = make_setup_df(len(ind_df))
    scoring_df = make_scoring_df(len(ind_df))
    trades = [make_trade(22, 500.0), make_trade(25, -200.0)]
    examples = build_training_examples(trades, ind_df, setup_df, scoring_df, direction="LONG")

    X, y = to_feature_matrix(examples)
    assert len(X) == len(examples) == len(y)
    assert all(len(row) == len(examples[0].features) for row in X)
    assert set(y) <= {0, 1}
