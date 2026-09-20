import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings  # noqa: E402
from app.core.security import build_cors_origins, build_security_headers  # noqa: E402


def test_build_cors_origins_returns_configured_list():
    settings = Settings(cors_allowed_origins=["https://a.com", "https://b.com"])
    assert build_cors_origins(settings) == ["https://a.com", "https://b.com"]


def test_build_security_headers_includes_baseline_headers():
    settings = Settings(force_https=False)
    headers = build_security_headers(settings)
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert "Strict-Transport-Security" not in headers


def test_build_security_headers_includes_hsts_when_https_forced():
    settings = Settings(force_https=True)
    headers = build_security_headers(settings)
    assert "max-age=31536000" in headers["Strict-Transport-Security"]
    assert "includeSubDomains" in headers["Strict-Transport-Security"]
