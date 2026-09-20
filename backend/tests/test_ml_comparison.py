import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.backtesting.metrics import BacktestReport  # noqa: E402
from app.backtesting.trade_record import TradeRecord  # noqa: E402
from app.ml.comparison import compare_rule_vs_ml, should_retain_ml  # noqa: E402
from app.ml.features import FEATURE_NAMES  # noqa: E402
from app.ml.labels import TrainingExample  # noqa: E402
from app.ml.model import MLModel  # noqa: E402


def make_report(total_trades, expectancy):
    return BacktestReport(
        total_trades=total_trades, winning_trades=0, losing_trades=0, win_rate=None,
        average_win=None, average_loss=None, profit_factor=None, max_drawdown=0.0,
        average_r=None, expectancy=expectancy, total_pnl=expectancy * total_trades if expectancy else 0.0,
    )


def test_should_retain_ml_when_expectancy_improves_with_enough_trades():
    rule = make_report(total_trades=50, expectancy=100.0)
    ml = make_report(total_trades=20, expectancy=150.0)
    retain, reason = should_retain_ml(rule, ml, min_trades=10)
    assert retain is True
    assert "exceeds" in reason


def test_should_not_retain_ml_when_expectancy_does_not_improve():
    rule = make_report(total_trades=50, expectancy=100.0)
    ml = make_report(total_trades=20, expectancy=80.0)
    retain, reason = should_retain_ml(rule, ml, min_trades=10)
    assert retain is False
    assert "does not exceed" in reason


def test_should_not_retain_ml_when_too_few_filtered_trades():
    rule = make_report(total_trades=50, expectancy=100.0)
    ml = make_report(total_trades=3, expectancy=500.0)  # looks great, but too few trades to trust
    retain, reason = should_retain_ml(rule, ml, min_trades=10)
    assert retain is False
    assert "not enough" in reason.lower()


def test_should_not_retain_ml_when_expectancy_undefined():
    rule = make_report(total_trades=0, expectancy=None)
    ml = make_report(total_trades=20, expectancy=100.0)
    retain, reason = should_retain_ml(rule, ml, min_trades=10)
    assert retain is False


def make_trade(entry_time, net_pnl, symbol="TEST"):
    return TradeRecord(
        symbol=symbol, direction="LONG", entry_time=entry_time, entry_price_theoretical=100.0,
        entry_price_filled=100.1, stop_price=95.0, target_price=110.0, quantity=10,
        exit_time=entry_time + 1, exit_price_theoretical=105.0, exit_price_filled=104.9,
        exit_reason="TARGET_HIT" if net_pnl > 0 else "STOP_LOSS_HIT",
        gross_pnl=net_pnl, charges=0.0, net_pnl=net_pnl, r_multiple=net_pnl / 100,
    )


def make_example(entry_time, opportunity_score, label, symbol="TEST"):
    features = {name: 0.0 for name in FEATURE_NAMES}
    features["opportunity_score"] = opportunity_score
    return TrainingExample(symbol=symbol, entry_time=entry_time, features=features, label=label)


def test_compare_rule_vs_ml_end_to_end_on_a_clean_separable_case():
    """A synthetic scenario where the ML model should correctly learn to
    filter OUT the low-score losing trades, improving expectancy on the
    held-out test set - proving the comparison machinery itself works
    correctly (this is a plumbing test, not evidence that ML helps on
    real trading data - see comparison.py's module docstring)."""
    train_examples = []
    for i in range(40):
        score = 85.0 if i % 2 == 0 else 20.0
        label = 1 if i % 2 == 0 else 0
        train_examples.append(make_example(i, score, label))

    model = MLModel()
    model.fit(train_examples)

    test_trades = []
    test_examples = []
    for i in range(100, 130):
        favorable = i % 2 == 0
        score = 85.0 if favorable else 20.0
        pnl = 500.0 if favorable else -500.0
        test_trades.append(make_trade(i, pnl))
        test_examples.append(make_example(i, score, 1 if favorable else 0))

    result = compare_rule_vs_ml(test_trades, test_examples, model, probability_threshold=0.5, min_trades_for_decision=5)

    assert result.rule_based.total_trades == 30
    assert result.rule_plus_ml.total_trades <= result.rule_based.total_trades
    assert result.rule_plus_ml.expectancy > result.rule_based.expectancy
    assert result.retain_ml is True


def test_compare_rule_vs_ml_excludes_trades_without_matching_features():
    train_examples = [make_example(i, 80.0, 1) for i in range(10)]
    model = MLModel()
    model.fit(train_examples + [make_example(i, 20.0, 0) for i in range(10, 20)])

    test_trades = [make_trade(1, 100.0), make_trade(2, 100.0)]
    test_examples = [make_example(1, 80.0, 1)]  # no example for trade at entry_time=2

    result = compare_rule_vs_ml(test_trades, test_examples, model, min_trades_for_decision=1)
    assert result.rule_based.total_trades == 1  # only the matched trade counted
