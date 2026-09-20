"""
Runs a SMALL version of the full pipeline (fewer symbols/days than
app/ml/run_experiment.py, to keep test runtime reasonable) and checks
STRUCTURAL correctness only: the pipeline completes, produces the right
types, and the comparison logic runs without error.

This test DELIBERATELY does not assert whether ML is retained or not -
that's an empirical finding about this specific synthetic dataset, not a
code invariant. Asserting a specific outcome here would be wrong twice
over: it would break if the synthetic data generation changes even
slightly, and it would encourage exactly the kind of "adjust until the
test passes" behavior this phase is designed to prevent. Run
app/ml/run_experiment.py directly to see the actual, current honest result.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.run_experiment import build_symbol_ohlcv  # noqa: E402
from app.backtesting.config import BacktestConfig  # noqa: E402
from app.backtesting.engine import run_symbol  # noqa: E402
from app.entry_engine.config import EntryEngineConfig, EntryMethod, StopMethod, TargetMethod  # noqa: E402
from app.indicators.engine import IndicatorEngine  # noqa: E402
from app.ml.comparison import StrategyComparisonResult, compare_rule_vs_ml  # noqa: E402
from app.ml.labels import build_training_examples  # noqa: E402
from app.ml.model import MLModel  # noqa: E402
from app.ml.split import chronological_split  # noqa: E402
from app.scoring.engine import OpportunityScoringEngine  # noqa: E402
from app.setup_detection.engine import SetupDetectionEngine  # noqa: E402


def test_full_pipeline_runs_and_produces_valid_comparison_result():
    backtest_config = BacktestConfig(
        direction="LONG",
        entry_config=EntryEngineConfig(
            entry_method=EntryMethod.BREAKOUT, stop_method=StopMethod.SUPPORT_RESISTANCE, target_method=TargetMethod.RISK_REWARD_2
        ),
        min_score=30.0,
    )

    all_trades = []
    all_examples = []
    for symbol, drift, seed in [("A", 0.0001, 1), ("B", -0.0001, 2), ("C", 0.00005, 3)]:
        ohlcv = build_symbol_ohlcv(symbol, n_days=60, seed_price=200.0, drift_bias=drift, seed=seed)
        indicators_df = IndicatorEngine().compute(ohlcv)
        setup_df = SetupDetectionEngine().compute(indicators_df, nifty_df=None)
        scoring_df = OpportunityScoringEngine().compute(indicators_df, setup_df, nifty_indicators_df=None)
        trades, _open = run_symbol(symbol, indicators_df, setup_df, scoring_df, backtest_config)
        all_trades.extend(trades)
        all_examples.extend(build_training_examples(trades, indicators_df, setup_df, scoring_df, direction="LONG"))

    assert len(all_examples) >= 10, "synthetic dataset too small to exercise the pipeline meaningfully"

    train, val, test = chronological_split(all_examples, train_frac=0.6, val_frac=0.2)
    assert len(train) > 0

    model = MLModel()
    model.fit(train)

    if val:
        val_probs = model.predict_proba(val)
        assert len(val_probs) == len(val)
        assert all(0.0 <= p <= 1.0 for p in val_probs)

    test_example_keys = {(e.symbol, e.entry_time) for e in test}
    matching_trades = [t for t in all_trades if (t.symbol, t.entry_time) in test_example_keys]

    result = compare_rule_vs_ml(matching_trades, test, model, probability_threshold=0.5, min_trades_for_decision=5)

    assert isinstance(result, StrategyComparisonResult)
    assert isinstance(result.retain_ml, bool)
    assert isinstance(result.reason, str) and len(result.reason) > 0
    assert result.rule_plus_ml.total_trades <= result.rule_based.total_trades
