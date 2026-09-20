import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.alerts.conditions import direction_becomes, score_crosses, state_becomes  # noqa: E402


def test_score_crosses_true_on_actual_crossing():
    assert score_crosses(75.0, 82.0, 80.0) is True


def test_score_crosses_false_when_already_above():
    assert score_crosses(85.0, 88.0, 80.0) is False


def test_score_crosses_false_when_falling_through():
    assert score_crosses(85.0, 75.0, 80.0) is False


def test_score_crosses_true_at_exact_threshold():
    assert score_crosses(79.9, 80.0, 80.0) is True


def test_score_crosses_false_with_missing_values():
    assert score_crosses(None, 82.0, 80.0) is False
    assert score_crosses(75.0, None, 80.0) is False
    assert score_crosses(float("nan"), 82.0, 80.0) is False


def test_direction_becomes():
    assert direction_becomes("NONE", "LONG", "LONG") is True
    assert direction_becomes("SHORT", "LONG", "LONG") is True
    assert direction_becomes("LONG", "LONG", "LONG") is False  # already was - not a fresh transition
    assert direction_becomes(None, "LONG", "LONG") is True


def test_state_becomes():
    assert state_becomes("SETUP", "ENTRY_TRIGGER", "ENTRY_TRIGGER") is True
    assert state_becomes("ENTRY_TRIGGER", "ENTRY_TRIGGER", "ENTRY_TRIGGER") is False
    assert state_becomes("POSITION_ACTIVE", "TARGET_HIT", "TARGET_HIT") is True
    assert state_becomes("TARGET_HIT", "TARGET_HIT", "TARGET_HIT") is False  # persisting terminal state, not a new hit
