import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.indicators.volatility import atr, true_range  # noqa: E402


@pytest.fixture()
def sample_ohlc():
    high = pd.Series([10.0, 12.0, 11.0, 13.0, 14.0])
    low = pd.Series([8.0, 9.0, 7.0, 10.0, 13.0])
    close = pd.Series([9.0, 11.0, 8.0, 12.0, 13.0])
    return high, low, close


def test_true_range_hand_computed(sample_ohlc):
    high, low, close = sample_ohlc
    # bar0: no prior close -> TR = H-L = 2 (still a valid number, not NaN,
    #   since H-L doesn't need a previous close)
    # bar1: prev_close=9 -> max(12-9=3, |12-9|=3, |9-9|=0) = 3
    # bar2: prev_close=11 -> max(11-7=4, |11-11|=0, |7-11|=4) = 4
    # bar3: prev_close=8  -> max(13-10=3, |13-8|=5, |10-8|=2) = 5
    # bar4: prev_close=12 -> max(14-13=1, |14-12|=2, |13-12|=1) = 2
    tr = true_range(high, low, close)
    assert tr.tolist() == pytest.approx([2.0, 3.0, 4.0, 5.0, 2.0])


def test_atr_hand_computed(sample_ohlc):
    high, low, close = sample_ohlc
    # TR series = [2, 3, 4, 5, 2], period=2
    # seed (index1) = mean(TR[0], TR[1]) = mean(2, 3) = 2.5
    # index2 = (2.5*1 + 4) / 2 = 3.25
    # index3 = (3.25*1 + 5) / 2 = 4.125
    # index4 = (4.125*1 + 2) / 2 = 3.0625
    result = atr(high, low, close, period=2)
    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == pytest.approx(2.5)
    assert result.iloc[2] == pytest.approx(3.25)
    assert result.iloc[3] == pytest.approx(4.125)
    assert result.iloc[4] == pytest.approx(3.0625)


def test_atr_rejects_non_positive_period(sample_ohlc):
    high, low, close = sample_ohlc
    with pytest.raises(ValueError):
        atr(high, low, close, period=0)


def test_atr_never_negative(sample_ohlc):
    high, low, close = sample_ohlc
    result = atr(high, low, close, period=2).dropna()
    assert (result >= 0).all()
