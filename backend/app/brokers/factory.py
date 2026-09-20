"""
Broker factory: the single place that decides which BrokerAdapter a
caller gets. PAPER IS THE DEFAULT - "paper trading must remain the
default mode" is enforced here, not just documented.

This module has NO knowledge of any specific real broker (Zerodha,
Upstox, or otherwise) - "do not hard-code any specific broker" holds even
at the factory level. A future real integration registers itself via
register_live_broker() from its OWN module; this file never imports it.
Because nothing is registered yet, selecting LIVE mode always fails
loudly, even with every flag enabled - there is currently no real broker
for this system to trade through, and that is the correct, safe state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, Optional

from app.brokers.base import BrokerAdapter
from app.brokers.mock_adapter import MockBrokerAdapter
from app.brokers.paper_adapter import PaperBrokerAdapter
from app.brokers.safety import LiveTradingConfig
from app.paper_trading.engine import PaperTradingEngine


class BrokerMode(str, Enum):
    MOCK = "mock"
    PAPER = "paper"
    LIVE = "live"


@dataclass
class BrokerFactoryConfig:
    mode: BrokerMode = BrokerMode.PAPER  # PAPER IS THE DEFAULT
    live_trading_config: LiveTradingConfig = field(default_factory=LiveTradingConfig)


_LIVE_ADAPTER_FACTORIES: Dict[str, Callable[[], BrokerAdapter]] = {}


def register_live_broker(name: str, factory_fn: Callable[[], BrokerAdapter]) -> None:
    """A future real-broker integration calls this from its OWN module to
    make itself selectable - this factory never imports any real broker's
    module itself, keeping it broker-agnostic."""
    _LIVE_ADAPTER_FACTORIES[name] = factory_fn


def registered_live_brokers() -> list:
    return sorted(_LIVE_ADAPTER_FACTORIES.keys())


def create_broker_adapter(
    config: BrokerFactoryConfig,
    live_broker_name: Optional[str] = None,
    paper_engine: Optional[PaperTradingEngine] = None,
) -> BrokerAdapter:
    if config.mode == BrokerMode.MOCK:
        return MockBrokerAdapter()

    if config.mode == BrokerMode.PAPER:
        return PaperBrokerAdapter(engine=paper_engine)

    if config.mode == BrokerMode.LIVE:
        if not config.live_trading_config.live_trading_enabled:
            raise RuntimeError(
                "Cannot create a live broker adapter: live_trading_enabled is False. "
                "Paper trading remains the default and safe mode."
            )
        if not _LIVE_ADAPTER_FACTORIES:
            raise NotImplementedError(
                "No real broker adapter is registered (by design - this system does not "
                "hard-code any specific broker). Implement a BrokerAdapter subclass for your "
                "broker in its own module and call register_live_broker() before selecting LIVE mode."
            )
        if live_broker_name is None:
            raise ValueError(
                f"multiple/ambiguous live broker selection: specify live_broker_name "
                f"(registered: {registered_live_brokers()})"
            )
        factory_fn = _LIVE_ADAPTER_FACTORIES.get(live_broker_name)
        if factory_fn is None:
            raise ValueError(f"no live broker registered under {live_broker_name!r} (registered: {registered_live_brokers()})")
        adapter = factory_fn()
        if not adapter.is_live:
            raise RuntimeError(
                f"the adapter registered under {live_broker_name!r} reports is_live=False - "
                f"refusing to use it for LIVE mode"
            )
        return adapter

    raise ValueError(f"unknown broker mode: {config.mode}")
