import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.brokers.base import BrokerAdapter  # noqa: E402
from app.brokers.mock_adapter import MockBrokerAdapter  # noqa: E402
from app.brokers.models import AccountInfo, AuthResult, BrokerCredentials  # noqa: E402
from app.brokers.safety import LiveTradingConfig, LiveTradingSafetyGate  # noqa: E402


class FakeLiveAdapter(BrokerAdapter):
    """A duck-typed stand-in that reports is_live=True, without needing a
    real broker implementation - just enough to exercise the safety
    gate's own logic."""

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


COMPLETE_CREDENTIALS = BrokerCredentials(api_key="k", api_secret="s")
INCOMPLETE_CREDENTIALS = BrokerCredentials()


def test_all_checks_pass_with_a_live_adapter_and_everything_enabled():
    gate = LiveTradingSafetyGate(LiveTradingConfig(live_trading_enabled=True))
    result = gate.check(FakeLiveAdapter(), COMPLETE_CREDENTIALS, risk_approved=True)
    assert result.passed is True
    assert result.failed_checks == []


def test_fails_when_flag_is_not_enabled():
    gate = LiveTradingSafetyGate(LiveTradingConfig(live_trading_enabled=False))
    result = gate.check(FakeLiveAdapter(), COMPLETE_CREDENTIALS, risk_approved=True)
    assert result.passed is False
    assert any("LIVE_TRADING_ENABLED" in reason for reason in result.failed_checks)


def test_fails_when_adapter_is_not_live_even_with_flag_enabled():
    """The central requirement: the flag alone is not enough - a non-live
    adapter (mock or paper) must still be rejected."""
    gate = LiveTradingSafetyGate(LiveTradingConfig(live_trading_enabled=True))
    result = gate.check(MockBrokerAdapter(), COMPLETE_CREDENTIALS, risk_approved=True)
    assert result.passed is False
    assert any("not a live adapter" in reason for reason in result.failed_checks)


def test_fails_when_credentials_incomplete():
    gate = LiveTradingSafetyGate(LiveTradingConfig(live_trading_enabled=True))
    result = gate.check(FakeLiveAdapter(), INCOMPLETE_CREDENTIALS, risk_approved=True)
    assert result.passed is False
    assert any("credentials" in reason for reason in result.failed_checks)


def test_fails_when_risk_management_has_not_approved():
    gate = LiveTradingSafetyGate(LiveTradingConfig(live_trading_enabled=True))
    result = gate.check(FakeLiveAdapter(), COMPLETE_CREDENTIALS, risk_approved=False)
    assert result.passed is False
    assert any("risk management" in reason for reason in result.failed_checks)


def test_fails_when_order_value_exceeds_circuit_breaker():
    gate = LiveTradingSafetyGate(LiveTradingConfig(live_trading_enabled=True, max_live_order_value=50000.0))
    result = gate.check(FakeLiveAdapter(), COMPLETE_CREDENTIALS, risk_approved=True, order_value=75000.0)
    assert result.passed is False
    assert any("exceeds the configured max_live_order_value" in reason for reason in result.failed_checks)


def test_multiple_failures_are_all_reported_together():
    """Every check is independent - a caller sees ALL the reasons a live
    trade was blocked, not just the first one."""
    gate = LiveTradingSafetyGate(LiveTradingConfig(live_trading_enabled=False))
    result = gate.check(MockBrokerAdapter(), INCOMPLETE_CREDENTIALS, risk_approved=False)
    assert result.passed is False
    assert len(result.failed_checks) >= 4  # flag, liveness, credentials, risk approval


def test_risk_approval_check_can_be_disabled_via_config():
    gate = LiveTradingSafetyGate(LiveTradingConfig(live_trading_enabled=True, require_risk_approval=False))
    result = gate.check(FakeLiveAdapter(), COMPLETE_CREDENTIALS, risk_approved=False)
    assert result.passed is True
