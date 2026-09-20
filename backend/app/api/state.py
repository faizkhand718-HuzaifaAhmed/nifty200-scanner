"""
Process-global singleton state for the API layer - a V1 SIMPLIFICATION,
flagged explicitly so it isn't mistaken for a permanent design.

There is no per-user authentication yet (Step 5 of this rollout comes
later), so this holds ONE shared instance of each stateful engine for the
whole process, as if there were a single account. Once auth exists, this
should become per-user state (keyed by user ID), not a global singleton -
noted here so that migration is planned for, not a surprise.

Nothing here recomputes or reimplements engine logic - it only
constructs and holds instances of the SAME classes already built and
tested in Phases 2-17.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from app.alerts.history import AlertHistory
from app.core.config import Settings
from app.market_data.base import IntradayOHLCVProvider
from app.market_data.caching_provider import CachingProvider
from app.market_data.calendar import NSECalendar
from app.market_data.providers.mock_provider import MockDataProvider
from app.paper_trading.risk_gated_engine import RiskGatedPaperTradingEngine
from app.risk_management.config import RiskConfig
from app.risk_management.engine import RiskManager

_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"

_calendar: Optional[NSECalendar] = None
_market_data_provider: Optional[IntradayOHLCVProvider] = None
_risk_manager: Optional[RiskManager] = None
_paper_trading_engine: Optional[RiskGatedPaperTradingEngine] = None
_alert_history: Optional[AlertHistory] = None


def get_calendar() -> NSECalendar:
    global _calendar
    if _calendar is None:
        holiday_file = _CONFIG_DIR / "market_calendar" / "nse_holidays_2026.json"
        try:
            _calendar = NSECalendar.from_file(holiday_file)
        except FileNotFoundError:
            _calendar = NSECalendar()
    return _calendar


def get_market_data_provider() -> IntradayOHLCVProvider:
    """Returns the CURRENTLY CONFIGURED data provider, selected via
    Settings.market_data_provider (env var MARKET_DATA_PROVIDER):
      - "mock" (default): MockDataProvider - safe for dev/tests, never
        used for anything presented as real data.
      - "nse_mcp": the official NSE MCP services, wrapped in a TTL cache.
        See app/market_data/providers/nse_mcp_provider.py's module
        docstring for exactly what this does and does not support.
    There is NO automatic fallback from nse_mcp to mock on failure - a
    live-data failure must surface as a clear error to the caller, never
    silently substitute synthetic data. See app/api/routes/rankings.py
    for how failures are surfaced and the last-known-good cache is used."""
    global _market_data_provider
    if _market_data_provider is None:
        settings = Settings.from_env()
        if settings.market_data_provider == "nse_mcp":
            from app.market_data.providers.nse_mcp_provider import NSEMCPProvider

            inner = NSEMCPProvider(
                bhavcopy_url=settings.nse_mcp_bhavcopy_url,
                cmmkt_url=settings.nse_mcp_cmmkt_url,
                auth_token=settings.nse_mcp_auth_token,
            )
            _market_data_provider = CachingProvider(
                inner,
                live_ttl_seconds=settings.nse_mcp_live_cache_ttl_seconds,
                historical_ttl_seconds=settings.nse_mcp_historical_cache_ttl_seconds,
            )
        else:
            _market_data_provider = MockDataProvider(get_calendar())
    return _market_data_provider


def get_risk_manager() -> RiskManager:
    global _risk_manager
    if _risk_manager is None:
        # TODO(auth): account_capital should come from a real per-user
        # account once Step 5 (auth) exists - hardcoded here as the v1
        # single-account placeholder, not a real balance.
        config = RiskConfig(account_capital=100000.0)
        _risk_manager = RiskManager(config, today=date.today())
    return _risk_manager


def get_paper_trading_engine() -> RiskGatedPaperTradingEngine:
    """The RISK-GATED engine, deliberately - never expose a raw
    PaperTradingEngine through the API, or the duplicate-position gap
    documented in QA_AUDIT_REPORT.md's Critical Finding #1 comes back."""
    global _paper_trading_engine
    if _paper_trading_engine is None:
        _paper_trading_engine = RiskGatedPaperTradingEngine(get_risk_manager())
    return _paper_trading_engine


def get_alert_history() -> AlertHistory:
    global _alert_history
    if _alert_history is None:
        _alert_history = AlertHistory()
    return _alert_history


def reset_state_for_tests() -> None:
    """Test-only: clears every singleton so each test starts from a clean
    process state, rather than leaking state between tests."""
    global _calendar, _market_data_provider, _risk_manager, _paper_trading_engine, _alert_history
    _calendar = None
    _market_data_provider = None
    _risk_manager = None
    _paper_trading_engine = None
    _alert_history = None
