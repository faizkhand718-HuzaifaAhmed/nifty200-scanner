"""
Startup safety checks: run once, at process boot, before the app starts
accepting traffic. This is the application-level reinforcement of "keep
LIVE TRADING disabled by default" - Phase 16's RiskManager and Phase 17's
LiveTradingSafetyGate both check safety at TRADE time, which is correct
but not sufficient on its own: a misconfigured deployment could run for
hours before anyone attempts a trade and discovers the problem. This
module catches the same class of misconfiguration at DEPLOY time instead
- fail loudly on startup, not silently on the first live order attempt.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

from app.core.config import Environment, Settings

logger = logging.getLogger(__name__)


class StartupConfigurationError(RuntimeError):
    """Raised to deliberately prevent the app from starting."""


@dataclass
class StartupCheckResult:
    ok: bool
    warnings: List[str]
    fatal_problems: List[str]


def run_startup_checks(settings: Settings) -> StartupCheckResult:
    warnings: List[str] = []
    fatal: List[str] = []

    problems = settings.validate_for_environment()
    if settings.environment == Environment.PRODUCTION:
        fatal.extend(problems)
    else:
        warnings.extend(problems)

    if settings.live_trading_enabled and not settings.broker_credentials_prefix:
        fatal.append(
            "LIVE_TRADING_ENABLED=true but BROKER_CREDENTIALS_PREFIX is not set - "
            "refusing to start. This is not a place to fail open."
        )

    if settings.live_trading_enabled:
        logger.warning(
            "LIVE TRADING IS ENABLED for this deployment. Real orders can be placed "
            "if all of Phase 16/17's additional safety checks also pass at trade time.",
            extra={"live_trading_enabled": True, "environment": settings.environment.value},
        )
    else:
        logger.info("Live trading is disabled (default, safe state).", extra={"live_trading_enabled": False})

    for warning in warnings:
        logger.warning("startup configuration warning", extra={"problem": warning})

    return StartupCheckResult(ok=not fatal, warnings=warnings, fatal_problems=fatal)


def enforce_startup_checks(settings: Settings) -> None:
    """Call this at process boot. Raises StartupConfigurationError (and
    the caller should let the process exit non-zero) if any fatal problem
    was found."""
    result = run_startup_checks(settings)
    if not result.ok:
        for problem in result.fatal_problems:
            logger.critical("FATAL startup configuration problem", extra={"problem": problem})
        raise StartupConfigurationError(
            f"{len(result.fatal_problems)} fatal configuration problem(s) found - refusing to start: "
            f"{result.fatal_problems}"
        )
