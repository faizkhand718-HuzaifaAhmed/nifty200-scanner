import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.features import extract_features, realized_volatility  # noqa: E402


def make_rows(direction="LONG"):
    ind = pd.Series({
        "close": 101.0, "vwap": 100.0, "ema_9": 102.0, "ema_20": 100.0, "ema_50": 98.0,
        "rsi": 65.0, "adx": 25.0, "atr": 2.0, "relative_volume": 1.5, "relative_strength": 0.02,
    })
    setup = pd.Series({"long_breakout": True, "short_breakdown": False})
    scoring = pd.Series({"long_score": 78.0, "short_score": 20.0})
    return ind, setup, scoring


def test_extract_features_long_hand_computed():
    ind, setup, scoring = make_rows()
    features = extract_features(ind, setup, scoring, "LONG", realized_vol=0.01)

    assert features is not None
    assert features["vwap_distance"] == pytest.approx((101.0 - 100.0) / 100.0)
    assert features["ema_9_20_pct"] == pytest.approx((102.0 - 100.0) / 100.0)
    assert features["ema_20_50_pct"] == pytest.approx((100.0 - 98.0) / 98.0)
    assert features["rsi_favorable"] == pytest.approx(65.0)  # LONG: RSI as-is
    assert features["adx"] == pytest.approx(25.0)
    assert features["atr_pct"] == pytest.approx(2.0 / 101.0)
    assert features["relative_volume"] == pytest.approx(1.5)
    assert features["breakout_status"] == pytest.approx(1.0)
    assert features["relative_strength_favorable"] == pytest.approx(0.02)  # LONG: as-is
    assert features["opportunity_score"] == pytest.approx(78.0)


def test_extract_features_short_sign_flips_direction_relative_fields():
    ind, setup, scoring = make_rows()
    setup = pd.Series({"long_breakout": False, "short_breakdown": True})
    features = extract_features(ind, setup, scoring, "SHORT", realized_vol=0.01)

    assert features is not None
    # SHORT: everything direction-relative gets sign-flipped vs the LONG case
    assert features["vwap_distance"] == pytest.approx(-(101.0 - 100.0) / 100.0)
    assert features["ema_9_20_pct"] == pytest.approx(-(102.0 - 100.0) / 100.0)
    assert features["rsi_favorable"] == pytest.approx(100.0 - 65.0)  # SHORT: 100-RSI
    assert features["relative_strength_favorable"] == pytest.approx(-0.02)
    assert features["breakout_status"] == pytest.approx(1.0)  # short_breakdown True
    assert features["opportunity_score"] == pytest.approx(20.0)  # short_score, not long_score


def test_extract_features_direction_agnostic_fields_unchanged_by_direction():
    ind, setup, scoring = make_rows()
    long_features = extract_features(ind, setup, scoring, "LONG", realized_vol=0.01)
    short_features = extract_features(ind, setup, scoring, "SHORT", realized_vol=0.01)
    assert long_features["adx"] == short_features["adx"]
    assert long_features["atr_pct"] == short_features["atr_pct"]
    assert long_features["relative_volume"] == short_features["relative_volume"]


def test_extract_features_none_when_required_value_missing():
    ind, setup, scoring = make_rows()
    ind_missing = ind.copy()
    ind_missing["rsi"] = float("nan")
    assert extract_features(ind_missing, setup, scoring, "LONG", realized_vol=0.01) is None


def test_extract_features_none_when_volatility_missing():
    ind, setup, scoring = make_rows()
    assert extract_features(ind, setup, scoring, "LONG", realized_vol=None) is None
    assert extract_features(ind, setup, scoring, "LONG", realized_vol=float("nan")) is None


def test_extract_features_market_alignment_and_regime():
    ind, setup, scoring = make_rows()
    nifty_bullish = pd.Series({"adx": 30.0, "ema_20": 20000.0, "ema_50": 19800.0})
    features_long = extract_features(ind, setup, scoring, "LONG", nifty_ind_row=nifty_bullish, realized_vol=0.01)
    assert features_long["market_alignment"] == pytest.approx(1.0)  # nifty bullish, trade LONG -> aligned
    assert features_long["market_regime_adx"] == pytest.approx(30.0)

    features_short = extract_features(ind, setup, scoring, "SHORT", nifty_ind_row=nifty_bullish, realized_vol=0.01)
    assert features_short["market_alignment"] == pytest.approx(-1.0)  # nifty bullish, trade SHORT -> misaligned


def test_realized_volatility_hand_computed():
    closes = pd.Series([100.0, 101.0, 100.0, 102.0, 101.0, 103.0])
    vol = realized_volatility(closes, window=3)
    assert pd.isna(vol.iloc[0])
    assert pd.isna(vol.iloc[1])
    assert not pd.isna(vol.iloc[3])  # first window fully populated once 3 returns exist


def test_realized_volatility_rejects_non_positive_window():
    with pytest.raises(ValueError):
        realized_volatility(pd.Series([100.0, 101.0]), window=0)
