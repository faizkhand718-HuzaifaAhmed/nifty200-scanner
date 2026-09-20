import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Environment, Settings  # noqa: E402
from app.core.startup_checks import (  # noqa: E402
    StartupConfigurationError,
    enforce_startup_checks,
    run_startup_checks,
)


def clean_prod_settings(**overrides):
    base = dict(
        environment=Environment.PRODUCTION, database_url="postgresql://x", log_format="json",
        force_https=True, cors_allowed_origins=["https://app.example.com"], secret_key="x" * 32,
    )
    base.update(overrides)
    return Settings(**base)


def test_clean_production_config_passes():
    result = run_startup_checks(clean_prod_settings())
    assert result.ok is True
    assert result.fatal_problems == []


def test_production_problems_are_fatal():
    settings = Settings(environment=Environment.PRODUCTION)
    result = run_startup_checks(settings)
    assert result.ok is False
    assert len(result.fatal_problems) > 0


def test_development_problems_are_only_warnings():
    settings = Settings(environment=Environment.DEVELOPMENT)
    result = run_startup_checks(settings)
    assert result.ok is True
    assert result.fatal_problems == []


def test_live_trading_without_broker_prefix_is_fatal_even_in_development():
    settings = Settings(environment=Environment.DEVELOPMENT, live_trading_enabled=True, broker_credentials_prefix=None)
    result = run_startup_checks(settings)
    assert result.ok is False
    assert any("LIVE_TRADING_ENABLED" in p for p in result.fatal_problems)


def test_live_trading_with_broker_prefix_configured_is_fine():
    settings = clean_prod_settings(live_trading_enabled=True, broker_credentials_prefix="ZERODHA")
    result = run_startup_checks(settings)
    assert result.ok is True


def test_enforce_startup_checks_raises_on_fatal_problems():
    settings = Settings(environment=Environment.PRODUCTION)
    with pytest.raises(StartupConfigurationError):
        enforce_startup_checks(settings)


def test_enforce_startup_checks_does_not_raise_when_clean():
    enforce_startup_checks(clean_prod_settings())


def test_default_settings_never_enable_live_trading():
    """The literal 'keep LIVE TRADING disabled by default' requirement,
    checked directly against Settings' own defaults with nothing set."""
    assert Settings().live_trading_enabled is False
