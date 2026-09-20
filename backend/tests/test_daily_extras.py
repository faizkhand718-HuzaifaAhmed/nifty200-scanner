import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.indicators.daily_extras import daily_relative_volume, fifty_two_week_high_low, period_return_pct  # noqa: E402


def test_fifty_two_week_high_low_hand_computed():
    closes = pd.Series([100.0 + i * 0.5 for i in range(300)])
    highs = closes + 1.0
    lows = closes - 1.0

    result = fifty_two_week_high_low(closes, highs, lows, window=252)

    window_highs = highs.iloc[48:300]
    expected_high = window_highs.max()
    assert result["fifty_two_week_high"].iloc[299] == pytest.approx(expected_high)

    expected_pct_from_high = (closes.iloc[299] - expected_high) / expected_high * 100
    assert result["pct_from_52w_high"].iloc[299] == pytest.approx(expected_pct_from_high)


def test_fifty_two_week_high_low_nan_before_window_filled():
    closes = pd.Series([100.0] * 100)
    result = fifty_two_week_high_low(closes, closes, closes, window=252)
    assert result["fifty_two_week_high"].isna().all()


def test_period_return_pct_hand_computed():
    closes = pd.Series([100.0, 101.0, 102.0, 103.0, 110.0])
    returns = period_return_pct(closes, periods=4)
    assert returns.iloc[4] == pytest.approx(10.0)
    assert returns.iloc[:4].isna().all()


def test_period_return_pct_rejects_non_positive_periods():
    with pytest.raises(ValueError):
        period_return_pct(pd.Series([100.0]), periods=0)


def test_daily_relative_volume_hand_computed():
    volumes = pd.Series([1000] * 21 + [3000])
    result = daily_relative_volume(volumes, window=20)
    assert result.iloc[-1] == pytest.approx(3.0)


def test_daily_relative_volume_never_includes_todays_own_bar():
    volumes = pd.Series([1000] * 20 + [100000])
    result = daily_relative_volume(volumes, window=20)
    assert result.iloc[-1] == pytest.approx(100.0)


def test_daily_relative_volume_rejects_non_positive_window():
    with pytest.raises(ValueError):
        daily_relative_volume(pd.Series([1000.0]), window=0)
