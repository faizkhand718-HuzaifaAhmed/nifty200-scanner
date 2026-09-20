import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.brokers.exceptions import OrderNotFoundError  # noqa: E402
from app.brokers.models import OrderRequest  # noqa: E402
from app.brokers.paper_adapter import PaperBrokerAdapter  # noqa: E402
from app.paper_trading.engine import PaperTradingEngine  # noqa: E402


def test_is_live_is_false():
    assert PaperBrokerAdapter().is_live is False


def test_place_order_requires_explicit_price():
    adapter = PaperBrokerAdapter()
    result = adapter.place_order(OrderRequest(symbol="RELIANCE", direction="LONG", quantity=10))  # no price
    assert result.success is False
    assert "price" in result.message.lower()


def test_place_order_with_price_opens_a_paper_position():
    engine = PaperTradingEngine()
    adapter = PaperBrokerAdapter(engine=engine)
    result = adapter.place_order(OrderRequest(symbol="RELIANCE", direction="LONG", quantity=10, price=2900.0, trigger_price=2870.0))
    assert result.success is True
    assert result.order_id is not None

    open_positions = engine.get_open_positions()
    assert len(open_positions) == 1
    assert open_positions[0].symbol == "RELIANCE"
    assert open_positions[0].stop_loss == pytest.approx(2870.0)


def test_get_positions_reflects_engine_state():
    engine = PaperTradingEngine()
    adapter = PaperBrokerAdapter(engine=engine)
    adapter.place_order(OrderRequest(symbol="RELIANCE", direction="LONG", quantity=10, price=2900.0))
    positions = adapter.get_positions()
    assert len(positions) == 1
    assert positions[0].symbol == "RELIANCE"
    assert positions[0].average_price == pytest.approx(2900.0)


def test_get_account_info_reflects_realized_pnl():
    engine = PaperTradingEngine()
    adapter = PaperBrokerAdapter(engine=engine, account_capital=100000.0)
    position = engine.open_position("RELIANCE", "LONG", 100.0, 10, 95.0, 115.0, entry_time=1)
    engine.close_position_manually(position.id, exit_time=2, exit_price=110.0)  # +100 pnl

    info = adapter.get_account_info()
    assert info.total_balance == pytest.approx(100100.0)  # 100000 + 100 realized


def test_get_order_status_after_place():
    engine = PaperTradingEngine()
    adapter = PaperBrokerAdapter(engine=engine)
    result = adapter.place_order(OrderRequest(symbol="RELIANCE", direction="LONG", quantity=10, price=2900.0))
    status = adapter.get_order_status(result.order_id)
    assert status.filled_quantity == 10
    assert status.average_fill_price == pytest.approx(2900.0)


def test_get_order_status_unknown_id_raises():
    adapter = PaperBrokerAdapter()
    with pytest.raises(OrderNotFoundError):
        adapter.get_order_status("does-not-exist")


def test_cancel_order_always_fails_with_clear_message():
    engine = PaperTradingEngine()
    adapter = PaperBrokerAdapter(engine=engine)
    result = adapter.place_order(OrderRequest(symbol="RELIANCE", direction="LONG", quantity=10, price=2900.0))
    cancel_result = adapter.cancel_order(result.order_id)
    assert cancel_result.success is False
    assert "fill instantly" in cancel_result.message


def test_get_market_data_returns_none():
    assert PaperBrokerAdapter().get_market_data("RELIANCE") is None
