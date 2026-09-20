"""
Broker exception hierarchy. Every adapter implementation raises these
rather than leaking a provider-SDK-specific exception, so calling code
can handle failures without knowing which broker is behind the interface.
"""
from __future__ import annotations


class BrokerError(Exception):
    """Base class for all broker errors."""


class AuthenticationError(BrokerError):
    pass


class OrderError(BrokerError):
    pass


class OrderNotFoundError(BrokerError):
    pass


class LiveTradingDisabledError(BrokerError):
    """Raised when any code path attempts to place a real order while
    live trading is not fully enabled - see safety.py."""
