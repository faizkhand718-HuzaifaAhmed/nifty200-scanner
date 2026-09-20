import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.indicators.trend_strength import adx  # noqa: E402


@pytest.fixture()
def clean_uptrend():
    # A parallel channel moving up by 2 each bar, closing at the high each
    # time. This is contrived specifically so True Range, +DM stay
    # constant (=2) and -DM stays exactly 0 - a clean, hand-traceable case
    # where ADX should read exactly 100 once it has enough history, and
    # -DI should read exactly 0 throughout.
    high = pd.Series([10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0])
    low = pd.Series([8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0])
    close = high.copy()
    return high, low, close


def test_adx_clean_uptrend_hand_computed(clean_uptrend):
    high, low, close = clean_uptrend
    result = adx(high, low, close, period=2)

    # +DM=2, -DM=0, TR=2 constant -> +DI settles at exactly 100, -DI at 0.
    # First ADX value expected at index 2*period-1 = 3 (needs one Wilder
    # pass to get +DI/-DI, a second to smooth DX into ADX).
    assert result["adx"].iloc[:3].isna().all()
    assert result["adx"].iloc[3:].apply(lambda v: v == pytest.approx(100.0)).all()
    assert result["minus_di"].iloc[2:].apply(lambda v: v == pytest.approx(0.0)).all()
    assert result["plus_di"].iloc[2:].apply(lambda v: v == pytest.approx(100.0)).all()


def test_adx_bounded_between_0_and_100():
    # A noisier, non-trending series - just checking the invariant holds,
    # not hand-tracing every value.
    high = pd.Series([10, 11, 10.5, 12, 11, 13, 10, 14, 9, 15], dtype=float)
    low = pd.Series([9, 9.5, 9, 10, 9.5, 11, 8.5, 12, 8, 13], dtype=float)
    close = pd.Series([9.5, 10, 9.7, 11, 10, 12, 9, 13, 8.5, 14], dtype=float)
    result = adx(high, low, close, period=3).dropna()
    assert (result["adx"] >= 0).all() and (result["adx"] <= 100).all()
    assert (result["plus_di"] >= 0).all()
    assert (result["minus_di"] >= 0).all()


def test_adx_rejects_non_positive_period(clean_uptrend):
    high, low, close = clean_uptrend
    with pytest.raises(ValueError):
        adx(high, low, close, period=0)
