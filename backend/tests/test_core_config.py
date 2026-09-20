import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Environment, Settings  # noqa: E402

ENV_KEYS = [
    "ENVIRONMENT", "APP_VERSION", "DATABASE_URL", "REDIS_URL", "LOG_LEVEL",
    "LOG_FORMAT", "SENTRY_DSN", "CORS_ALLOWED_ORIGINS", "FORCE_HTTPS",
    "SECRET_KEY", "LIVE_TRADING_ENABLED", "BROKER_CREDENTIALS_PREFIX",
]


def _clean_env(fn):
    def wrapper():
        saved = {k: os.environ.get(k) for k in ENV_KEYS}
        for k in ENV_KEYS:
            os.environ.pop(k, None)
        try:
            fn()
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
    wrapper.__name__ = fn.__name__
    return wrapper


@_clean_env
def test_defaults_are_safe_when_nothing_is_set():
    settings = Settings.from_env()
    assert settings.environment == Environment.DEVELOPMENT
    assert settings.live_trading_enabled is False
    assert settings.database_url is None
    assert settings.secret_key is None


@_clean_env
def test_from_env_reads_every_variable():
    os.environ["ENVIRONMENT"] = "production"
    os.environ["APP_VERSION"] = "1.2.3"
    os.environ["DATABASE_URL"] = "postgresql://x"
    os.environ["LOG_LEVEL"] = "warning"
    os.environ["CORS_ALLOWED_ORIGINS"] = "https://a.com, https://b.com"
    os.environ["LIVE_TRADING_ENABLED"] = "true"

    settings = Settings.from_env()
    assert settings.environment == Environment.PRODUCTION
    assert settings.app_version == "1.2.3"
    assert settings.database_url == "postgresql://x"
    assert settings.log_level == "WARNING"
    assert settings.cors_allowed_origins == ["https://a.com", "https://b.com"]
    assert settings.live_trading_enabled is True


@_clean_env
def test_invalid_environment_raises():
    os.environ["ENVIRONMENT"] = "not-a-real-environment"
    with pytest.raises(ValueError):
        Settings.from_env()


@_clean_env
def test_bool_parsing_variants():
    for value in ("1", "true", "True", "yes", "on"):
        os.environ["LIVE_TRADING_ENABLED"] = value
        assert Settings.from_env().live_trading_enabled is True
    for value in ("0", "false", "no", "off", ""):
        os.environ["LIVE_TRADING_ENABLED"] = value
        assert Settings.from_env().live_trading_enabled is False


def test_validate_for_environment_clean_production_config():
    settings = Settings(
        environment=Environment.PRODUCTION, database_url="postgresql://x", log_format="json",
        force_https=True, cors_allowed_origins=["https://app.example.com"], secret_key="x" * 32,
    )
    assert settings.validate_for_environment() == []


def test_validate_for_environment_flags_missing_database_url():
    settings = Settings(environment=Environment.PRODUCTION, secret_key="x" * 32, cors_allowed_origins=["https://a.com"])
    problems = settings.validate_for_environment()
    assert any("DATABASE_URL" in p for p in problems)


def test_validate_for_environment_flags_wildcard_cors():
    settings = Settings(
        environment=Environment.PRODUCTION, database_url="x", secret_key="x" * 32, cors_allowed_origins=["*"],
    )
    problems = settings.validate_for_environment()
    assert any("wildcard" in p for p in problems)


def test_validate_for_environment_flags_short_secret_key():
    settings = Settings(
        environment=Environment.PRODUCTION, database_url="x", cors_allowed_origins=["https://a.com"], secret_key="short",
    )
    problems = settings.validate_for_environment()
    assert any("SECRET_KEY" in p for p in problems)


def test_validate_for_environment_is_lenient_in_development():
    settings = Settings(environment=Environment.DEVELOPMENT)
    assert settings.validate_for_environment() == []


def test_live_trading_without_broker_prefix_flagged_in_any_environment():
    settings = Settings(environment=Environment.DEVELOPMENT, live_trading_enabled=True, broker_credentials_prefix=None)
    problems = settings.validate_for_environment()
    assert any("BROKER_CREDENTIALS_PREFIX" in p for p in problems)
