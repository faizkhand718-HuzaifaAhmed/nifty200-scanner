"""
Structured logging setup. Pure stdlib `logging` - no structlog dependency
(same reasoning as config.py: keeps this executable/testable without
network access to install anything extra).

CRITICAL: never logs secrets. `_REDACT_KEYS` is a defense-in-depth
safeguard - if a caller accidentally passes a credential-shaped field
into `extra`, the formatter redacts it rather than writing it to logs
verbatim. This does not replace the discipline of not passing secrets to
logging in the first place; it's a second line of defense.
"""
from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any, Dict, Optional

from app.core.config import Settings

_REDACT_KEYS = {
    "api_key", "api_secret", "access_token", "password", "secret",
    "secret_key", "authorization", "token", "database_url",
}
_REDACTED_VALUE = "[REDACTED]"

_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def new_correlation_id() -> str:
    return uuid.uuid4().hex[:16]


def set_correlation_id(correlation_id: str) -> None:
    _correlation_id.set(correlation_id)


def get_correlation_id() -> Optional[str]:
    return _correlation_id.get()


def _redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: (_REDACTED_VALUE if k.lower() in _REDACT_KEYS else _redact(v))
            for k, v in obj.items()
        }
    return obj


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        correlation_id = get_correlation_id()
        if correlation_id:
            payload["correlation_id"] = correlation_id

        standard_attrs = set(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime"}
        extras = {k: v for k, v in vars(record).items() if k not in standard_attrs}
        if extras:
            payload["extra"] = _redact(extras)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


class TextFormatter(logging.Formatter):
    def __init__(self):
        super().__init__("%(asctime)s %(levelname)-8s %(name)s: %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        correlation_id = get_correlation_id()
        return f"[{correlation_id}] {base}" if correlation_id else base


def configure_logging(settings: Settings) -> None:
    root = logging.getLogger()
    root.setLevel(settings.log_level)
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter() if settings.log_format == "json" else TextFormatter())
    root.addHandler(handler)
