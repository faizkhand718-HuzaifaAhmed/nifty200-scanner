import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.indicators.pivots import classic_pivot_points, support_resistance  # noqa: E402

DAY1 = date(2026, 1, 27)
DAY2 = date(2026, 1, 28)


def test_classic_pivot_points_hand_computed():
    # prev_high=110, prev_low=90, prev_close=100
    # PP = (110+90+100)/3 = 100
    # R1 = 2*100-90 = 110      S1 = 2*100-110 = 90
    # R2 = 100+(110-90) = 120  S2 = 100-(110-90) = 80
    # R3 = 110+2*(100-90) = 130  S3 = 90-2*(110-100) = 70
    prev_high = pd.Series([110.0])
    prev_low = pd.Series([90.0])
    prev_close = pd.Series([100.0])
    result = classic_pivot_points(prev_high, prev_low, prev_close)

    assert result["pivot"].iloc[0] == pytest.approx(100.0)
    assert result["r1"].iloc[0] == pytest.approx(110.0)
    assert result["s1"].iloc[0] == pytest.approx(90.0)
    assert result["r2"].iloc[0] == pytest.approx(120.0)
    assert result["s2"].iloc[0] == pytest.approx(80.0)
    assert result["r3"].iloc[0] == pytest.approx(130.0)
    assert result["s3"].iloc[0] == pytest.approx(70.0)


@pytest.fixture()
def two_day_data():
    high = pd.Series([105.0, 110.0, 108.0, 112.0, 116.0, 109.0])
    low = pd.Series([95.0, 90.0, 92.0, 91.0, 84.0, 95.0])
    close = pd.Series([100.0, 105.0, 100.0, 115.0, 85.0, 100.0])
    session_date = pd.Series([DAY1] * 3 + [DAY2] * 3)
    return high, low, close, session_date


def test_support_resistance_derived_from_previous_day(two_day_data):
    high, low, close, session_date = two_day_data
    result = support_resistance(high, low, close, session_date)

    # Day 1's actual high/low/close(last) = 110/90/100 -> same pivots as
    # the hand-computed example above, held constant through day 2.
    day2 = result.iloc[3:6]
    assert (day2["pivot"] == pytest.approx(100.0)).all()
    assert (day2["resistance"] == pytest.approx(110.0)).all()
    assert (day2["support"] == pytest.approx(90.0)).all()


def test_breakout_and_breakdown_flags(two_day_data):
    high, low, close, session_date = two_day_data
    result = support_resistance(high, low, close, session_date)
    day2 = result.iloc[3:6].reset_index(drop=True)

    # day2 closes: 115 (>110 resistance -> breakout), 85 (<90 support ->
    # breakdown), 100 (neither).
    assert list(day2["breakout"]) == [True, False, False]
    assert list(day2["breakdown"]) == [False, True, False]


def test_first_day_has_no_levels_and_unknown_breakout(two_day_data):
    high, low, close, session_date = two_day_data
    result = support_resistance(high, low, close, session_date)
    day1 = result.iloc[0:3]

    assert day1["pivot"].isna().all()
    assert day1["support"].isna().all()
    assert day1["resistance"].isna().all()
    # Breakout/breakdown must be "unknown" (NA), not fabricated False.
    assert day1["breakout"].isna().all()
    assert day1["breakdown"].isna().all()
