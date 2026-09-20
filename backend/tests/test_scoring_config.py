import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.scoring.config import ScoringWeights  # noqa: E402


def test_default_weights_sum_to_100():
    w = ScoringWeights()
    assert w.total() == pytest.approx(100.0)
    w.validate()  # must not raise


def test_default_weights_match_spec():
    w = ScoringWeights()
    assert w.trend == 20
    assert w.volume == 15
    assert w.vwap == 15
    assert w.momentum == 10
    assert w.ema_structure == 10
    assert w.breakout == 10
    assert w.market_confirmation == 10
    assert w.relative_strength == 5
    assert w.risk == 5


def test_validate_rejects_non_100_total():
    w = ScoringWeights(trend=25.0)  # now sums to 105
    with pytest.raises(ValueError, match="must sum to 100"):
        w.validate()


def test_validate_rejects_negative_weight():
    w = ScoringWeights(trend=-5.0, volume=25.0)  # still sums to 100 but negative
    with pytest.raises(ValueError, match="non-negative"):
        w.validate()


def test_rescaled_normalizes_to_100():
    w = ScoringWeights.rescaled(trend=4, volume=3, vwap=3, momentum=2, ema_structure=2, breakout=2, market_confirmation=2, relative_strength=1, risk=1)
    assert w.total() == pytest.approx(100.0)
    w.validate()
    # relative proportions preserved: trend was 4x risk's 1x
    assert w.trend == pytest.approx(w.risk * 4)


def test_rescaled_rejects_non_positive_total():
    with pytest.raises(ValueError):
        ScoringWeights.rescaled(trend=0, volume=0, vwap=0, momentum=0, ema_structure=0, breakout=0, market_confirmation=0, relative_strength=0, risk=0)
