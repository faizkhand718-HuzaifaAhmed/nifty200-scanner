import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.brokers.exceptions import OrderNotFoundError  # noqa: E402
from app.brokers.mock_adapter import MockBrokerAdapter  # noqa: E402
from app.brokers.models import BrokerCredentials, OrderModification, OrderRequest, OrderState, OrderType  # noqa: E402


def test_is_live_is_false():
    assert MockBrokerAdapter().is_live is False


def test_authenticate_always_succeeds():
    adapter = MockBrokerAdapter()
    result = adapter.authenticate(BrokerCredentials())  # even empty credentials
    assert result.success is True


def test_get_account_info_reflects_starting_balance():
    adapter = MockBrokerAdapter(starting_balance=50000.0)
    info = adapter.get_account_info()
    assert info.total_balance == pytest.approx(50000.0)


def test_place_order_returns_a_filled_order():
    adapter = MockBrokerAdapter()
    result = adapter.place_order(OrderRequest(symbol="RELIANCE", direction="LONG", quantity=10, order_type=OrderType.MARKET))
    assert result.success is True
    assert result.order_id is not None

    status = adapter.get_order_status(result.order_id)
    assert status.state == OrderState.COMPLETE
    assert status.filled_quantity == 10


def test_place_order_creates_a_position():
    adapter = MockBrokerAdapter()
    adapter.place_order(OrderRequest(symbol="RELIANCE", direction="LONG", quantity=10, price=2900.0))
    positions = adapter.get_positions()
    assert len(positions) == 1
    assert positions[0].symbol == "RELIANCE"
    assert positions[0].quantity == 10
    assert positions[0].average_price == pytest.approx(2900.0)


def test_repeated_orders_in_same_symbol_accumulate_quantity():
    adapter = MockBrokerAdapter()
    adapter.place_order(OrderRequest(symbol="RELIANCE", direction="LONG", quantity=10, price=2900.0))
    adapter.place_order(OrderRequest(symbol="RELIANCE", direction="LONG", quantity=5, price=2905.0))
    positions = adapter.get_positions()
    assert positions[0].quantity == 15


def test_get_order_status_unknown_id_raises():
    adapter = MockBrokerAdapter()
    with pytest.raises(OrderNotFoundError):
        adapter.get_order_status("does-not-exist")


def test_cancel_order_fails_on_already_completed_order():
    # This mock adapter fills orders immediately (COMPLETE), matching how
    # a market order would behave in practice - cancelling a completed
    # order must fail, not silently succeed.
    adapter = MockBrokerAdapter()
    result = adapter.place_order(OrderRequest(symbol="RELIANCE", direction="LONG", quantity=10, price=2900.0))
    cancel_result = adapter.cancel_order(result.order_id)
    assert cancel_result.success is False


def test_cancel_order_unknown_id_raises():
    adapter = MockBrokerAdapter()
    with pytest.raises(OrderNotFoundError):
        adapter.cancel_order("does-not-exist")


def test_modify_order_on_completed_order_fails():
    adapter = MockBrokerAdapter()
    result = adapter.place_order(OrderRequest(symbol="RELIANCE", direction="LONG", quantity=10, price=2900.0))
    modify_result = adapter.modify_order(result.order_id, OrderModification(new_quantity=20))
    assert modify_result.success is False


def test_get_market_data_returns_none_no_fabricated_price():
    adapter = MockBrokerAdapter()
    assert adapter.get_market_data("RELIANCE") is None
