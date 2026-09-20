import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.setup_detection import conditions as cond  # noqa: E402


def test_above_below_vwap():
    close = pd.Series([100.0, 100.0, 100.0])
    vwap = pd.Series([99.0, 100.0, 101.0])
    assert list(cond.above_vwap(close, vwap)) == [True, False, False]
    assert list(cond.below_vwap(close, vwap)) == [False, False, True]


def test_ema_alignment():
    fast = pd.Series([10.0, 10.0, 10.0])
    slow = pd.Series([9.0, 10.0, 11.0])
    assert list(cond.ema_bullish_alignment(fast, slow)) == [True, False, False]
    assert list(cond.ema_bearish_alignment(fast, slow)) == [False, False, True]


def test_rsi_in_zone():
    rsi = pd.Series([40.0, 50.0, 65.0, 80.0, 90.0])
    result = cond.rsi_in_zone(rsi, low=50.0, high=80.0)
    assert list(result) == [False, True, True, True, False]


def test_rsi_in_zone_rejects_invalid_bounds():
    with pytest.raises(ValueError):
        cond.rsi_in_zone(pd.Series([50.0]), low=80.0, high=50.0)


def test_adx_bullish_and_bearish():
    adx = pd.Series([15.0, 25.0, 25.0])
    plus_di = pd.Series([30.0, 30.0, 10.0])
    minus_di = pd.Series([10.0, 10.0, 30.0])
    # row0: adx too low -> False regardless of DI
    # row1: adx>=20 and +DI>-DI -> bullish True
    # row2: adx>=20 but -DI>+DI -> bullish False, bearish True
    assert list(cond.adx_bullish(adx, plus_di, minus_di, adx_min=20.0)) == [False, True, False]
    assert list(cond.adx_bearish(adx, plus_di, minus_di, adx_min=20.0)) == [False, False, True]


def test_volume_and_relative_volume():
    volume = pd.Series([100, 200, 50])
    avg_volume = pd.Series([150, 150, 150])
    assert list(cond.volume_above_average(volume, avg_volume)) == [False, True, False]

    rel_vol = pd.Series([0.8, 1.2, 1.5])
    assert list(cond.relative_volume_confirmed(rel_vol, minimum=1.2)) == [False, True, True]


def test_relative_strength_bullish_and_bearish():
    rs = pd.Series([-0.05, 0.0, 0.05])
    assert list(cond.relative_strength_bullish(rs, minimum=0.0)) == [False, False, True]
    assert list(cond.relative_strength_bearish(rs, minimum=0.0)) == [True, False, False]


def test_market_direction():
    fast = pd.Series([100.0, 100.0])
    slow = pd.Series([99.0, 101.0])
    assert list(cond.market_direction_bullish(fast, slow)) == [True, False]
    assert list(cond.market_direction_bearish(fast, slow)) == [False, True]


def test_nan_inputs_never_evaluate_true():
    """A missing indicator value must never be silently treated as a
    passing condition."""
    close = pd.Series([100.0])
    vwap = pd.Series([float("nan")])
    assert cond.above_vwap(close, vwap).iloc[0] == False
    assert cond.below_vwap(close, vwap).iloc[0] == False
