import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.indicators.structure import classify_structure, market_structure, swing_points  # noqa: E402


@pytest.fixture()
def sample_series():
    # n=1: a bar is a swing point if it's more extreme than the single bar
    # immediately before AND after it. Confirmation happens 1 bar later.
    #
    # high = [10, 15, 12, 18, 11, 14, 9]
    #   i=1: 15 > high[0]=10 and 15 > high[2]=12 -> swing high, confirmed@2, price=15
    #   i=3: 18 > high[2]=12 and 18 > high[4]=11 -> swing high, confirmed@4, price=18 (higher than 15)
    #   i=5: 14 > high[4]=11 and 14 > high[6]=9  -> swing high, confirmed@6, price=14 (lower than 18)
    #
    # low = [8, 5, 9, 3, 10, 6, 11]
    #   i=1: 5 < low[0]=8 and 5 < low[2]=9   -> swing low, confirmed@2, price=5
    #   i=3: 3 < low[2]=9 and 3 < low[4]=10  -> swing low, confirmed@4, price=3 (lower than 5)
    #   i=5: 6 < low[4]=10 and 6 < low[6]=11 -> swing low, confirmed@6, price=6 (higher than 3)
    high = pd.Series([10.0, 15.0, 12.0, 18.0, 11.0, 14.0, 9.0])
    low = pd.Series([8.0, 5.0, 9.0, 3.0, 10.0, 6.0, 11.0])
    return high, low


def test_swing_points_confirmed_at_correct_rows(sample_series):
    high, low = sample_series
    result = swing_points(high, low, n=1)

    assert list(result["swing_high_confirmed"]) == [False, False, True, False, True, False, True]
    assert list(result["swing_low_confirmed"]) == [False, False, True, False, True, False, True]

    assert result["swing_high_price"].iloc[2] == pytest.approx(15.0)
    assert result["swing_high_price"].iloc[4] == pytest.approx(18.0)
    assert result["swing_high_price"].iloc[6] == pytest.approx(14.0)

    assert result["swing_low_price"].iloc[2] == pytest.approx(5.0)
    assert result["swing_low_price"].iloc[4] == pytest.approx(3.0)
    assert result["swing_low_price"].iloc[6] == pytest.approx(6.0)


def test_classify_structure_higher_lower_high_low(sample_series):
    high, low = sample_series
    swings = swing_points(high, low, n=1)
    structure = classify_structure(swings)

    # First swing of each type (row 2) has nothing to compare against.
    assert structure["higher_high"].iloc[2] is False or structure["higher_high"].iloc[2] == False
    assert structure["lower_high"].iloc[2] == False
    assert structure["higher_low"].iloc[2] == False
    assert structure["lower_low"].iloc[2] == False

    # Row 4: swing high 18 > previous swing high 15 -> Higher High
    assert structure["higher_high"].iloc[4] == True
    assert structure["lower_high"].iloc[4] == False
    # Row 4: swing low 3 < previous swing low 5 -> Lower Low
    assert structure["lower_low"].iloc[4] == True
    assert structure["higher_low"].iloc[4] == False

    # Row 6: swing high 14 < previous swing high 18 -> Lower High
    assert structure["lower_high"].iloc[6] == True
    assert structure["higher_high"].iloc[6] == False
    # Row 6: swing low 6 > previous swing low 3 -> Higher Low
    assert structure["higher_low"].iloc[6] == True
    assert structure["lower_low"].iloc[6] == False


def test_market_structure_combines_both_steps(sample_series):
    high, low = sample_series
    combined = market_structure(high, low, n=1)
    assert set(combined.columns) == {
        "swing_high_confirmed", "swing_high_price", "swing_low_confirmed", "swing_low_price",
        "higher_high", "lower_high", "higher_low", "lower_low",
    }
    assert combined["higher_high"].iloc[4] == True


def test_swing_points_rejects_non_positive_n(sample_series):
    high, low = sample_series
    with pytest.raises(ValueError):
        swing_points(high, low, n=0)


def test_no_swings_confirmed_at_the_very_edges(sample_series):
    """The first and last `n` bars can never be confirmed swings - there
    isn't enough history/future-within-available-data on one side."""
    high, low = sample_series
    result = swing_points(high, low, n=1)
    assert result["swing_high_confirmed"].iloc[0] == False
    assert result["swing_high_confirmed"].iloc[-1] == False
