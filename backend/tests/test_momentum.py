import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.indicators.momentum import rsi  # noqa: E402


def test_rsi_hand_computed_example():
    # closes: 10, 11, 10, 12, 13, 12, 14 ; period=3
    # diffs:  -, +1, -1, +2, +1, -1, +2
    # Wilder bootstrap seed at index 3 = mean of first 3 gains/losses:
    #   avg_gain seed = mean(1, 0, 2) = 1.0
    #   avg_loss seed = mean(0, 1, 0) = 0.3333...
    # RSI[3] = 100 - 100/(1 + 1.0/0.3333) = 75.0
    # RSI[4] = 100 - 100/(1 + 1.0/0.2222) = 81.8182
    # RSI[5] = 100 - 100/(1 + 0.6667/0.4815) = 58.0645
    # RSI[6] = 100 - 100/(1 + 1.1111/0.3210) = 77.5862
    closes = pd.Series([10, 11, 10, 12, 13, 12, 14], dtype=float)
    result = rsi(closes, period=3)

    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])
    assert pd.isna(result.iloc[2])
    assert result.iloc[3] == pytest.approx(75.0, rel=1e-4)
    assert result.iloc[4] == pytest.approx(81.8182, rel=1e-4)
    assert result.iloc[5] == pytest.approx(58.0645, rel=1e-4)
    assert result.iloc[6] == pytest.approx(77.5862, rel=1e-4)


def test_rsi_all_gains_is_100():
    closes = pd.Series([10, 11, 12, 13, 14, 15], dtype=float)
    result = rsi(closes, period=3)
    assert result.iloc[-1] == pytest.approx(100.0)


def test_rsi_all_losses_is_0():
    closes = pd.Series([15, 14, 13, 12, 11, 10], dtype=float)
    result = rsi(closes, period=3)
    assert result.iloc[-1] == pytest.approx(0.0)


def test_rsi_bounded_between_0_and_100():
    closes = pd.Series([10, 12, 9, 15, 8, 20, 7, 25, 6, 30], dtype=float)
    result = rsi(closes, period=3).dropna()
    assert (result >= 0).all() and (result <= 100).all()


def test_rsi_rejects_non_positive_period():
    with pytest.raises(ValueError):
        rsi(pd.Series([1.0, 2.0]), period=0)
