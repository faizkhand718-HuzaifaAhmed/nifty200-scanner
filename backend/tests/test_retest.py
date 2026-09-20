import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.setup_detection.retest import retest_long, retest_short  # noqa: E402


def test_retest_long_hand_computed():
    # resistance=100 constant; breakout happens at bar1; bars 2-3 pull
    # back within 0.3% of 100 while holding above it -> retest True there.
    # bar4 spikes far away (no retest); bar5 has no recent breakout in
    # its 3-bar lookback window anymore -> False.
    breakout = pd.Series([False, True, False, False, False, False])
    resistance = pd.Series([100.0] * 6)
    low = pd.Series([98.0, 101.0, 99.7, 99.9, 105.0, 99.8])
    close = pd.Series([99.0, 102.0, 100.5, 99.85, 106.0, 99.9])

    result = retest_long(breakout, resistance, low, close, lookback_bars=3, tolerance_pct=0.003)
    assert list(result) == [False, False, True, True, False, False]


def test_retest_short_hand_computed():
    breakdown = pd.Series([False, True, False, False, False, False])
    support = pd.Series([100.0] * 6)
    high = pd.Series([102.0, 99.0, 100.2, 100.05, 95.0, 100.1])
    close = pd.Series([101.0, 98.0, 99.8, 100.1, 94.0, 100.05])

    result = retest_short(breakdown, support, high, close, lookback_bars=3, tolerance_pct=0.003)
    assert list(result) == [False, False, True, True, False, False]


def test_retest_long_false_without_a_recent_breakout():
    breakout = pd.Series([False, False, False, False])
    resistance = pd.Series([100.0] * 4)
    low = pd.Series([99.9, 99.9, 99.9, 99.9])
    close = pd.Series([100.0, 100.0, 100.0, 100.0])
    result = retest_long(breakout, resistance, low, close, lookback_bars=3, tolerance_pct=0.003)
    assert not result.any()


def test_retest_long_false_when_level_unknown():
    breakout = pd.Series([True, False])
    resistance = pd.Series([float("nan"), float("nan")])
    low = pd.Series([100.0, 100.0])
    close = pd.Series([100.0, 100.0])
    result = retest_long(breakout, resistance, low, close, lookback_bars=3, tolerance_pct=0.003)
    assert not result.any()


def test_retest_rejects_non_positive_params():
    breakout = pd.Series([True, False])
    resistance = pd.Series([100.0, 100.0])
    low = pd.Series([99.0, 99.0])
    close = pd.Series([100.0, 100.0])
    with pytest.raises(ValueError):
        retest_long(breakout, resistance, low, close, lookback_bars=0, tolerance_pct=0.003)
    with pytest.raises(ValueError):
        retest_long(breakout, resistance, low, close, lookback_bars=3, tolerance_pct=0.0)
