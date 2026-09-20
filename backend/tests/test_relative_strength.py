import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.indicators.relative_strength import relative_strength  # noqa: E402


def test_relative_strength_hand_computed():
    # stock grows 10% per bar; nifty grows 2% per bar. Over a 2-bar window,
    # stock return = (1.1^2 - 1) = 0.21 ; nifty return = (1.02^2 - 1) = 0.0404
    # relative strength = 0.21 - 0.0404 = 0.1696 (stock outperforming)
    stock_close = pd.Series([100.0, 110.0, 121.0, 133.1])
    nifty_close = pd.Series([1000.0, 1020.0, 1040.4, 1061.208])

    result = relative_strength(stock_close, nifty_close, window=2)

    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])
    assert result.iloc[2] == pytest.approx(0.1696, rel=1e-3)
    assert result.iloc[3] == pytest.approx(0.1696, rel=1e-3)


def test_relative_strength_negative_when_underperforming():
    stock_close = pd.Series([100.0, 100.0, 100.0])  # flat
    nifty_close = pd.Series([1000.0, 1050.0, 1100.0])  # index rising
    result = relative_strength(stock_close, nifty_close, window=1)
    assert result.iloc[1] < 0
    assert result.iloc[2] < 0


def test_relative_strength_rejects_misaligned_lengths():
    with pytest.raises(ValueError):
        relative_strength(pd.Series([1.0, 2.0]), pd.Series([1.0, 2.0, 3.0]), window=1)


def test_relative_strength_rejects_non_positive_window():
    with pytest.raises(ValueError):
        relative_strength(pd.Series([1.0, 2.0]), pd.Series([1.0, 2.0]), window=0)
