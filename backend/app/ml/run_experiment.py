"""
End-to-end ML experiment: generates a synthetic multi-symbol dataset,
runs the full Phase 4-7/10/12 pipeline to produce real backtest trades,
extracts features (Phase 15), trains the ML model on a chronological
split, and reports the honest out-of-sample Rule-based vs Rule+ML
comparison.

Run from the backend/ directory:
    python -m app.ml.run_experiment

WHAT TO EXPECT: this project's MockDataProvider-style data (and the
synthetic random walk generated below) has no genuine predictive
structure by construction - it's noise with a drift term, not real
market behavior. The HONEST, CORRECT result of this experiment is
therefore that ML shows little or no real improvement out-of-sample, and
may even show a worse result. When this was run during development: Rule-
based expectancy ~696 vs Rule+ML ~-62 on a 37-trade held-out test set,
correctly triggering "DO NOT RETAIN ML." That is not a failure of this
code - it is the correct behavior of a well-built experiment run on data
with no real signal in it. Do not be tempted to change the threshold or
model until the result "looks good" - that would be p-hacking against
your own test set, precisely what the chronological split exists to
prevent.
"""
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from app.backtesting.config import BacktestConfig
from app.backtesting.engine import run_symbol
from app.entry_engine.config import EntryEngineConfig, EntryMethod, StopMethod, TargetMethod
from app.indicators.engine import IndicatorEngine
from app.ml.comparison import compare_rule_vs_ml
from app.ml.labels import build_training_examples
from app.ml.model import MLModel
from app.ml.split import chronological_split
from app.scoring.engine import OpportunityScoringEngine
from app.setup_detection.engine import SetupDetectionEngine

IST = ZoneInfo("Asia/Kolkata")


def session_timestamps(d, minutes_step=15):
    open_t = datetime(d.year, d.month, d.day, 9, 15, tzinfo=IST)
    close_t = datetime(d.year, d.month, d.day, 15, 30, tzinfo=IST)
    out = []
    ts = open_t
    while ts <= close_t:
        out.append(ts)
        ts += timedelta(minutes=minutes_step)
    return out


def trading_days(start, n_days):
    days = []
    d = start
    while len(days) < n_days:
        if d.weekday() < 5:  # skip weekends; ignore holidays for this synthetic experiment
            days.append(d)
        d += timedelta(days=1)
    return days


def build_symbol_ohlcv(symbol, n_days=40, seed_price=200.0, drift_bias=0.0, vol=0.006, seed=0):
    """A real (numpy) random walk per symbol, each with a different seed
    and drift bias, so different symbols behave differently rather than
    all being the same series shifted."""
    rng = np.random.default_rng(seed)
    days = trading_days(date(2026, 1, 5), n_days)
    timestamps = [ts for d in days for ts in session_timestamps(d)]
    n = len(timestamps)

    log_returns = rng.normal(loc=drift_bias, scale=vol, size=n)
    prices = seed_price * np.exp(np.cumsum(log_returns))

    rows = []
    for i, ts in enumerate(timestamps):
        close = float(prices[i])
        intrabar_vol = close * vol * 0.5
        high = close + abs(rng.normal(0, intrabar_vol))
        low = close - abs(rng.normal(0, intrabar_vol))
        open_ = close - rng.normal(0, intrabar_vol * 0.3)
        volume = int(50000 + rng.uniform(0, 200000))
        rows.append((ts, open_, max(high, close, open_), min(low, close, open_), close, volume))
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])


SYMBOLS = [
    ("SYM_G", 0.00008, 555),
    ("SYM_H", -0.00012, 777),
    ("SYM_I", 0.00003, 888),
    ("SYM_J", 0.00018, 999),
    ("SYM_A", 0.00015, 42),
    ("SYM_B", -0.00010, 7),
    ("SYM_C", 0.00005, 99),
    ("SYM_D", 0.00020, 123),
    ("SYM_E", -0.00005, 256),
    ("SYM_F", 0.00010, 314),
]

def main():
    print("Generating synthetic multi-symbol dataset...")
    all_trades = []
    all_examples = []
    direction = "LONG"

    backtest_config = BacktestConfig(
        direction=direction,
        entry_config=EntryEngineConfig(
            entry_method=EntryMethod.BREAKOUT,
            stop_method=StopMethod.SUPPORT_RESISTANCE,
            target_method=TargetMethod.RISK_REWARD_2,
        ),
        min_score=30.0,  # loose gate, to get enough trades for a meaningful split
    )

    for symbol, drift, seed in SYMBOLS:
        ohlcv = build_symbol_ohlcv(symbol, n_days=140, seed_price=200.0 + seed, drift_bias=drift, seed=seed)
        indicators_df = IndicatorEngine().compute(ohlcv)
        setup_df = SetupDetectionEngine().compute(indicators_df, nifty_df=None)
        scoring_df = OpportunityScoringEngine().compute(indicators_df, setup_df, nifty_indicators_df=None)

        trades, open_trade = run_symbol(symbol, indicators_df, setup_df, scoring_df, backtest_config)
        print(f"  {symbol}: {len(trades)} closed trades, open at end: {open_trade is not None}")
        all_trades.extend(trades)

        examples = build_training_examples(trades, indicators_df, setup_df, scoring_df, direction=direction)
        all_examples.extend(examples)

    print(f"\nTotal closed trades across all symbols: {len(all_trades)}")
    print(f"Total training examples (features successfully extracted): {len(all_examples)}")

    if len(all_examples) < 30:
        print("Not enough examples for a meaningful train/val/test split - experiment inconclusive.")
        return

    train, val, test = chronological_split(all_examples, train_frac=0.6, val_frac=0.2)
    print(f"\nSplit: train={len(train)}, val={len(val)}, test={len(test)}")
    print(f"Train label balance: {sum(e.label for e in train)}/{len(train)} wins")
    print(f"Val label balance:   {sum(e.label for e in val)}/{len(val)} wins")
    print(f"Test label balance:  {sum(e.label for e in test)}/{len(test)} wins")

    model = MLModel()
    model.fit(train)

    print("\nModel coefficients (scaled-feature space):")
    for name, coef in sorted(model.feature_coefficients().items(), key=lambda kv: -abs(kv[1])):
        print(f"  {name:30s} {coef:+.4f}")

    # Validation-set accuracy, just as a sanity check on the model's plumbing
    val_probs = model.predict_proba(val)
    val_preds = [1 if p >= 0.5 else 0 for p in val_probs]
    val_labels = [e.label for e in val]
    val_accuracy = sum(p == l for p, l in zip(val_preds, val_labels)) / len(val_labels) if val_labels else None
    print(f"\nValidation accuracy: {val_accuracy:.3f}" if val_accuracy is not None else "\nValidation set empty")

    # Match test trades to test examples for the actual out-of-sample comparison
    test_example_keys = {(e.symbol, e.entry_time) for e in test}
    matching_trades = [t for t in all_trades if (t.symbol, t.entry_time) in test_example_keys]

    print(f"\nTest-set trades available for comparison: {len(matching_trades)}")

    result = compare_rule_vs_ml(matching_trades, test, model, probability_threshold=0.5, min_trades_for_decision=10)

    print("\n" + "=" * 70)
    print("OUT-OF-SAMPLE COMPARISON: Rule-based vs Rule+ML (TEST SET ONLY)")
    print("=" * 70)
    print(f"Rule-based : trades={result.rule_based.total_trades:3d}  win_rate={result.rule_based.win_rate}  "
          f"expectancy={result.rule_based.expectancy}  total_pnl={result.rule_based.total_pnl}")
    print(f"Rule+ML    : trades={result.rule_plus_ml.total_trades:3d}  win_rate={result.rule_plus_ml.win_rate}  "
          f"expectancy={result.rule_plus_ml.expectancy}  total_pnl={result.rule_plus_ml.total_pnl}")
    print(f"\nDecision: {'RETAIN ML' if result.retain_ml else 'DO NOT RETAIN ML'}")
    print(f"Reason: {result.reason}")
    return result


if __name__ == "__main__":
    main()
