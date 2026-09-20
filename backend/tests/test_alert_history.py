import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.alerts.config import AlertChannel, AlertType  # noqa: E402
from app.alerts.history import AlertHistory  # noqa: E402
from app.alerts.models import Alert  # noqa: E402


def make_alert(symbol="RELIANCE", alert_type=AlertType.BREAKOUT, direction="LONG", ts=1) -> Alert:
    return Alert(
        symbol=symbol, alert_type=alert_type, direction=direction, message="test",
        candle_timestamp=ts, fired_at=datetime.now(timezone.utc), channels={AlertChannel.DASHBOARD},
    )


def test_has_fired_false_before_add():
    history = AlertHistory()
    alert = make_alert()
    assert history.has_fired(alert.dedup_key) is False


def test_has_fired_true_after_add():
    history = AlertHistory()
    alert = make_alert()
    history.add(alert)
    assert history.has_fired(alert.dedup_key) is True


def test_different_candle_timestamp_is_not_a_duplicate():
    history = AlertHistory()
    history.add(make_alert(ts=1))
    assert history.has_fired(make_alert(ts=2).dedup_key) is False


def test_different_direction_is_not_a_duplicate():
    history = AlertHistory()
    history.add(make_alert(direction="LONG"))
    assert history.has_fired(make_alert(direction="SHORT").dedup_key) is False


def test_list_most_recent_first():
    history = AlertHistory()
    history.add(make_alert(ts=1))
    history.add(make_alert(ts=2))
    history.add(make_alert(ts=3))
    result = history.list()
    assert [a.candle_timestamp for a in result] == [3, 2, 1]


def test_list_filters_by_symbol():
    history = AlertHistory()
    history.add(make_alert(symbol="RELIANCE", ts=1))
    history.add(make_alert(symbol="TCS", ts=2))
    result = history.list(symbol="TCS")
    assert len(result) == 1
    assert result[0].symbol == "TCS"


def test_list_filters_by_type():
    history = AlertHistory()
    history.add(make_alert(alert_type=AlertType.BREAKOUT, ts=1))
    history.add(make_alert(alert_type=AlertType.TARGET, ts=2))
    result = history.list(alert_type=AlertType.TARGET)
    assert len(result) == 1
    assert result[0].alert_type == AlertType.TARGET


def test_list_respects_limit():
    history = AlertHistory()
    for i in range(5):
        history.add(make_alert(ts=i))
    assert len(history.list(limit=2)) == 2


def test_clear_resets_dedup_state():
    history = AlertHistory()
    alert = make_alert()
    history.add(alert)
    history.clear()
    assert history.has_fired(alert.dedup_key) is False
    assert len(history) == 0
