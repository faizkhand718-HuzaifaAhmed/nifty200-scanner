"""
Error monitoring: a generic capture_exception()/capture_message() hook so
the rest of the app never needs to know which provider (if any) is
behind it. No-op by default - error monitoring is OPT-IN via SENTRY_DSN,
never silently sends anything anywhere unless explicitly configured.

sentry-sdk is an OPTIONAL dependency, imported lazily and only if
SENTRY_DSN is actually set - an environment without it installed (like
this project's dev sandbox) still runs correctly, just with monitoring
disabled, which is exactly what "no DSN configured" should mean anyway.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.core.config import Settings

logger = logging.getLogger(__name__)


class ErrorMonitor:
    def __init__(self, settings: Settings):
        self.enabled = bool(settings.sentry_dsn)
        self._sentry = None

        if self.enabled:
            try:
                import sentry_sdk  # optional dependency, imported only when actually needed

                sentry_sdk.init(
                    dsn=settings.sentry_dsn,
                    environment=settings.environment.value,
                    release=settings.app_version,
                    traces_sample_rate=settings.error_monitoring_sample_rate,
                )
                self._sentry = sentry_sdk
                logger.info("error monitoring enabled", extra={"provider": "sentry"})
            except ImportError:
                logger.warning(
                    "SENTRY_DSN is set but the sentry-sdk package is not installed - "
                    "error monitoring is disabled. Add sentry-sdk to requirements.txt."
                )
                self.enabled = False
        else:
            logger.info("error monitoring disabled (no SENTRY_DSN configured)")

    def capture_exception(self, exc: BaseException, context: Optional[Dict[str, Any]] = None) -> None:
        logger.error("unhandled exception", exc_info=exc, extra={"context": context or {}})
        if self.enabled and self._sentry is not None:
            with self._sentry.push_scope() as scope:
                for key, value in (context or {}).items():
                    scope.set_extra(key, value)
                self._sentry.capture_exception(exc)

    def capture_message(self, message: str, level: str = "info", context: Optional[Dict[str, Any]] = None) -> None:
        getattr(logger, level, logger.info)(message, extra={"context": context or {}})
        if self.enabled and self._sentry is not None:
            with self._sentry.push_scope() as scope:
                for key, value in (context or {}).items():
                    scope.set_extra(key, value)
                self._sentry.capture_message(message, level=level)
