import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.entry_engine.config import EntryEngineConfig, StopMethod, TargetMethod  # noqa: E402
from app.entry_engine.stop_target import compute_stop, compute_target  # noqa: E402

CONFIG = EntryEngineConfig()  # stop_atr_multiple=1.5, stop_percentage=0.005, target_atr_multiple=3.0


def test_stop_atr_long():
    ind = pd.Series({"atr": 2.0})
    stop = compute_stop(StopMethod.ATR, entry_price=100.0, direction="LONG", ind_row=ind, config=CONFIG)
    assert stop == pytest.approx(97.0)  # 100 - 1.5*2


def test_stop_atr_short():
    ind = pd.Series({"atr": 2.0})
    stop = compute_stop(StopMethod.ATR, entry_price=100.0, direction="SHORT", ind_row=ind, config=CONFIG)
    assert stop == pytest.approx(103.0)


def test_stop_atr_none_when_atr_missing():
    ind = pd.Series({"atr": float("nan")})
    stop = compute_stop(StopMethod.ATR, entry_price=100.0, direction="LONG", ind_row=ind, config=CONFIG)
    assert stop is None


def test_stop_percentage_long():
    stop = compute_stop(StopMethod.PERCENTAGE, entry_price=100.0, direction="LONG", ind_row=pd.Series({}), config=CONFIG)
    assert stop == pytest.approx(99.5)  # 100 * (1 - 0.005)


def test_stop_support_resistance_long():
    ind = pd.Series({"support": 95.0})
    stop = compute_stop(StopMethod.SUPPORT_RESISTANCE, entry_price=100.0, direction="LONG", ind_row=ind, config=CONFIG)
    assert stop == pytest.approx(95.0)


def test_stop_support_resistance_rejects_wrong_side():
    # support ABOVE entry price is not a usable LONG stop
    ind = pd.Series({"support": 105.0})
    stop = compute_stop(StopMethod.SUPPORT_RESISTANCE, entry_price=100.0, direction="LONG", ind_row=ind, config=CONFIG)
    assert stop is None


def test_stop_swing_long():
    stop = compute_stop(
        StopMethod.SWING, entry_price=100.0, direction="LONG", ind_row=pd.Series({}), config=CONFIG,
        recent_swing_low=97.0, recent_swing_high=110.0,
    )
    assert stop == pytest.approx(97.0)


def test_stop_swing_none_when_no_swing_seen_yet():
    stop = compute_stop(
        StopMethod.SWING, entry_price=100.0, direction="LONG", ind_row=pd.Series({}), config=CONFIG,
        recent_swing_low=None, recent_swing_high=None,
    )
    assert stop is None


def test_target_risk_reward_2_long():
    # entry=100, stop=97 -> risk=3 -> target = 100 + 2*3 = 106
    target = compute_target(TargetMethod.RISK_REWARD_2, entry_price=100.0, stop_price=97.0, direction="LONG", ind_row=pd.Series({}), config=CONFIG)
    assert target == pytest.approx(106.0)


def test_target_risk_reward_1_5_short():
    # entry=100, stop=103 -> risk=3 -> target = 100 - 1.5*3 = 95.5
    target = compute_target(TargetMethod.RISK_REWARD_1_5, entry_price=100.0, stop_price=103.0, direction="SHORT", ind_row=pd.Series({}), config=CONFIG)
    assert target == pytest.approx(95.5)


def test_target_risk_reward_none_without_stop():
    target = compute_target(TargetMethod.RISK_REWARD_3, entry_price=100.0, stop_price=None, direction="LONG", ind_row=pd.Series({}), config=CONFIG)
    assert target is None


def test_target_atr_long():
    ind = pd.Series({"atr": 2.0})
    target = compute_target(TargetMethod.ATR, entry_price=100.0, stop_price=97.0, direction="LONG", ind_row=ind, config=CONFIG)
    assert target == pytest.approx(106.0)  # 100 + 3*2


def test_target_prev_support_resistance_picks_next_level_above():
    ind = pd.Series({"r1": 98.0, "r2": 110.0, "r3": 120.0})  # r1 already below entry
    target = compute_target(TargetMethod.PREV_SUPPORT_RESISTANCE, entry_price=100.0, stop_price=97.0, direction="LONG", ind_row=ind, config=CONFIG)
    assert target == pytest.approx(110.0)


def test_target_prev_support_resistance_none_when_no_level_beyond_entry():
    ind = pd.Series({"r1": 90.0, "r2": 95.0, "r3": 99.0})  # all below entry=100
    target = compute_target(TargetMethod.PREV_SUPPORT_RESISTANCE, entry_price=100.0, stop_price=97.0, direction="LONG", ind_row=ind, config=CONFIG)
    assert target is None
