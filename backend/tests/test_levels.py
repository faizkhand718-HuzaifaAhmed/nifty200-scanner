import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.indicators.levels import day_high_low, previous_day_high_low  # noqa: E402

DAY1 = date(2026, 1, 27)
DAY2 = date(2026, 1, 28)


@pytest.fixture()
def two_day_data():
    high = pd.Series([10.0, 12.0, 11.0, 15.0, 14.0, 16.0])
    low = pd.Series([8.0, 9.0, 7.0, 13.0, 12.0, 11.0])
    session_date = pd.Series([DAY1, DAY1, DAY1, DAY2, DAY2, DAY2])
    return high, low, session_date


def test_day_high_low_is_running_within_session(two_day_data):
    high, low, session_date = two_day_data
    result = day_high_low(high, low, session_date)

    # Day 1: high running max = 10, 12, 12 ; low running min = 8, 8, 7
    assert result["day_high"].iloc[0:3].tolist() == pytest.approx([10.0, 12.0, 12.0])
    assert result["day_low"].iloc[0:3].tolist() == pytest.approx([8.0, 8.0, 7.0])

    # Day 2 resets and runs independently: high = 15, 15, 16 ; low = 13, 12, 11
    assert result["day_high"].iloc[3:6].tolist() == pytest.approx([15.0, 15.0, 16.0])
    assert result["day_low"].iloc[3:6].tolist() == pytest.approx([13.0, 12.0, 11.0])


def test_previous_day_high_low(two_day_data):
    high, low, session_date = two_day_data
    result = previous_day_high_low(high, low, session_date)

    # Day 1 has no prior day - NaN throughout.
    assert result["prev_day_high"].iloc[0:3].isna().all()
    assert result["prev_day_low"].iloc[0:3].isna().all()

    # Day 2: previous day's completed high=12, low=7, held constant.
    assert result["prev_day_high"].iloc[3:6].tolist() == pytest.approx([12.0, 12.0, 12.0])
    assert result["prev_day_low"].iloc[3:6].tolist() == pytest.approx([7.0, 7.0, 7.0])


def test_previous_day_high_low_does_not_leak_current_day_data(two_day_data):
    """A same-day extreme that exceeds the previous day's range must NOT
    appear in prev_day_high/low - that would be look-ahead within the day
    itself (using today's own high to describe "yesterday")."""
    high, low, session_date = two_day_data
    result = previous_day_high_low(high, low, session_date)
    # Day 2's own high (16) must not appear as any prev_day_high value.
    assert 16.0 not in result["prev_day_high"].tolist()
