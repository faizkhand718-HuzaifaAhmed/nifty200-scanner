import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.alerts.config import AlertChannel, AlertConfig, AlertType  # noqa: E402
from app.alerts.engine import AlertEngine  # noqa: E402
from app.alerts.history import AlertHistory  # noqa: E402


def ind(ts=1, close=100.0, vwap=100.0):
    return pd.Series({"timestamp": ts, "close": close, "vwap": vwap})


def setup(long_breakout=False, short_breakdown=False):
    return pd.Series({"long_breakout": long_breakout, "short_breakdown": short_breakdown})


def scoring(long_score=0.0, short_score=0.0):
    return pd.Series({"long_score": long_score, "short_score": short_score})


def test_score_crosses_80_fires_with_correct_direction():
    engine = AlertEngine()
    alerts = engine.evaluate(
        "RELIANCE", ind(ts=2), ind(ts=1), setup(),
        scoring_row=scoring(long_score=82.0), prev_scoring_row=scoring(long_score=75.0),
    )
    types_directions = [(a.alert_type, a.direction) for a in alerts]
    assert (AlertType.SCORE_CROSSES_80, "LONG") in types_directions
    assert (AlertType.SCORE_CROSSES_90, "LONG") not in types_directions


def test_score_crosses_90_fires_separately_from_80():
    engine = AlertEngine()
    alerts = engine.evaluate(
        "RELIANCE", ind(ts=2), ind(ts=1), setup(),
        scoring_row=scoring(long_score=92.0), prev_scoring_row=scoring(long_score=88.0),
    )
    types = [a.alert_type for a in alerts]
    assert AlertType.SCORE_CROSSES_90 in types
    assert AlertType.SCORE_CROSSES_80 not in types  # was already above 80, not a fresh cross


def test_no_score_alert_when_already_above_threshold():
    engine = AlertEngine()
    alerts = engine.evaluate(
        "RELIANCE", ind(ts=2), ind(ts=1), setup(),
        scoring_row=scoring(long_score=85.0), prev_scoring_row=scoring(long_score=84.0),
    )
    assert alerts == []


def test_long_setup_fires_on_direction_transition():
    engine = AlertEngine()
    alerts = engine.evaluate(
        "RELIANCE", ind(ts=1), None, setup(),
        ranking_direction="LONG", prev_ranking_direction="NONE",
    )
    assert len(alerts) == 1
    assert alerts[0].alert_type == AlertType.LONG_SETUP


def test_short_setup_fires_on_direction_transition():
    engine = AlertEngine()
    alerts = engine.evaluate(
        "RELIANCE", ind(ts=1), None, setup(),
        ranking_direction="SHORT", prev_ranking_direction="NONE",
    )
    assert len(alerts) == 1
    assert alerts[0].alert_type == AlertType.SHORT_SETUP


def test_no_setup_alert_when_direction_unchanged():
    engine = AlertEngine()
    alerts = engine.evaluate(
        "RELIANCE", ind(ts=1), None, setup(),
        ranking_direction="LONG", prev_ranking_direction="LONG",
    )
    assert alerts == []


def test_breakout_and_breakdown_fire_from_setup_row():
    engine = AlertEngine()
    alerts = engine.evaluate("RELIANCE", ind(ts=1), None, setup(long_breakout=True))
    assert len(alerts) == 1
    assert alerts[0].alert_type == AlertType.BREAKOUT
    assert alerts[0].direction == "LONG"

    engine2 = AlertEngine()
    alerts2 = engine2.evaluate("RELIANCE", ind(ts=1), None, setup(short_breakdown=True))
    assert alerts2[0].alert_type == AlertType.BREAKDOWN
    assert alerts2[0].direction == "SHORT"


def test_vwap_reclaim_fires_on_crossing():
    engine = AlertEngine()
    prev = ind(ts=1, close=99.0, vwap=100.0)
    curr = ind(ts=2, close=100.5, vwap=100.0)
    alerts = engine.evaluate("RELIANCE", curr, prev, setup())
    assert any(a.alert_type == AlertType.VWAP_RECLAIM for a in alerts)


def test_vwap_rejection_fires_on_crossing_down():
    engine = AlertEngine()
    prev = ind(ts=1, close=101.0, vwap=100.0)
    curr = ind(ts=2, close=99.0, vwap=100.0)
    alerts = engine.evaluate("RELIANCE", curr, prev, setup())
    assert any(a.alert_type == AlertType.VWAP_REJECTION for a in alerts)


def test_entry_trigger_stop_loss_target_fire_on_lifecycle_transitions():
    engine = AlertEngine()

    entry_alerts = engine.evaluate(
        "RELIANCE", ind(ts=1), None, setup(),
        lifecycle_state="ENTRY_TRIGGER", prev_lifecycle_state="SETUP", lifecycle_direction="LONG",
    )
    assert entry_alerts[0].alert_type == AlertType.ENTRY_TRIGGER

    target_alerts = engine.evaluate(
        "RELIANCE", ind(ts=2), None, setup(),
        lifecycle_state="TARGET_HIT", prev_lifecycle_state="POSITION_ACTIVE", lifecycle_direction="LONG",
    )
    assert target_alerts[0].alert_type == AlertType.TARGET

    # Terminal state persisting on a further bar must NOT re-fire.
    no_more_alerts = engine.evaluate(
        "RELIANCE", ind(ts=3), None, setup(),
        lifecycle_state="TARGET_HIT", prev_lifecycle_state="TARGET_HIT", lifecycle_direction="LONG",
    )
    assert no_more_alerts == []


def test_stop_loss_alert():
    engine = AlertEngine()
    alerts = engine.evaluate(
        "RELIANCE", ind(ts=1), None, setup(),
        lifecycle_state="STOP_LOSS_HIT", prev_lifecycle_state="POSITION_ACTIVE", lifecycle_direction="SHORT",
    )
    assert alerts[0].alert_type == AlertType.STOP_LOSS
    assert alerts[0].direction == "SHORT"


def test_duplicate_alert_for_same_candle_is_suppressed():
    """The central requirement: processing the exact same bar twice must
    not produce the alert twice."""
    history = AlertHistory()
    engine = AlertEngine(history=history)

    curr, prev = ind(ts=2), ind(ts=1)
    scoring_curr = scoring(long_score=82.0)
    scoring_prev = scoring(long_score=75.0)

    first = engine.evaluate("RELIANCE", curr, prev, setup(), scoring_row=scoring_curr, prev_scoring_row=scoring_prev)
    second = engine.evaluate("RELIANCE", curr, prev, setup(), scoring_row=scoring_curr, prev_scoring_row=scoring_prev)

    assert len(first) == 1
    assert second == []
    assert len(history) == 1


def test_disabled_alert_type_never_fires():
    config = AlertConfig(enabled_types={AlertType.BREAKOUT})  # only breakout enabled
    engine = AlertEngine(config=config)
    alerts = engine.evaluate(
        "RELIANCE", ind(ts=2), ind(ts=1), setup(),
        scoring_row=scoring(long_score=95.0), prev_scoring_row=scoring(long_score=50.0),
    )
    # score crossed both 80 and 90, but neither type is enabled
    assert alerts == []


def test_channels_assigned_per_config():
    config = AlertConfig(channels={AlertType.BREAKOUT: {AlertChannel.SOUND}})
    engine = AlertEngine(config=config)
    alerts = engine.evaluate("RELIANCE", ind(ts=1), None, setup(long_breakout=True))
    assert alerts[0].channels == {AlertChannel.SOUND}


def test_missing_optional_inputs_do_not_crash():
    engine = AlertEngine()
    # Only the required params supplied - everything else defaults to None.
    alerts = engine.evaluate("RELIANCE", ind(ts=1), None, setup())
    assert alerts == []


def test_different_symbols_do_not_share_dedup_state():
    history = AlertHistory()
    engine = AlertEngine(history=history)
    a1 = engine.evaluate("RELIANCE", ind(ts=1), None, setup(long_breakout=True))
    a2 = engine.evaluate("TCS", ind(ts=1), None, setup(long_breakout=True))
    assert len(a1) == 1
    assert len(a2) == 1  # same candle timestamp, different symbol - not a duplicate
