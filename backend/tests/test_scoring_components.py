import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.scoring import components as comp  # noqa: E402


def test_trend_score_hand_computed():
    # adx=30, adx_min=20, adx_full=40 -> strength_fraction=(30-20)/20=0.5
    # direction ok (plus_di>minus_di), structure confirmed=True -> 1.0
    # trend fraction = 0.5*0.5 + 0.5*1.0 = 0.75
    adx = pd.Series([30.0])
    plus_di = pd.Series([25.0])
    minus_di = pd.Series([10.0])
    structure = pd.Series([True])
    result = comp.trend_score(adx, plus_di, minus_di, structure, adx_min=20.0, adx_full=40.0, bullish=True)
    assert result.iloc[0] == pytest.approx(0.75)


def test_trend_score_zero_when_direction_wrong():
    adx = pd.Series([30.0])
    plus_di = pd.Series([10.0])
    minus_di = pd.Series([25.0])  # wrong direction for bullish
    structure = pd.Series([True])
    result = comp.trend_score(adx, plus_di, minus_di, structure, adx_min=20.0, adx_full=40.0, bullish=True)
    # strength component drops to 0, only structure half remains = 0.5
    assert result.iloc[0] == pytest.approx(0.5)


def test_vwap_score_hand_computed():
    # close=100.4, vwap=100 -> distance_pct=0.004 ; full=0.005 -> 0.8
    close = pd.Series([100.4])
    vwap = pd.Series([100.0])
    result = comp.vwap_score(close, vwap, distance_full_pct=0.005, bullish=True)
    assert result.iloc[0] == pytest.approx(0.8)


def test_vwap_score_zero_when_below_for_bullish():
    close = pd.Series([99.0])
    vwap = pd.Series([100.0])
    result = comp.vwap_score(close, vwap, distance_full_pct=0.005, bullish=True)
    assert result.iloc[0] == pytest.approx(0.0)


def test_momentum_score_peaks_at_zone_center():
    # zone 50-80, mid=65, half=15
    rsi = pd.Series([65.0, 72.5, 50.0, 80.0, 90.0, 40.0])
    result = comp.momentum_score(rsi, zone_min=50.0, zone_max=80.0)
    assert result.iloc[0] == pytest.approx(1.0)   # exact center
    assert result.iloc[1] == pytest.approx(0.5)   # 7.5 off-center of 15 half-width
    assert result.iloc[2] == pytest.approx(0.0)   # at zone edge
    assert result.iloc[3] == pytest.approx(0.0)   # at other edge
    assert result.iloc[4] == pytest.approx(0.0)   # outside zone, clipped
    assert result.iloc[5] == pytest.approx(0.0)   # outside zone, clipped


def test_ema_structure_score_counts_conditions():
    cond1 = pd.Series([True, True, False, False])
    cond2 = pd.Series([True, False, True, False])
    result = comp.ema_structure_score(cond1, cond2)
    assert list(result) == pytest.approx([1.0, 0.5, 0.5, 0.0])


def test_volume_score_hand_computed():
    # relative_volume=1.5, full=2.0 -> rel_fraction=(1.5-1)/(2-1)=0.5
    # above_average=True -> avg_fraction=1.0 ; combined=0.5*0.5+0.5*1=0.75
    volume_above_avg = pd.Series([True])
    relative_volume = pd.Series([1.5])
    result = comp.volume_score(volume_above_avg, relative_volume, relative_volume_full=2.0)
    assert result.iloc[0] == pytest.approx(0.75)


def test_breakout_score_hand_computed():
    breakout = pd.Series([True, False, True, False])
    retest = pd.Series([False, True, True, False])
    result = comp.breakout_score(breakout, retest)
    assert list(result) == pytest.approx([0.5, 0.5, 1.0, 0.0])


def test_market_confirmation_score_hand_computed():
    # direction confirmed=True, nifty_adx=15, full=30 -> strength=0.5 -> 0.5
    direction = pd.Series([True])
    nifty_adx = pd.Series([15.0])
    result = comp.market_confirmation_score(direction, nifty_adx, nifty_adx_full=30.0)
    assert result.iloc[0] == pytest.approx(0.5)


def test_market_confirmation_score_zero_when_none():
    nifty_adx = pd.Series([15.0, 20.0])
    result = comp.market_confirmation_score(None, nifty_adx, nifty_adx_full=30.0)
    assert list(result) == [0.0, 0.0]


def test_relative_strength_score_hand_computed():
    # relative_strength=0.015, full=0.03 -> 0.5 (bullish)
    rs = pd.Series([0.015])
    result = comp.relative_strength_score(rs, full=0.03, bullish=True, index=rs.index)
    assert result.iloc[0] == pytest.approx(0.5)

    # SHORT: relative_strength=-0.015 -> value flips sign -> 0.5
    rs_short = pd.Series([-0.015])
    result_short = comp.relative_strength_score(rs_short, full=0.03, bullish=False, index=rs_short.index)
    assert result_short.iloc[0] == pytest.approx(0.5)


def test_relative_strength_score_zero_when_none():
    idx = pd.RangeIndex(2)
    result = comp.relative_strength_score(None, full=0.03, bullish=True, index=idx)
    assert list(result) == [0.0, 0.0]


def test_risk_score_hand_computed():
    # atr=1.0, close=100 -> atr_pct=0.01 ; ideal=0.008, tolerance=0.008
    # diff=0.002 -> fraction=1-0.002/0.008=0.75
    atr = pd.Series([1.0])
    close = pd.Series([100.0])
    result = comp.risk_score(atr, close, ideal_atr_pct=0.008, tolerance_pct=0.008)
    assert result.iloc[0] == pytest.approx(0.75)


def test_risk_score_peaks_at_ideal():
    atr = pd.Series([0.8])
    close = pd.Series([100.0])  # atr_pct exactly 0.008 = ideal
    result = comp.risk_score(atr, close, ideal_atr_pct=0.008, tolerance_pct=0.008)
    assert result.iloc[0] == pytest.approx(1.0)


def test_all_component_functions_handle_nan_as_zero_credit():
    nan_series = pd.Series([float("nan")])
    bool_series = pd.Series([True])
    assert comp.vwap_score(nan_series, pd.Series([100.0]), 0.005, True).iloc[0] == 0.0
    assert comp.momentum_score(nan_series, 50.0, 80.0).iloc[0] == 0.0
    assert comp.risk_score(nan_series, pd.Series([100.0]), 0.008, 0.008).iloc[0] == 0.0
