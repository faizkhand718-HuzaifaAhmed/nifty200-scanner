import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.entry_engine.config import EntryEngineConfig, EntryMethod, StopMethod, TargetMethod  # noqa: E402
from app.entry_engine.state_machine import TradeLifecycle  # noqa: E402
from app.entry_engine.states import TradeState  # noqa: E402


def make_row(**kwargs) -> pd.Series:
    base = {
        "timestamp": 0, "close": 100.0, "high": 100.0, "low": 100.0,
        "resistance": float("nan"), "support": float("nan"), "atr": float("nan"),
        "swing_low_price": float("nan"), "swing_high_price": float("nan"),
        "r1": float("nan"), "r2": float("nan"), "r3": float("nan"),
        "s1": float("nan"), "s2": float("nan"), "s3": float("nan"),
    }
    base.update(kwargs)
    return pd.Series(base)


def make_setup_row(**kwargs) -> pd.Series:
    base = {"long_breakout": False, "long_retest": False, "short_breakdown": False, "short_retest": False}
    base.update(kwargs)
    return pd.Series(base)


def default_config(**overrides) -> EntryEngineConfig:
    cfg = EntryEngineConfig(entry_method=EntryMethod.BREAKOUT, stop_method=StopMethod.SUPPORT_RESISTANCE, target_method=TargetMethod.RISK_REWARD_2)
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def test_full_happy_path_setup_to_target_hit():
    lifecycle = TradeLifecycle("LONG", default_config())

    bars = [
        (make_row(close=98.0, high=99.0, low=97.0, resistance=100.0, support=90.0), make_setup_row()),
        (make_row(close=99.8, high=100.0, low=99.0, resistance=100.0, support=90.0), make_setup_row()),
        (make_row(close=101.0, high=101.5, low=99.5, resistance=100.0, support=90.0), make_setup_row(long_breakout=True)),
        (make_row(close=105.0, high=106.0, low=104.0, resistance=100.0, support=90.0), make_setup_row()),
        (make_row(close=124.0, high=125.0, low=123.0, resistance=100.0, support=90.0), make_setup_row()),
        (make_row(close=130.0, high=131.0, low=129.0, resistance=100.0, support=90.0), make_setup_row()),
    ]

    states = []
    prev_ind = None
    for ind, setup in bars:
        states.append(lifecycle.step(ind, prev_ind, setup))
        prev_ind = ind

    assert states == [
        TradeState.SETUP,
        TradeState.CONFIRMATION,   # close within 0.3% of resistance
        TradeState.ENTRY_TRIGGER,  # long_breakout fires
        TradeState.POSITION_ACTIVE,
        TradeState.TARGET_HIT,     # high=125 >= target
        TradeState.TARGET_HIT,     # terminal - stays
    ]
    assert lifecycle.entry_price == pytest.approx(101.0)
    assert lifecycle.stop == pytest.approx(90.0)   # support at trigger bar
    assert lifecycle.target == pytest.approx(101.0 + 2 * (101.0 - 90.0))  # RR 1:2


def test_stop_loss_hit_path():
    lifecycle = TradeLifecycle("LONG", default_config())
    bars = [
        (make_row(close=101.0, high=101.5, low=99.5, resistance=100.0, support=90.0), make_setup_row(long_breakout=True)),
        (make_row(close=85.0, high=101.0, low=80.0, resistance=100.0, support=90.0), make_setup_row()),
    ]
    states = []
    prev_ind = None
    for ind, setup in bars:
        states.append(lifecycle.step(ind, prev_ind, setup))
        prev_ind = ind
    assert states == [TradeState.ENTRY_TRIGGER, TradeState.STOP_LOSS_HIT]


def test_same_bar_stop_and_target_conflict_resolves_to_stop():
    lifecycle = TradeLifecycle("LONG", default_config())
    trigger_bar = make_row(close=101.0, high=101.5, low=99.5, resistance=100.0, support=90.0)
    # stop=90, target=101+2*11=123. This bar's range covers both.
    conflict_bar = make_row(close=100.0, high=130.0, low=80.0, resistance=100.0, support=90.0)

    s1 = lifecycle.step(trigger_bar, None, make_setup_row(long_breakout=True))
    s2 = lifecycle.step(conflict_bar, trigger_bar, make_setup_row())
    assert s1 == TradeState.ENTRY_TRIGGER
    assert s2 == TradeState.STOP_LOSS_HIT


def test_invalidated_when_support_breached_before_entry():
    lifecycle = TradeLifecycle("LONG", default_config())
    bars = [
        (make_row(close=98.0, high=99.0, low=97.0, resistance=100.0, support=95.0), make_setup_row()),
        (make_row(close=94.0, high=98.0, low=93.0, resistance=100.0, support=95.0), make_setup_row()),
    ]
    states = []
    prev_ind = None
    for ind, setup in bars:
        states.append(lifecycle.step(ind, prev_ind, setup))
        prev_ind = ind
    assert states == [TradeState.SETUP, TradeState.INVALIDATED]


def test_invalidation_does_not_fire_alongside_trigger_on_same_bar():
    """A bar that both breaks support AND triggers breakout is a
    contradiction that shouldn't happen with real data, but the
    invalidation check must win (checked first) rather than silently
    entering a structurally-broken setup."""
    lifecycle = TradeLifecycle("LONG", default_config())
    bar = make_row(close=94.0, high=99.0, low=93.0, resistance=100.0, support=95.0)
    state = lifecycle.step(bar, None, make_setup_row(long_breakout=True))
    assert state == TradeState.INVALIDATED


def test_invalidated_after_max_bars_without_trigger():
    lifecycle = TradeLifecycle("LONG", default_config(max_bars_without_trigger=2))
    far_bar = make_row(close=50.0, high=51.0, low=49.0, resistance=100.0, support=10.0)
    states = []
    prev_ind = None
    for _ in range(3):
        states.append(lifecycle.step(far_bar, prev_ind, make_setup_row()))
        prev_ind = far_bar
    assert states == [TradeState.SETUP, TradeState.SETUP, TradeState.INVALIDATED]


def test_terminal_states_never_change_on_further_bars():
    lifecycle = TradeLifecycle("LONG", default_config())
    lifecycle.step(
        make_row(close=101.0, high=101.5, low=99.5, resistance=100.0, support=90.0), None, make_setup_row(long_breakout=True)
    )
    lifecycle.step(
        make_row(close=124.0, high=125.0, low=123.0, resistance=100.0, support=90.0),
        make_row(close=101.0, high=101.5, low=99.5, resistance=100.0, support=90.0),
        make_setup_row(),
    )
    assert lifecycle.state == TradeState.TARGET_HIT
    frozen_stop, frozen_target, frozen_entry = lifecycle.stop, lifecycle.target, lifecycle.entry_price

    # Feed a bunch more bars, including ones that would look like a fresh
    # breakout - terminal state must not budge.
    for _ in range(5):
        state = lifecycle.step(
            make_row(close=999.0, high=1000.0, low=998.0, resistance=100.0, support=90.0),
            None,
            make_setup_row(long_breakout=True),
        )
        assert state == TradeState.TARGET_HIT

    assert (lifecycle.stop, lifecycle.target, lifecycle.entry_price) == (frozen_stop, frozen_target, frozen_entry)


def test_construction_rejects_incompatible_direction_and_method():
    with pytest.raises(ValueError, match="not valid for SHORT"):
        TradeLifecycle("SHORT", EntryEngineConfig(entry_method=EntryMethod.BREAKOUT))
    with pytest.raises(ValueError, match="not valid for LONG"):
        TradeLifecycle("LONG", EntryEngineConfig(entry_method=EntryMethod.BREAKDOWN))


def test_construction_rejects_bad_direction_string():
    with pytest.raises(ValueError):
        TradeLifecycle("UP", EntryEngineConfig())


def test_never_enters_merely_because_a_high_score_is_present():
    """Behavioral companion to the architectural import-check test: even
    if an (irrelevant, never-read) high opportunity_score column is
    present on the row, the state machine must not enter without the
    actual configured trigger firing."""
    lifecycle = TradeLifecycle("LONG", default_config())
    bar_with_high_score = make_row(
        close=50.0, high=51.0, low=49.0, resistance=100.0, support=10.0, opportunity_score=99.0
    )
    state = lifecycle.step(bar_with_high_score, None, make_setup_row(long_breakout=False))
    assert state in (TradeState.SETUP, TradeState.CONFIRMATION)
    assert lifecycle.entry_price is None


def test_swing_stop_method_end_to_end():
    lifecycle = TradeLifecycle("LONG", default_config(stop_method=StopMethod.SWING))
    bars = [
        (make_row(close=98.0, high=99.0, low=95.0, resistance=100.0, swing_low_price=95.0), make_setup_row()),
        (make_row(close=101.0, high=101.5, low=99.5, resistance=100.0), make_setup_row(long_breakout=True)),
    ]
    prev_ind = None
    states = []
    for ind, setup in bars:
        states.append(lifecycle.step(ind, prev_ind, setup))
        prev_ind = ind
    assert states[-1] == TradeState.ENTRY_TRIGGER
    assert lifecycle.stop == pytest.approx(95.0)  # remembered from the earlier bar, not the trigger bar itself


def test_run_produces_dataframe_matching_bar_count():
    lifecycle = TradeLifecycle("LONG", default_config())
    indicators_df = pd.DataFrame(
        [
            make_row(timestamp=1, close=98.0, high=99.0, low=97.0, resistance=100.0, support=90.0),
            make_row(timestamp=2, close=101.0, high=101.5, low=99.5, resistance=100.0, support=90.0),
            make_row(timestamp=3, close=124.0, high=125.0, low=123.0, resistance=100.0, support=90.0),
        ]
    )
    setup_df = pd.DataFrame(
        [make_setup_row(), make_setup_row(long_breakout=True), make_setup_row()]
    )
    result = lifecycle.run(indicators_df, setup_df)
    assert list(result["lifecycle_state"]) == ["SETUP", "ENTRY_TRIGGER", "TARGET_HIT"]
    assert list(result["timestamp"]) == [1, 2, 3]
    assert result["entry_price"].iloc[0] is None or pd.isna(result["entry_price"].iloc[0])
    assert result["entry_price"].iloc[1] == pytest.approx(101.0)


def test_run_rejects_mismatched_row_counts():
    lifecycle = TradeLifecycle("LONG", default_config())
    indicators_df = pd.DataFrame([make_row()])
    setup_df = pd.DataFrame([make_setup_row(), make_setup_row()])
    with pytest.raises(ValueError, match="same number of rows"):
        lifecycle.run(indicators_df, setup_df)
