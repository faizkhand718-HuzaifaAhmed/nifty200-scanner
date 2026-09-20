import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.indicators._wilder import wilder_smooth  # noqa: E402


def test_wilder_smooth_hand_computed_example():
    # values (index 0 is a placeholder NaN, mimicking a .diff()/.shift()
    # leading gap): [NaN, 1, 2, 3, 4, 5]
    # period=2 -> seed = mean(values[1], values[2]) = mean(1, 2) = 1.5 at index 2
    # index 3: (1.5*(2-1) + 3) / 2 = (1.5+3)/2 = 2.25
    # index 4: (2.25*1 + 4) / 2 = 3.125
    # index 5: (3.125*1 + 5) / 2 = 4.0625
    series = pd.Series([float("nan"), 1, 2, 3, 4, 5])
    result = wilder_smooth(series, period=2)

    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])
    assert result.iloc[2] == pytest.approx(1.5)
    assert result.iloc[3] == pytest.approx(2.25)
    assert result.iloc[4] == pytest.approx(3.125)
    assert result.iloc[5] == pytest.approx(4.0625)


def test_wilder_smooth_insufficient_data_returns_all_nan():
    series = pd.Series([float("nan"), 1.0, 2.0])
    result = wilder_smooth(series, period=5)
    assert result.isna().all()


def test_wilder_smooth_rejects_non_positive_period():
    with pytest.raises(ValueError):
        wilder_smooth(pd.Series([1.0, 2.0, 3.0]), period=0)
