import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.entry_engine.config import EntryEngineConfig  # noqa: E402
from app.entry_engine.entry_methods import (  # noqa: E402
    BarContext,
    breakdown,
    breakout,
    ema_confirmation,
    opening_range_breakout,
    retest,
    vwap_reclaim,
    vwap_rejection,
)

CONFIG = EntryEngineConfig()  # approach_tolerance_pct=0.003, ema_convergence=0.002


def test_breakout_triggers_from_setup_flag():
    ind = pd.Series({"close": 105.0, "resistance": 100.0})
    setup = pd.Series({"long_breakout": True})
    ctx = BarContext(ind=ind, prev_ind=None, setup=setup, direction="LONG")
    approaching, triggered = breakout(ctx, CONFIG)
    assert triggered is True
    assert approaching is False


def test_breakout_approaching_within_tolerance():
    # close=99.8, resistance=100 -> (100-99.8)/100 = 0.002 <= 0.003 tolerance
    ind = pd.Series({"close": 99.8, "resistance": 100.0})
    setup = pd.Series({"long_breakout": False})
    ctx = BarContext(ind=ind, prev_ind=None, setup=setup, direction="LONG")
    approaching, triggered = breakout(ctx, CONFIG)
    assert triggered is False
    assert approaching is True


def test_breakout_not_approaching_when_far():
    ind = pd.Series({"close": 90.0, "resistance": 100.0})
    setup = pd.Series({"long_breakout": False})
    ctx = BarContext(ind=ind, prev_ind=None, setup=setup, direction="LONG")
    approaching, triggered = breakout(ctx, CONFIG)
    assert triggered is False
    assert approaching is False


def test_breakdown_triggers_from_setup_flag():
    ind = pd.Series({"close": 90.0, "support": 95.0})
    setup = pd.Series({"short_breakdown": True})
    ctx = BarContext(ind=ind, prev_ind=None, setup=setup, direction="SHORT")
    approaching, triggered = breakdown(ctx, CONFIG)
    assert triggered is True


def test_vwap_reclaim_triggers_on_crossing():
    prev_ind = pd.Series({"close": 99.0, "vwap": 100.0})
    ind = pd.Series({"close": 100.5, "vwap": 100.0})
    ctx = BarContext(ind=ind, prev_ind=prev_ind, setup=pd.Series({}), direction="LONG")
    approaching, triggered = vwap_reclaim(ctx, CONFIG)
    assert triggered is True


def test_vwap_reclaim_no_trigger_if_already_above():
    prev_ind = pd.Series({"close": 101.0, "vwap": 100.0})
    ind = pd.Series({"close": 101.5, "vwap": 100.0})
    ctx = BarContext(ind=ind, prev_ind=prev_ind, setup=pd.Series({}), direction="LONG")
    approaching, triggered = vwap_reclaim(ctx, CONFIG)
    assert triggered is False  # was already above, not a fresh reclaim


def test_vwap_reclaim_none_without_prev_bar():
    ind = pd.Series({"close": 100.5, "vwap": 100.0})
    ctx = BarContext(ind=ind, prev_ind=None, setup=pd.Series({}), direction="LONG")
    approaching, triggered = vwap_reclaim(ctx, CONFIG)
    assert (approaching, triggered) == (False, False)


def test_vwap_rejection_triggers_on_crossing_down():
    prev_ind = pd.Series({"close": 101.0, "vwap": 100.0})
    ind = pd.Series({"close": 99.0, "vwap": 100.0})
    ctx = BarContext(ind=ind, prev_ind=prev_ind, setup=pd.Series({}), direction="SHORT")
    approaching, triggered = vwap_rejection(ctx, CONFIG)
    assert triggered is True


def test_ema_confirmation_long_triggers_on_crossover():
    ind = pd.Series({"close": 101.0, "ema_9": 100.5, "ema_20": 100.0})
    ctx = BarContext(ind=ind, prev_ind=None, setup=pd.Series({}), direction="LONG")
    approaching, triggered = ema_confirmation(ctx, CONFIG)
    assert triggered is True


def test_ema_confirmation_long_approaching_when_converging():
    # ema9=99.9, ema20=100.0 -> (100-99.9)/100 = 0.001 <= 0.002 tolerance
    ind = pd.Series({"close": 99.5, "ema_9": 99.9, "ema_20": 100.0})
    ctx = BarContext(ind=ind, prev_ind=None, setup=pd.Series({}), direction="LONG")
    approaching, triggered = ema_confirmation(ctx, CONFIG)
    assert triggered is False
    assert approaching is True


def test_ema_confirmation_short_triggers_on_crossunder():
    ind = pd.Series({"close": 99.0, "ema_9": 99.5, "ema_20": 100.0})
    ctx = BarContext(ind=ind, prev_ind=None, setup=pd.Series({}), direction="SHORT")
    approaching, triggered = ema_confirmation(ctx, CONFIG)
    assert triggered is True


def test_opening_range_breakout_long():
    ind = pd.Series({"close": 105.0, "opening_range_high": 100.0})
    ctx = BarContext(ind=ind, prev_ind=None, setup=pd.Series({}), direction="LONG")
    approaching, triggered = opening_range_breakout(ctx, CONFIG)
    assert triggered is True


def test_opening_range_breakout_short():
    ind = pd.Series({"close": 90.0, "opening_range_low": 95.0})
    ctx = BarContext(ind=ind, prev_ind=None, setup=pd.Series({}), direction="SHORT")
    approaching, triggered = opening_range_breakout(ctx, CONFIG)
    assert triggered is True


def test_retest_triggers_from_setup_flag():
    ind = pd.Series({})
    setup = pd.Series({"long_retest": True, "long_breakout": False})
    ctx = BarContext(ind=ind, prev_ind=None, setup=setup, direction="LONG")
    approaching, triggered = retest(ctx, CONFIG)
    assert triggered is True


def test_retest_approaching_after_breakout_before_retest():
    setup = pd.Series({"long_retest": False, "long_breakout": True})
    ctx = BarContext(ind=pd.Series({}), prev_ind=None, setup=setup, direction="LONG")
    approaching, triggered = retest(ctx, CONFIG)
    assert triggered is False
    assert approaching is True


def test_methods_return_false_false_on_missing_data():
    ind = pd.Series({"close": 100.0})  # no resistance column at all
    setup = pd.Series({"long_breakout": False})
    ctx = BarContext(ind=ind, prev_ind=None, setup=setup, direction="LONG")
    approaching, triggered = breakout(ctx, CONFIG)
    assert (approaching, triggered) == (False, False)
