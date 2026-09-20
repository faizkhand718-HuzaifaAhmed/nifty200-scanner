"""
Compares the existing rule-based strategy against "rule + ML" (the rule-
based trade set additionally filtered by the ML model's predicted win
probability) on HELD-OUT test-set trades only - never on train or
validation data, which would overstate the ML model's real benefit.

REMINDER: the ML probability is an additional FEATURE for filtering, not
a guaranteed outcome - "rule + ML" here means "trades the rules already
generated, further filtered to ones the model also finds favorable," not
"trades the ML invented on its own." A trade the rules never generated is
never considered, regardless of what the model would have predicted for it.

THE DECISION RULE IS DELIBERATELY CONSERVATIVE: ML is retained only if it
demonstrably improves out-of-sample expectancy AND there are enough
filtered trades to trust the comparison isn't noise. On this project's own
synthetic (random-walk) mock data, the honest, EXPECTED result is that ML
does NOT improve performance - that is not a bug in this module, it is
the correct outcome of testing a model against data with no genuine
predictive structure. Do not be surprised or worried if that's what you see.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from app.backtesting.metrics import BacktestReport, compute_report
from app.backtesting.trade_record import TradeRecord
from app.ml.labels import TrainingExample
from app.ml.model import MLModel


@dataclass
class StrategyComparisonResult:
    rule_based: BacktestReport
    rule_plus_ml: BacktestReport
    ml_probability_threshold: float
    retain_ml: bool
    reason: str


def should_retain_ml(rule_report: BacktestReport, ml_report: BacktestReport, min_trades: int = 10) -> Tuple[bool, str]:
    if ml_report.total_trades < min_trades:
        return False, (
            f"only {ml_report.total_trades} ML-filtered trades in the test set "
            f"(need at least {min_trades}) - not enough out-of-sample evidence either way"
        )
    if rule_report.expectancy is None or ml_report.expectancy is None:
        return False, "expectancy is undefined for one of the strategies - cannot compare"
    if ml_report.expectancy > rule_report.expectancy:
        return True, (
            f"ML-filtered expectancy ({ml_report.expectancy:.2f}) exceeds rule-based "
            f"expectancy ({rule_report.expectancy:.2f}) on the held-out test set"
        )
    return False, (
        f"ML-filtered expectancy ({ml_report.expectancy:.2f}) does not exceed rule-based "
        f"expectancy ({rule_report.expectancy:.2f}) on the held-out test set - do not retain ML"
    )


def compare_rule_vs_ml(
    test_trades: List[TradeRecord],
    test_examples: List[TrainingExample],
    model: MLModel,
    probability_threshold: float = 0.5,
    min_trades_for_decision: int = 10,
) -> StrategyComparisonResult:
    """
    `test_trades` and `test_examples` must come from the SAME held-out
    test period. They're aligned here by (symbol, entry_time) - a trade
    without a matching feature example (e.g. dropped during feature
    extraction) is excluded from BOTH strategies, so the comparison is
    always apples-to-apples on the exact same trade set.
    """
    example_by_key = {(ex.symbol, ex.entry_time): ex for ex in test_examples}

    aligned_trades = []
    aligned_examples = []
    for trade in test_trades:
        example = example_by_key.get((trade.symbol, trade.entry_time))
        if example is not None:
            aligned_trades.append(trade)
            aligned_examples.append(example)

    probabilities = model.predict_proba(aligned_examples) if aligned_examples else []

    rule_report = compute_report(aligned_trades)
    ml_filtered_trades = [t for t, p in zip(aligned_trades, probabilities) if p >= probability_threshold]
    ml_report = compute_report(ml_filtered_trades)

    retain, reason = should_retain_ml(rule_report, ml_report, min_trades_for_decision)

    return StrategyComparisonResult(
        rule_based=rule_report,
        rule_plus_ml=ml_report,
        ml_probability_threshold=probability_threshold,
        retain_ml=retain,
        reason=reason,
    )
