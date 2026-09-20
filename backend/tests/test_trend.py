import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.indicators.trend import ema, macd  # noqa: E402


def test_ema_hand_computed_example():
    # span=3 -> alpha = 2/(3+1) = 0.5
    # closes: [10, 11, 12]
    # ema[0] = 10 (seed = first value, ewm adjust=False)
    # ema[1] = 0.5*11 + 0.5*10 = 10.5
    # ema[2] = 0.5*12 + 0.5*10.5 = 11.25
    closes = pd.Series([10.0, 11.0, 12.0])
    result = ema(closes, span=3)
    assert result.iloc[0] == pytest.approx(10.0)
    assert result.iloc[1] == pytest.approx(10.5)
    assert result.iloc[2] == pytest.approx(11.25)


def test_ema_rejects_non_positive_span():
    with pytest.raises(ValueError):
        ema(pd.Series([1.0, 2.0]), span=0)


def test_macd_histogram_equals_macd_minus_signal():
    closes = pd.Series([float(x) for x in range(1, 60)])  # long enough series
    result = macd(closes, fast=3, slow=6, signal=2)
    diff = (result["macd"] - result["signal"] - result["histogram"]).abs()
    assert (diff < 1e-9).all()


def test_macd_rejects_fast_greater_or_equal_slow():
    closes = pd.Series([1.0, 2.0, 3.0])
    with pytest.raises(ValueError):
        macd(closes, fast=26, slow=12)
