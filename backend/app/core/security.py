"""
Security configuration: CORS policy and HTTP security headers, built as
pure functions of Settings so they're directly testable without needing
a running server.
"""
from __future__ import annotations

from typing import Dict, List

from app.core.config import Settings


def build_cors_origins(settings: Settings) -> List[str]:
    """Never returns a wildcard in production - see
    Settings.validate_for_environment(), which flags '*' as a startup
    problem. This function just returns what's configured; the refusal
    to boot with a wildcard happens in startup_checks.py."""
    return list(settings.cors_allowed_origins)


def build_security_headers(settings: Settings) -> Dict[str, str]:
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    }
    if settings.force_https:
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return headers
