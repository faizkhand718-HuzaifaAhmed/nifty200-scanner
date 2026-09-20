import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ranking.risk_reward import long_risk_reward, short_risk_reward  # noqa: E402


def test_long_risk_reward_uses_pivot_levels():
    # close=102, support(S1)=98 -> risk=4 ; r1=110>close -> target=110,
    # reward=8 -> rr=8/4=2.0
    stop, target, rr = long_risk_reward(
        close=102.0, atr=1.0, support=98.0, r1=110.0, r2=120.0, r3=130.0,
        stop_atr_multiple=1.5, target_atr_multiple=3.0,
    )
    assert stop == pytest.approx(98.0)
    assert target == pytest.approx(110.0)
    assert rr == pytest.approx(2.0)


def test_long_risk_reward_skips_r1_if_already_below_close():
    # close=112 is already above r1=110, so target should be r2=120
    stop, target, rr = long_risk_reward(
        close=112.0, atr=1.0, support=98.0, r1=110.0, r2=120.0, r3=130.0,
        stop_atr_multiple=1.5, target_atr_multiple=3.0,
    )
    assert target == pytest.approx(120.0)


def test_long_risk_reward_falls_back_to_atr_when_no_levels():
    # no support/resistance available (NaN/None) -> use ATR multiples
    # stop = close - 1.5*atr = 100 - 1.5 = 98.5 ; target = close + 3*atr = 103
    stop, target, rr = long_risk_reward(
        close=100.0, atr=1.0, support=None, r1=None, r2=None, r3=None,
        stop_atr_multiple=1.5, target_atr_multiple=3.0,
    )
    assert stop == pytest.approx(98.5)
    assert target == pytest.approx(103.0)
    assert rr == pytest.approx(2.0)


def test_long_risk_reward_falls_back_when_support_is_not_below_close():
    # support(101) >= close(100) is not usable as a stop (it isn't below
    # price) - the function falls back to the ATR-based stop rather than
    # using an invalid level, so this does NOT produce an undefined risk.
    stop, target, rr = long_risk_reward(
        close=100.0, atr=1.0, support=101.0, r1=110.0, r2=None, r3=None,
        stop_atr_multiple=1.5, target_atr_multiple=3.0,
    )
    assert stop == pytest.approx(98.5)  # ATR fallback, not the invalid 101
    assert rr is not None


def test_long_risk_reward_none_when_atr_is_zero():
    # With no usable pivot levels and atr=0, the ATR fallback degenerates
    # to stop == target == close - zero risk AND zero reward - correctly
    # undefined rather than a fabricated ratio.
    stop, target, rr = long_risk_reward(
        close=100.0, atr=0.0, support=None, r1=None, r2=None, r3=None,
        stop_atr_multiple=1.5, target_atr_multiple=3.0,
    )
    assert rr is None


def test_short_risk_reward_uses_pivot_levels():
    # close=98, resistance(R1)=102 -> risk=4 ; s1=90<close -> target=90,
    # reward=8 -> rr=2.0
    stop, target, rr = short_risk_reward(
        close=98.0, atr=1.0, resistance=102.0, s1=90.0, s2=80.0, s3=70.0,
        stop_atr_multiple=1.5, target_atr_multiple=3.0,
    )
    assert stop == pytest.approx(102.0)
    assert target == pytest.approx(90.0)
    assert rr == pytest.approx(2.0)


def test_short_risk_reward_falls_back_to_atr_when_no_levels():
    stop, target, rr = short_risk_reward(
        close=100.0, atr=1.0, resistance=None, s1=None, s2=None, s3=None,
        stop_atr_multiple=1.5, target_atr_multiple=3.0,
    )
    assert stop == pytest.approx(101.5)
    assert target == pytest.approx(97.0)
    assert rr == pytest.approx(2.0)


def test_risk_reward_none_when_close_or_atr_missing():
    assert long_risk_reward(None, 1.0, 98.0, 110.0, None, None, 1.5, 3.0) == (None, None, None)
    assert long_risk_reward(100.0, float("nan"), 98.0, 110.0, None, None, 1.5, 3.0) == (None, None, None)
