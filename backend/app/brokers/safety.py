"""
LiveTradingSafetyGate: the explicit flag PLUS multiple independent safety
checks required before any real order can be placed. Every check is
independent and all must pass - there is no single boolean that, if
true, bypasses the rest.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from app.brokers.base import BrokerAdapter
from app.brokers.models import BrokerCredentials


@dataclass
class LiveTradingConfig:
    # THE explicit flag. Defaults to False - live trading is disabled
    # unless someone deliberately turns this on.
    live_trading_enabled: bool = False
    require_credentials_present: bool = True
    require_risk_approval: bool = True
    # An optional extra circuit breaker independent of risk_management's
    # own position-sizing limits (Phase 16) - a last-resort cap here.
    max_live_order_value: Optional[float] = None


@dataclass
class SafetyCheckResult:
    passed: bool
    failed_checks: List[str] = field(default_factory=list)


class LiveTradingSafetyGate:
    def __init__(self, config: LiveTradingConfig):
        self.config = config

    def check(
        self,
        adapter: BrokerAdapter,
        credentials: BrokerCredentials,
        risk_approved: bool = False,
        order_value: Optional[float] = None,
    ) -> SafetyCheckResult:
        cfg = self.config
        failed: List[str] = []

        if not cfg.live_trading_enabled:
            failed.append("LIVE_TRADING_ENABLED flag is not set - live trading is disabled by default")

        if not adapter.is_live:
            failed.append(f"the configured broker adapter ({type(adapter).__name__}) is not a live adapter")

        if cfg.require_credentials_present and not credentials.is_complete():
            failed.append("broker credentials are missing or incomplete")

        if cfg.require_risk_approval and not risk_approved:
            failed.append("risk management has not approved this trade")

        if cfg.max_live_order_value is not None and order_value is not None and order_value > cfg.max_live_order_value:
            failed.append(
                f"order value {order_value:.2f} exceeds the configured max_live_order_value "
                f"{cfg.max_live_order_value:.2f}"
            )

        return SafetyCheckResult(passed=len(failed) == 0, failed_checks=failed)
