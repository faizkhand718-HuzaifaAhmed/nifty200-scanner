import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ranking.config import RankingConfig  # noqa: E402
from app.ranking.engine import RankingEngine, SymbolSnapshot  # noqa: E402

CATEGORY_WEIGHTS = {
    "trend": 20, "volume": 15, "vwap": 15, "momentum": 10, "ema_structure": 10,
    "breakout": 10, "market_confirmation": 10, "relative_strength": 5, "risk": 5,
}


def make_scoring_row(long_score: float, short_score: float) -> pd.Series:
    row = {"long_score": long_score, "long_score_max": 100.0, "short_score": short_score, "short_score_max": 100.0}
    for cat, w in CATEGORY_WEIGHTS.items():
        row[f"long_{cat}_score"] = 0.0
        row[f"long_{cat}_max"] = w
        row[f"short_{cat}_score"] = 0.0
        row[f"short_{cat}_max"] = w
    return pd.Series(row)


def make_indicators_row(
    close=100.0, atr=1.0, rsi=55.0, adx=25.0, relative_volume=1.0, prev_day_close=98.0,
    support=None, resistance=None, r1=None, r2=None, r3=None, s1=None, s2=None, s3=None,
) -> pd.Series:
    return pd.Series(
        {
            "close": close, "atr": atr, "rsi": rsi, "adx": adx, "relative_volume": relative_volume,
            "prev_day_close": prev_day_close, "support": support, "resistance": resistance,
            "r1": r1, "r2": r2, "r3": r3, "s1": s1, "s2": s2, "s3": s3,
        }
    )


def make_setup_row(long_breakout=False, long_retest=False, short_breakdown=False, short_retest=False) -> pd.Series:
    return pd.Series(
        {
            "long_breakout": long_breakout, "long_retest": long_retest,
            "short_breakdown": short_breakdown, "short_retest": short_retest,
        }
    )


def test_direction_long_when_long_score_higher_and_above_threshold():
    snap = SymbolSnapshot("AAA", make_indicators_row(), make_setup_row(), make_scoring_row(60.0, 30.0))
    result = RankingEngine().rank([snap])
    assert result.loc[0, "direction"] == "LONG"
    assert result.loc[0, "opportunity_score"] == pytest.approx(60.0)


def test_direction_short_when_short_score_higher():
    snap = SymbolSnapshot("AAA", make_indicators_row(), make_setup_row(), make_scoring_row(20.0, 55.0))
    result = RankingEngine().rank([snap])
    assert result.loc[0, "direction"] == "SHORT"
    assert result.loc[0, "opportunity_score"] == pytest.approx(55.0)


def test_direction_none_when_leading_score_below_min_valid():
    snap = SymbolSnapshot("AAA", make_indicators_row(), make_setup_row(), make_scoring_row(30.0, 20.0))
    result = RankingEngine().rank([snap])
    assert result.loc[0, "direction"] == "NONE"
    # score is still shown for context, not hidden
    assert result.loc[0, "opportunity_score"] == pytest.approx(30.0)


def test_entry_status_ready_requires_score_and_breakout_or_retest():
    snap_with_breakout = SymbolSnapshot(
        "AAA", make_indicators_row(), make_setup_row(long_breakout=True), make_scoring_row(75.0, 10.0)
    )
    result = RankingEngine().rank([snap_with_breakout])
    assert result.loc[0, "entry_status"] == "READY"

    snap_without_breakout = SymbolSnapshot(
        "BBB", make_indicators_row(), make_setup_row(), make_scoring_row(75.0, 10.0)
    )
    result2 = RankingEngine().rank([snap_without_breakout])
    assert result2.loc[0, "entry_status"] == "WATCH"  # high score alone isn't enough for READY


def test_entry_status_watch_band():
    snap = SymbolSnapshot("AAA", make_indicators_row(), make_setup_row(), make_scoring_row(55.0, 10.0))
    result = RankingEngine().rank([snap])
    assert result.loc[0, "entry_status"] == "WATCH"


def test_entry_status_none_when_valid_direction_but_score_too_low_to_watch():
    # min_valid_score=40 default, watch_score_threshold=50 default:
    # a score of 45 is a valid direction but not yet watch-worthy.
    snap = SymbolSnapshot("AAA", make_indicators_row(), make_setup_row(), make_scoring_row(45.0, 10.0))
    result = RankingEngine().rank([snap])
    assert result.loc[0, "direction"] == "LONG"
    assert result.loc[0, "entry_status"] == "NONE"


def test_tie_break_by_relative_volume_then_symbol():
    snap_a = SymbolSnapshot(
        "ZZZ", make_indicators_row(relative_volume=2.0), make_setup_row(), make_scoring_row(60.0, 10.0)
    )
    snap_b = SymbolSnapshot(
        "AAA", make_indicators_row(relative_volume=1.0), make_setup_row(), make_scoring_row(60.0, 10.0)
    )
    snap_c = SymbolSnapshot(
        "BBB", make_indicators_row(relative_volume=2.0), make_setup_row(), make_scoring_row(60.0, 10.0)
    )
    result = RankingEngine().rank([snap_a, snap_b, snap_c])
    # ZZZ and BBB tie on score AND relative_volume(2.0) -> alphabetical: BBB before ZZZ
    # AAA has lower relative_volume(1.0) despite same score -> ranked last
    assert list(result["symbol"]) == ["BBB", "ZZZ", "AAA"]
    assert list(result["rank"]) == [1, 2, 3]


def test_change_pct_calculated_from_prev_day_close():
    snap = SymbolSnapshot(
        "AAA", make_indicators_row(close=102.0, prev_day_close=100.0), make_setup_row(), make_scoring_row(50.0, 10.0)
    )
    result = RankingEngine().rank([snap])
    assert result.loc[0, "change_pct"] == pytest.approx(2.0)


def test_change_pct_none_when_prev_day_close_missing():
    snap = SymbolSnapshot(
        "AAA", make_indicators_row(prev_day_close=float("nan")), make_setup_row(), make_scoring_row(50.0, 10.0)
    )
    result = RankingEngine().rank([snap])
    assert result.loc[0, "change_pct"] is None


def test_risk_reward_included_when_levels_available():
    snap = SymbolSnapshot(
        "AAA",
        make_indicators_row(close=102.0, atr=1.0, support=98.0, r1=110.0),
        make_setup_row(),
        make_scoring_row(60.0, 10.0),
    )
    result = RankingEngine().rank([snap])
    assert result.loc[0, "risk_reward"] == pytest.approx(2.0)  # (110-102)/(102-98)
    assert result.loc[0, "stop_loss"] == pytest.approx(98.0)
    assert result.loc[0, "target"] == pytest.approx(110.0)
    assert result.loc[0, "entry_price"] == pytest.approx(102.0)


def test_rank_empty_list_returns_empty_dataframe_with_expected_columns():
    result = RankingEngine().rank([])
    assert result.empty
    assert "rank" in result.columns
    assert "symbol" in result.columns


def test_custom_config_changes_thresholds():
    lenient = RankingConfig(min_valid_score=10.0, watch_score_threshold=20.0, ready_score_threshold=30.0)
    snap = SymbolSnapshot("AAA", make_indicators_row(), make_setup_row(), make_scoring_row(25.0, 5.0))
    result = RankingEngine(config=lenient).rank([snap])
    assert result.loc[0, "direction"] == "LONG"
    assert result.loc[0, "entry_status"] == "WATCH"


def test_setup_explanation_present_and_non_empty():
    snap = SymbolSnapshot("AAA", make_indicators_row(), make_setup_row(), make_scoring_row(60.0, 10.0))
    result = RankingEngine().rank([snap])
    assert isinstance(result.loc[0, "setup_explanation"], str)
    assert "Opportunity Score" in result.loc[0, "setup_explanation"]
