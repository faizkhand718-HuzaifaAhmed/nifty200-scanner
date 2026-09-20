import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.scoring.engine import OpportunityScoringEngine  # noqa: E402
from app.scoring.explanation import generate_explanation  # noqa: E402


def make_long_favorable_row():
    """Hand-computed to total EXACTLY 64.5/100 using default weights and
    default normalization constants:
      trend    = 0.5*((30-20)/20) + 0.5*1.0        = 0.75 -> 15.0/20
      volume   = 0.5*((1.5-1)/1)  + 0.5*1.0        = 0.75 -> 11.25/15
      vwap     = (0.004/0.005)                      = 0.8  -> 12.0/15
      momentum = 1-|72.5-65|/15                     = 0.5  -> 5.0/10
      ema      = (1+0)/2                            = 0.5  -> 5.0/10
      breakout = 0.5*1 + 0.5*0                       = 0.5  -> 5.0/10
      market   = 1.0 * (15/30)                      = 0.5  -> 5.0/10
      rel_str  = 0.015/0.03                          = 0.5  -> 2.5/5
      risk     = 1-|0.01-0.008|/0.008                = 0.75 -> 3.75/5
      total = 15+11.25+12+5+5+5+5+2.5+3.75 = 64.5
    """
    indicators_df = pd.DataFrame(
        {
            "timestamp": [1],
            "close": [100.4],
            "vwap": [100.0],
            "atr": [1.004],
            "rsi": [72.5],
            "adx": [30.0],
            "plus_di": [25.0],
            "minus_di": [10.0],
            "relative_volume": [1.5],
            "relative_strength": [0.015],
        }
    )
    setup_df = pd.DataFrame(
        {
            "timestamp": [1],
            "long_ema9_above_ema20": [True],
            "long_ema20_above_ema50": [False],
            "long_price_structure": [True],
            "long_volume_confirmation": [True],
            "long_breakout": [True],
            "long_retest": [False],
            "long_market_confirmation": [True],
            "short_ema9_below_ema20": [False],
            "short_ema20_below_ema50": [False],
            "short_price_structure": [False],
            "short_breakdown": [False],
            "short_retest": [False],
            "short_market_confirmation": [False],
        }
    )
    nifty_df = pd.DataFrame({"timestamp": [1], "adx": [15.0]})
    return indicators_df, setup_df, nifty_df


def make_short_favorable_row():
    """Mirror hand-computation, also totalling 64.5/100:
      trend    = 0.5*((30-20)/20) + 0.5*1.0         = 0.75 -> 15.0/20
      volume   = 0.5*((1.5-1)/1)  + 0.5*1.0         = 0.75 -> 11.25/15
      vwap     = (0.004/0.005)                       = 0.8  -> 12.0/15
      momentum (bearish zone 20-50, mid=35, half=15): rsi=27.5 -> 1-7.5/15=0.5 -> 5.0/10
      ema      = (1+0)/2                             = 0.5  -> 5.0/10
      breakdown= 0.5*1 + 0.5*0                        = 0.5  -> 5.0/10
      market   = 1.0*(15/30)                         = 0.5  -> 5.0/10
      rel_str  = 0.015/0.03 (sign-flipped)            = 0.5  -> 2.5/5
      risk     = 0.75                                 -> 3.75/5
      total = 64.5
    """
    indicators_df = pd.DataFrame(
        {
            "timestamp": [1],
            "close": [99.6],
            "vwap": [100.0],
            "atr": [0.996],
            "rsi": [27.5],
            "adx": [30.0],
            "plus_di": [10.0],
            "minus_di": [25.0],
            "relative_volume": [1.5],
            "relative_strength": [-0.015],
        }
    )
    setup_df = pd.DataFrame(
        {
            "timestamp": [1],
            "long_ema9_above_ema20": [False],
            "long_ema20_above_ema50": [False],
            "long_price_structure": [False],
            "long_volume_confirmation": [True],
            "long_breakout": [False],
            "long_retest": [False],
            "long_market_confirmation": [False],
            "short_ema9_below_ema20": [True],
            "short_ema20_below_ema50": [False],
            "short_price_structure": [True],
            "short_breakdown": [True],
            "short_retest": [False],
            "short_market_confirmation": [True],
        }
    )
    nifty_df = pd.DataFrame({"timestamp": [1], "adx": [15.0]})
    return indicators_df, setup_df, nifty_df


def test_long_score_exact_hand_computed_total():
    indicators_df, setup_df, nifty_df = make_long_favorable_row()
    result = OpportunityScoringEngine().compute(indicators_df, setup_df, nifty_indicators_df=nifty_df)
    assert result["long_score"].iloc[0] == pytest.approx(64.5)
    assert result["long_score_max"].iloc[0] == pytest.approx(100.0)
    assert result["long_trend_score"].iloc[0] == pytest.approx(15.0)
    assert result["long_volume_score"].iloc[0] == pytest.approx(11.25)
    assert result["long_vwap_score"].iloc[0] == pytest.approx(12.0)
    assert result["long_momentum_score"].iloc[0] == pytest.approx(5.0)
    assert result["long_ema_structure_score"].iloc[0] == pytest.approx(5.0)
    assert result["long_breakout_score"].iloc[0] == pytest.approx(5.0)
    assert result["long_market_confirmation_score"].iloc[0] == pytest.approx(5.0)
    assert result["long_relative_strength_score"].iloc[0] == pytest.approx(2.5)
    assert result["long_risk_score"].iloc[0] == pytest.approx(3.75)


def test_short_score_exact_hand_computed_total():
    indicators_df, setup_df, nifty_df = make_short_favorable_row()
    result = OpportunityScoringEngine().compute(indicators_df, setup_df, nifty_indicators_df=nifty_df)
    assert result["short_score"].iloc[0] == pytest.approx(64.5)
    assert result["short_score_max"].iloc[0] == pytest.approx(100.0)


def test_category_scores_sum_to_total():
    indicators_df, setup_df, nifty_df = make_long_favorable_row()
    result = OpportunityScoringEngine().compute(indicators_df, setup_df, nifty_indicators_df=nifty_df)
    categories = ["trend", "volume", "vwap", "momentum", "ema_structure", "breakout", "market_confirmation", "relative_strength", "risk"]
    category_sum = sum(result[f"long_{c}_score"].iloc[0] for c in categories)
    assert category_sum == pytest.approx(result["long_score"].iloc[0])


def test_perfect_setup_scores_100():
    indicators_df = pd.DataFrame(
        {
            "timestamp": [1], "close": [101.0], "vwap": [100.0], "atr": [0.808], "rsi": [65.0],
            "adx": [40.0], "plus_di": [30.0], "minus_di": [5.0], "relative_volume": [2.0],
            "relative_strength": [0.03],
        }
    )
    setup_df = pd.DataFrame(
        {
            "timestamp": [1], "long_ema9_above_ema20": [True], "long_ema20_above_ema50": [True],
            "long_price_structure": [True], "long_volume_confirmation": [True],
            "long_breakout": [True], "long_retest": [True], "long_market_confirmation": [True],
            "short_ema9_below_ema20": [False], "short_ema20_below_ema50": [False],
            "short_price_structure": [False], "short_breakdown": [False], "short_retest": [False],
            "short_market_confirmation": [False],
        }
    )
    nifty_df = pd.DataFrame({"timestamp": [1], "adx": [30.0]})
    result = OpportunityScoringEngine().compute(indicators_df, setup_df, nifty_indicators_df=nifty_df)
    assert result["long_score"].iloc[0] == pytest.approx(100.0)


def test_zero_setup_scores_0():
    indicators_df = pd.DataFrame(
        {
            "timestamp": [1], "close": [90.0], "vwap": [100.0], "atr": [5.0], "rsi": [20.0],
            "adx": [5.0], "plus_di": [5.0], "minus_di": [30.0], "relative_volume": [0.5],
            "relative_strength": [-0.05],
        }
    )
    setup_df = pd.DataFrame(
        {
            "timestamp": [1], "long_ema9_above_ema20": [False], "long_ema20_above_ema50": [False],
            "long_price_structure": [False], "long_volume_confirmation": [False],
            "long_breakout": [False], "long_retest": [False], "long_market_confirmation": [False],
            "short_ema9_below_ema20": [False], "short_ema20_below_ema50": [False],
            "short_price_structure": [False], "short_breakdown": [False], "short_retest": [False],
            "short_market_confirmation": [False],
        }
    )
    nifty_df = pd.DataFrame({"timestamp": [1], "adx": [5.0]})
    result = OpportunityScoringEngine().compute(indicators_df, setup_df, nifty_indicators_df=nifty_df)
    assert result["long_score"].iloc[0] == pytest.approx(0.0)


def test_missing_indicator_column_raises():
    indicators_df, setup_df, nifty_df = make_long_favorable_row()
    with pytest.raises(ValueError, match="indicators_df missing"):
        OpportunityScoringEngine().compute(indicators_df.drop(columns=["vwap"]), setup_df)


def test_missing_setup_column_raises():
    indicators_df, setup_df, nifty_df = make_long_favorable_row()
    with pytest.raises(ValueError, match="setup_df missing"):
        OpportunityScoringEngine().compute(indicators_df, setup_df.drop(columns=["long_breakout"]))


def test_misaligned_rows_raise():
    indicators_df, setup_df, nifty_df = make_long_favorable_row()
    misaligned_setup = setup_df.copy()
    misaligned_setup["timestamp"] = [2]  # doesn't match indicators_df's timestamp
    with pytest.raises(ValueError, match="row-aligned"):
        OpportunityScoringEngine().compute(indicators_df, misaligned_setup)


def test_relative_strength_and_market_confirmation_default_to_zero_when_absent():
    indicators_df, setup_df, _ = make_long_favorable_row()
    indicators_df = indicators_df.drop(columns=["relative_strength"])
    setup_df = setup_df.drop(columns=["long_market_confirmation", "short_market_confirmation"])
    result = OpportunityScoringEngine().compute(indicators_df, setup_df, nifty_indicators_df=None)
    assert result["long_relative_strength_score"].iloc[0] == pytest.approx(0.0)
    assert result["long_market_confirmation_score"].iloc[0] == pytest.approx(0.0)


def test_breakdown_format_matches_spec_style():
    indicators_df, setup_df, nifty_df = make_long_favorable_row()
    result = OpportunityScoringEngine().compute(indicators_df, setup_df, nifty_indicators_df=nifty_df)
    breakdown = OpportunityScoringEngine.breakdown(result.iloc[0], "long")
    assert breakdown["trend"] == "15.0/20"
    assert breakdown["volume"] == "11.2/15"  # 11.25 -> "11.2" (float repr rounds down here)
    assert breakdown["total"] == "64.5/100"


def test_explanation_uses_required_terminology_and_avoids_guarantees():
    indicators_df, setup_df, nifty_df = make_long_favorable_row()
    result = OpportunityScoringEngine().compute(indicators_df, setup_df, nifty_indicators_df=nifty_df)
    text = generate_explanation(result.iloc[0], "long")

    assert "Opportunity Score" in text
    assert "Setup Quality" in text
    assert "Signal Strength" in text
    forbidden = ["probability of profit", "guaranteed", "will win", "chance of winning", "sure thing"]
    lowered = text.lower()
    for phrase in forbidden:
        if phrase == "probability of profit":
            # the phrase legitimately appears, but only in a NEGATION
            assert "not a probability of profit" in lowered
        else:
            assert phrase not in lowered


def test_custom_weights_change_the_score():
    indicators_df, setup_df, nifty_df = make_long_favorable_row()
    from app.scoring.config import ScoringWeights

    default_result = OpportunityScoringEngine().compute(indicators_df, setup_df, nifty_indicators_df=nifty_df)
    heavy_trend = ScoringWeights(trend=80, volume=5, vwap=5, momentum=2, ema_structure=2, breakout=2, market_confirmation=2, relative_strength=1, risk=1)
    heavy_trend.validate()
    custom_result = OpportunityScoringEngine(weights=heavy_trend).compute(indicators_df, setup_df, nifty_indicators_df=nifty_df)

    assert custom_result["long_score"].iloc[0] != pytest.approx(default_result["long_score"].iloc[0])
