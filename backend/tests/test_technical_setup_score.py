import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.scoring.technical_setup_score import TechnicalSetupScoreConfig, compute_technical_setup_score  # noqa: E402

CFG = TechnicalSetupScoreConfig()


def test_all_categories_available_perfect_bullish_setup():
    result = compute_technical_setup_score(
        close=110.0, ema_20=108.0, ema_50=105.0, ema_200=100.0,
        rsi=60.0,
        daily_relative_volume=1.5,
        return_20d_pct=15.0,
        stock_return_pct_for_relative_strength=15.0,
        nifty_return_pct_for_relative_strength=5.0,
        pct_from_52w_high=0.0,
        config=CFG,
    )
    assert result.total_score == pytest.approx(100.0, abs=0.5)
    assert result.unavailable_categories == []


def test_trend_category_hand_computed_partial_alignment():
    result = compute_technical_setup_score(
        close=110.0, ema_20=108.0, ema_50=105.0, ema_200=112.0,
        rsi=None, daily_relative_volume=None, return_20d_pct=None,
        stock_return_pct_for_relative_strength=None, nifty_return_pct_for_relative_strength=None,
        pct_from_52w_high=None, config=CFG,
    )
    trend = next(c for c in result.categories if c.name == "trend")
    assert trend.available is True
    assert trend.score == pytest.approx((2 / 3) * CFG.trend_weight)


def test_momentum_linear_scaling_hand_computed():
    result = compute_technical_setup_score(
        close=100.0, ema_20=None, ema_50=None, ema_200=None, rsi=None, daily_relative_volume=None,
        return_20d_pct=5.0, stock_return_pct_for_relative_strength=None,
        nifty_return_pct_for_relative_strength=None, pct_from_52w_high=None, config=CFG,
    )
    momentum = next(c for c in result.categories if c.name == "momentum")
    assert momentum.score == pytest.approx(0.5 * CFG.momentum_weight)


def test_momentum_clips_below_floor_to_zero():
    result = compute_technical_setup_score(
        close=100.0, ema_20=None, ema_50=None, ema_200=None, rsi=None, daily_relative_volume=None,
        return_20d_pct=-20.0,
        stock_return_pct_for_relative_strength=None, nifty_return_pct_for_relative_strength=None,
        pct_from_52w_high=None, config=CFG,
    )
    momentum = next(c for c in result.categories if c.name == "momentum")
    assert momentum.score == pytest.approx(0.0)


def test_rsi_trapezoid_full_score_in_healthy_zone():
    result = compute_technical_setup_score(
        close=100.0, ema_20=None, ema_50=None, ema_200=None, rsi=55.0,
        daily_relative_volume=None, return_20d_pct=None,
        stock_return_pct_for_relative_strength=None, nifty_return_pct_for_relative_strength=None,
        pct_from_52w_high=None, config=CFG,
    )
    rsi_cat = next(c for c in result.categories if c.name == "rsi")
    assert rsi_cat.score == pytest.approx(CFG.rsi_weight)


def test_rsi_zero_when_extremely_overbought():
    result = compute_technical_setup_score(
        close=100.0, ema_20=None, ema_50=None, ema_200=None, rsi=95.0,
        daily_relative_volume=None, return_20d_pct=None,
        stock_return_pct_for_relative_strength=None, nifty_return_pct_for_relative_strength=None,
        pct_from_52w_high=None, config=CFG,
    )
    rsi_cat = next(c for c in result.categories if c.name == "rsi")
    assert rsi_cat.score == pytest.approx(0.0)


def test_missing_categories_marked_unavailable_and_rescaled():
    result = compute_technical_setup_score(
        close=110.0, ema_20=108.0, ema_50=105.0, ema_200=100.0,
        rsi=None, daily_relative_volume=None, return_20d_pct=None,
        stock_return_pct_for_relative_strength=None, nifty_return_pct_for_relative_strength=None,
        pct_from_52w_high=None,
        config=CFG,
    )
    assert set(result.unavailable_categories) == {"momentum", "volume", "rsi", "relative_strength", "breakout_52week"}
    assert result.total_score == pytest.approx(100.0)


def test_all_categories_unavailable_gives_zero_not_a_crash():
    result = compute_technical_setup_score(
        close=100.0, ema_20=None, ema_50=None, ema_200=None, rsi=None, daily_relative_volume=None,
        return_20d_pct=None, stock_return_pct_for_relative_strength=None,
        nifty_return_pct_for_relative_strength=None, pct_from_52w_high=None, config=CFG,
    )
    assert result.total_score == pytest.approx(0.0)
    assert len(result.unavailable_categories) == 6


def test_relative_strength_uses_outperformance_not_raw_return():
    result = compute_technical_setup_score(
        close=100.0, ema_20=None, ema_50=None, ema_200=None, rsi=None, daily_relative_volume=None,
        return_20d_pct=5.0, stock_return_pct_for_relative_strength=5.0,
        nifty_return_pct_for_relative_strength=10.0, pct_from_52w_high=None, config=CFG,
    )
    relative_strength = next(c for c in result.categories if c.name == "relative_strength")
    assert relative_strength.score == pytest.approx(0.0)
    momentum = next(c for c in result.categories if c.name == "momentum")
    assert momentum.score > 0


def test_config_weights_must_be_non_negative():
    with pytest.raises(ValueError):
        TechnicalSetupScoreConfig(trend_weight=-5.0).validate()


def test_config_weights_cannot_all_be_zero():
    with pytest.raises(ValueError):
        TechnicalSetupScoreConfig(
            trend_weight=0, momentum_weight=0, volume_weight=0, rsi_weight=0,
            relative_strength_weight=0, breakout_52week_weight=0,
        ).validate()


def test_weights_are_configurable_and_change_the_total():
    custom = TechnicalSetupScoreConfig(trend_weight=100.0, momentum_weight=0, volume_weight=0, rsi_weight=0, relative_strength_weight=0, breakout_52week_weight=0)
    result = compute_technical_setup_score(
        close=110.0, ema_20=108.0, ema_50=105.0, ema_200=100.0,
        rsi=None, daily_relative_volume=None, return_20d_pct=None,
        stock_return_pct_for_relative_strength=None, nifty_return_pct_for_relative_strength=None,
        pct_from_52w_high=None, config=custom,
    )
    assert result.total_score == pytest.approx(100.0)
