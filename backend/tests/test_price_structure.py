import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.indicators.structure import market_structure  # noqa: E402
from app.setup_detection.price_structure import (  # noqa: E402
    price_structure_bearish,
    price_structure_bullish,
    price_structure_regime,
)


@pytest.fixture()
def clean_uptrend_structure():
    # n=1 fractal. Designed so:
    #   - first swing high confirms@2 (price 15) - no baseline yet
    #   - second swing high confirms@4 (price 18, HIGHER -> higher_high@4)
    #   - third swing high confirms@6 (price 20, HIGHER -> higher_high@6)
    #   - first swing low confirms@3 (price 9) - no baseline yet
    #   - second swing low confirms@5 (price 11, HIGHER -> higher_low@5)
    high = pd.Series([10.0, 15.0, 12.0, 18.0, 14.0, 20.0, 15.0])
    low = pd.Series([8.0, 13.0, 9.0, 14.0, 11.0, 16.0, 10.0])
    structure = market_structure(high, low, n=1)
    return structure


def test_regime_stays_unknown_until_first_confirmed_pair(clean_uptrend_structure):
    regime = price_structure_regime(
        clean_uptrend_structure["higher_high"],
        clean_uptrend_structure["lower_high"],
        clean_uptrend_structure["higher_low"],
        clean_uptrend_structure["lower_low"],
    )
    # No higher_high/lower_high/higher_low/lower_low flag is True until
    # index 4 (first higher_high) - state must be unknown (NA) before that.
    assert regime["high_swing_state"].iloc[0:4].isna().all()
    assert regime["low_swing_state"].iloc[0:5].isna().all()


def test_regime_forward_fills_after_confirmation(clean_uptrend_structure):
    regime = price_structure_regime(
        clean_uptrend_structure["higher_high"],
        clean_uptrend_structure["lower_high"],
        clean_uptrend_structure["higher_low"],
        clean_uptrend_structure["lower_low"],
    )
    assert regime["high_swing_state"].iloc[4] == "higher"
    assert regime["high_swing_state"].iloc[5] == "higher"  # held constant, forward-filled
    assert regime["low_swing_state"].iloc[5] == "higher"


def test_require_both_true_needs_both_sides_confirmed(clean_uptrend_structure):
    regime = price_structure_regime(
        clean_uptrend_structure["higher_high"],
        clean_uptrend_structure["lower_high"],
        clean_uptrend_structure["higher_low"],
        clean_uptrend_structure["lower_low"],
    )
    bullish_both = price_structure_bullish(regime, require_both=True)
    # At index 4: high side confirmed "higher", but low side hasn't
    # confirmed "higher" yet (that happens at index 5) -> must be False.
    assert bullish_both.iloc[4] == False
    # At index 5: both sides now "higher" -> True.
    assert bullish_both.iloc[5] == True


def test_require_both_false_accepts_either_side(clean_uptrend_structure):
    regime = price_structure_regime(
        clean_uptrend_structure["higher_high"],
        clean_uptrend_structure["lower_high"],
        clean_uptrend_structure["higher_low"],
        clean_uptrend_structure["lower_low"],
    )
    bullish_either = price_structure_bullish(regime, require_both=False)
    # At index 4, high side alone already confirmed "higher" -> True even
    # though the low side hasn't confirmed yet - this is the difference
    # require_both makes.
    assert bullish_either.iloc[4] == True


def test_bearish_structure_never_true_during_this_uptrend(clean_uptrend_structure):
    regime = price_structure_regime(
        clean_uptrend_structure["higher_high"],
        clean_uptrend_structure["lower_high"],
        clean_uptrend_structure["higher_low"],
        clean_uptrend_structure["lower_low"],
    )
    bearish = price_structure_bearish(regime, require_both=True)
    assert not bearish.any()
