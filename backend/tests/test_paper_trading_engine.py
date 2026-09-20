import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.paper_trading.engine import PaperTradingEngine  # noqa: E402


def test_open_position_appears_in_open_list():
    engine = PaperTradingEngine()
    position = engine.open_position("RELIANCE", "LONG", 100.0, 200, 95.0, 115.0, entry_time=1)
    assert position.is_open is True
    assert engine.get_open_positions() == [position]
    assert engine.get_closed_positions() == []


def test_open_position_rejects_non_positive_quantity():
    engine = PaperTradingEngine()
    with pytest.raises(ValueError):
        engine.open_position("RELIANCE", "LONG", 100.0, 0, 95.0, 115.0, entry_time=1)


def test_open_position_rejects_bad_direction():
    engine = PaperTradingEngine()
    with pytest.raises(ValueError):
        engine.open_position("RELIANCE", "UP", 100.0, 100, 95.0, 115.0, entry_time=1)


def test_update_open_positions_closes_on_target_hit():
    engine = PaperTradingEngine()
    engine.open_position("RELIANCE", "LONG", 100.0, 200, 95.0, 115.0, entry_time=1)
    closed = engine.update_open_positions("RELIANCE", timestamp=2, high=116.0, low=110.0)
    assert len(closed) == 1
    assert closed[0].exit_reason == "TARGET_HIT"
    assert engine.get_open_positions() == []
    assert len(engine.get_closed_positions()) == 1


def test_update_open_positions_closes_on_stop_hit():
    engine = PaperTradingEngine()
    engine.open_position("RELIANCE", "LONG", 100.0, 200, 95.0, 115.0, entry_time=1)
    closed = engine.update_open_positions("RELIANCE", timestamp=2, high=101.0, low=93.0)
    assert closed[0].exit_reason == "STOP_LOSS_HIT"


def test_update_open_positions_same_bar_conflict_resolves_to_stop():
    engine = PaperTradingEngine()
    engine.open_position("RELIANCE", "LONG", 100.0, 200, 95.0, 115.0, entry_time=1)
    closed = engine.update_open_positions("RELIANCE", timestamp=2, high=120.0, low=90.0)
    assert closed[0].exit_reason == "STOP_LOSS_HIT"


def test_update_open_positions_no_change_when_neither_hit():
    engine = PaperTradingEngine()
    engine.open_position("RELIANCE", "LONG", 100.0, 200, 95.0, 115.0, entry_time=1)
    closed = engine.update_open_positions("RELIANCE", timestamp=2, high=105.0, low=98.0)
    assert closed == []
    assert len(engine.get_open_positions()) == 1


def test_update_open_positions_only_affects_matching_symbol():
    engine = PaperTradingEngine()
    engine.open_position("RELIANCE", "LONG", 100.0, 200, 95.0, 115.0, entry_time=1)
    engine.open_position("TCS", "LONG", 3000.0, 10, 2900.0, 3200.0, entry_time=1)
    engine.update_open_positions("RELIANCE", timestamp=2, high=116.0, low=110.0)
    open_symbols = {p.symbol for p in engine.get_open_positions()}
    assert open_symbols == {"TCS"}


def test_close_position_manually():
    engine = PaperTradingEngine()
    position = engine.open_position("RELIANCE", "LONG", 100.0, 200, 95.0, 115.0, entry_time=1)
    closed = engine.close_position_manually(position.id, exit_time=2, exit_price=103.0)
    assert closed.exit_reason == "MANUAL_CLOSE"
    assert closed.pnl == pytest.approx(600.0)


def test_close_position_manually_rejects_unknown_id():
    engine = PaperTradingEngine()
    with pytest.raises(KeyError):
        engine.close_position_manually("nonexistent", exit_time=2, exit_price=103.0)


def test_close_position_manually_rejects_already_closed():
    engine = PaperTradingEngine()
    position = engine.open_position("RELIANCE", "LONG", 100.0, 200, 95.0, 115.0, entry_time=1)
    engine.close_position_manually(position.id, exit_time=2, exit_price=103.0)
    with pytest.raises(ValueError):
        engine.close_position_manually(position.id, exit_time=3, exit_price=104.0)


def test_multiple_open_and_closed_positions_tracked_correctly():
    engine = PaperTradingEngine()
    p1 = engine.open_position("RELIANCE", "LONG", 100.0, 200, 95.0, 115.0, entry_time=1)
    p2 = engine.open_position("TCS", "LONG", 3000.0, 10, 2900.0, 3200.0, entry_time=1)
    engine.close_position_manually(p1.id, exit_time=2, exit_price=110.0)
    assert len(engine.get_open_positions()) == 1
    assert engine.get_open_positions()[0].id == p2.id
    assert len(engine.get_closed_positions()) == 1
    assert engine.get_closed_positions()[0].id == p1.id


def test_short_position_stop_and_target_directions():
    engine = PaperTradingEngine()
    engine.open_position("ZOMATO", "SHORT", 100.0, 200, 105.0, 85.0, entry_time=1)
    # price rallies toward stop (above entry for a short)
    closed = engine.update_open_positions("ZOMATO", timestamp=2, high=106.0, low=100.0)
    assert closed[0].exit_reason == "STOP_LOSS_HIT"
