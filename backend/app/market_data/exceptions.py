"""
Exception hierarchy for the market-data abstraction layer.

Every provider implementation (mock or real) is expected to raise these
rather than leaking provider-SDK-specific exceptions, so calling code can
handle failures without knowing which vendor is behind the interface.
"""
from __future__ import annotations

from typing import Optional


class MarketDataError(Exception):
    """Base class for all market-data errors."""


class ProviderAPIError(MarketDataError):
    """The upstream provider returned an error or an unexpected response."""


class ProviderRateLimitError(MarketDataError):
    """The upstream provider's rate limit was hit."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after_seconds: Optional[float] = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class InvalidTimeframeError(MarketDataError):
    """The requested timeframe is not supported by this provider/context."""


class SymbolNotFoundError(MarketDataError):
    """The requested symbol/exchange combination is not recognized."""


class DataValidationError(MarketDataError):
    """Candle or quote data failed validation (bad timestamp, tz, shape)."""
