import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.brokers.base import BrokerAdapter  # noqa: E402
from app.brokers.factory import (  # noqa: E402
    BrokerFactoryConfig,
    BrokerMode,
    create_broker_adapter,
    register_live_broker,
    registered_live_brokers,
    _LIVE_ADAPTER_FACTORIES,
)
from app.brokers.mock_adapter import MockBrokerAdapter  # noqa: E402
from app.brokers.models import AccountInfo, AuthResult  # noqa: E402
from app.brokers.paper_adapter import PaperBrokerAdapter  # noqa: E402
from app.brokers.safety import LiveTradingConfig  # noqa: E402


def test_default_mode_is_paper():
    assert BrokerFactoryConfig().mode == BrokerMode.PAPER


def test_default_config_creates_a_paper_adapter():
    adapter = create_broker_adapter(BrokerFactoryConfig())
    assert isinstance(adapter, PaperBrokerAdapter)
    assert adapter.is_live is False


def test_mock_mode_creates_a_mock_adapter():
    adapter = create_broker_adapter(BrokerFactoryConfig(mode=BrokerMode.MOCK))
    assert isinstance(adapter, MockBrokerAdapter)


def test_live_mode_fails_when_flag_disabled():
    config = BrokerFactoryConfig(mode=BrokerMode.LIVE, live_trading_config=LiveTradingConfig(live_trading_enabled=False))
    with pytest.raises(RuntimeError, match="live_trading_enabled is False"):
        create_broker_adapter(config)


def test_live_mode_fails_even_with_flag_enabled_when_nothing_registered():
    """The central requirement: enabling the flag alone must NOT be
    sufficient to get a live adapter if no real broker is registered -
    this system doesn't hard-code any specific broker, so by default
    there is nothing to select."""
    assert _LIVE_ADAPTER_FACTORIES == {}  # sanity: nothing registered in this test run yet
    config = BrokerFactoryConfig(mode=BrokerMode.LIVE, live_trading_config=LiveTradingConfig(live_trading_enabled=True))
    with pytest.raises(NotImplementedError, match="No real broker adapter is registered"):
        create_broker_adapter(config)


class FakeRegisteredLiveAdapter(BrokerAdapter):
    @property
    def is_live(self) -> bool:
        return True

    def authenticate(self, credentials):
        return AuthResult(success=True)

    def get_account_info(self):
        return AccountInfo(account_id="X", available_margin=0, used_margin=0, total_balance=0)

    def get_positions(self):
        return []

    def place_order(self, order):
        raise NotImplementedError

    def get_order_status(self, order_id):
        raise NotImplementedError

    def cancel_order(self, order_id):
        raise NotImplementedError

    def modify_order(self, order_id, modification):
        raise NotImplementedError

    def get_market_data(self, symbol):
        return None


def test_registering_a_live_broker_makes_it_selectable():
    register_live_broker("test-broker", FakeRegisteredLiveAdapter)
    try:
        assert "test-broker" in registered_live_brokers()
        config = BrokerFactoryConfig(mode=BrokerMode.LIVE, live_trading_config=LiveTradingConfig(live_trading_enabled=True))
        adapter = create_broker_adapter(config, live_broker_name="test-broker")
        assert isinstance(adapter, FakeRegisteredLiveAdapter)
        assert adapter.is_live is True
    finally:
        _LIVE_ADAPTER_FACTORIES.pop("test-broker", None)


def test_registered_but_unnamed_selection_requires_explicit_name():
    register_live_broker("test-broker-2", FakeRegisteredLiveAdapter)
    try:
        config = BrokerFactoryConfig(mode=BrokerMode.LIVE, live_trading_config=LiveTradingConfig(live_trading_enabled=True))
        with pytest.raises(ValueError, match="ambiguous"):
            create_broker_adapter(config)  # no live_broker_name given
    finally:
        _LIVE_ADAPTER_FACTORIES.pop("test-broker-2", None)


def test_registered_adapter_that_lies_about_is_live_is_rejected():
    class FakeNonLiveAdapter(FakeRegisteredLiveAdapter):
        @property
        def is_live(self) -> bool:
            return False  # misconfigured - claims live mode but isn't

    register_live_broker("liar-broker", FakeNonLiveAdapter)
    try:
        config = BrokerFactoryConfig(mode=BrokerMode.LIVE, live_trading_config=LiveTradingConfig(live_trading_enabled=True))
        with pytest.raises(RuntimeError, match="is_live=False"):
            create_broker_adapter(config, live_broker_name="liar-broker")
    finally:
        _LIVE_ADAPTER_FACTORIES.pop("liar-broker", None)


def test_unknown_broker_name_raises():
    config = BrokerFactoryConfig(mode=BrokerMode.LIVE, live_trading_config=LiveTradingConfig(live_trading_enabled=True))
    register_live_broker("some-other-broker", FakeRegisteredLiveAdapter)
    try:
        with pytest.raises(ValueError, match="no live broker registered"):
            create_broker_adapter(config, live_broker_name="totally-unknown")
    finally:
        _LIVE_ADAPTER_FACTORIES.pop("some-other-broker", None)
