import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.indicators.volume import average_volume, relative_volume, vwap  # noqa: E402


def test_vwap_hand_computed_single_day():
    high = pd.Series([10.0, 11.0, 12.0])
    low = pd.Series([8.0, 9.0, 10.0])
    close = pd.Series([9.0, 10.0, 11.0])
    volume = pd.Series([100, 200, 100])
    session_date = pd.Series([date(2026, 1, 27)] * 3)

    result = vwap(high, low, close, volume, session_date)

    # typical prices: 9.0, 10.0, 11.0 ; pv: 900, 2000, 1100
    # cum_pv: 900, 2900, 4000 ; cum_vol: 100, 300, 400
    # vwap: 9.0, 9.6667, 10.0
    assert result.iloc[0] == pytest.approx(9.0)
    assert result.iloc[1] == pytest.approx(2900 / 300)
    assert result.iloc[2] == pytest.approx(10.0)


def test_vwap_resets_at_new_session():
    high = pd.Series([10.0, 11.0, 20.0])
    low = pd.Series([8.0, 9.0, 18.0])
    close = pd.Series([9.0, 10.0, 19.0])
    volume = pd.Series([100, 200, 50])
    session_date = pd.Series([date(2026, 1, 27), date(2026, 1, 27), date(2026, 1, 28)])

    result = vwap(high, low, close, volume, session_date)

    # Day 2 has a single bar - its VWAP must equal that bar's own typical
    # price, NOT be influenced by day 1's cumulative sums.
    assert result.iloc[2] == pytest.approx(19.0)


def test_average_volume_hand_computed():
    volume = pd.Series([100, 200, 100, 50])
    result = average_volume(volume, window=2)
    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == pytest.approx(150.0)
    assert result.iloc[2] == pytest.approx(150.0)
    assert result.iloc[3] == pytest.approx(75.0)


def test_relative_volume_excludes_current_bar_from_baseline():
    volume = pd.Series([100, 200, 100, 50])
    result = relative_volume(volume, window=2)
    # baseline at index2 = mean(volume[0], volume[1]) = mean(100, 200) = 150
    # relative_volume[2] = volume[2] / 150 = 100/150
    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])
    assert result.iloc[2] == pytest.approx(100 / 150)
    assert result.iloc[3] == pytest.approx(50 / 150)


def test_average_and_relative_volume_reject_non_positive_window():
    volume = pd.Series([100, 200])
    with pytest.raises(ValueError):
        average_volume(volume, window=0)
    with pytest.raises(ValueError):
        relative_volume(volume, window=0)
