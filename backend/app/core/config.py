"""
Application settings, loaded ONLY from environment variables. This is the
single place production configuration is assembled - no default here is
a real secret, and nothing in this file (or anywhere else in the
codebase) contains a hardcoded API key, broker credential, or database
password. See .env.example for every variable this reads, documented,
with placeholder (never real) values.

Deliberately plain stdlib (dataclass + os.environ), not pydantic-settings
- pydantic-settings isn't installable in this project's dev sandbox
  (no network access), so building this on plain stdlib means it can
  actually be executed and tested here, not just syntax-checked.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


def _get_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _get_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw is not None else default


def _get_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw is not None else default


def _get_list(name: str, default: Optional[List[str]] = None) -> List[str]:
    raw = os.environ.get(name)
    if raw is None:
        return default or []
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass
class Settings:
    # --- Environment identity ---
    environment: Environment = Environment.DEVELOPMENT
    app_version: str = "0.0.0-dev"

    # --- Database (Phase 2's db layer reads DATABASE_URL directly too;
    # this mirrors it so the rest of the app has one place to look) ---
    database_url: Optional[str] = None
    database_pool_size: int = 5
    database_pool_max_overflow: int = 10
    database_pool_timeout_seconds: int = 30
    database_statement_timeout_ms: int = 30000  # kills runaway queries in prod

    # --- Redis (rate limiting / caching at multi-instance scale; the
    # in-memory rate limiter in this codebase is the single-instance
    # fallback - see rate_limiter.py's module docstring) ---
    redis_url: Optional[str] = None

    # --- Logging ---
    log_level: str = "INFO"
    log_format: str = "json"  # "json" in prod, "text" is fine for local dev

    # --- Error monitoring (Sentry or compatible; optional, no-op if unset) ---
    sentry_dsn: Optional[str] = None
    error_monitoring_sample_rate: float = 1.0

    # --- CORS / security ---
    cors_allowed_origins: List[str] = field(default_factory=list)
    force_https: bool = True
    secret_key: Optional[str] = None  # for any future session/JWT signing

    # --- Rate limiting (protects THIS app's own API, distinct from
    # Phase 3's provider-side outbound rate limiting) ---
    rate_limit_requests_per_minute: int = 120
    rate_limit_burst: int = 20

    # --- Live trading (mirrors app.brokers.safety.LiveTradingConfig's
    # flag at the application-config level, so app startup can refuse to
    # boot in a dangerously inconsistent state - see startup_checks.py) ---
    live_trading_enabled: bool = False
    broker_credentials_prefix: Optional[str] = None  # e.g. "ZERODHA" -> reads ZERODHA_API_KEY etc.

    # --- Health check dependencies ---
    health_check_timeout_seconds: float = 5.0

    # --- Market data provider selection ---
    # "mock" (default, safe for dev/tests) or "nse_mcp" (the official NSE
    # MCP services - see app/market_data/providers/nse_mcp_provider.py).
    # Never silently falls back from nse_mcp to mock on failure - see
    # that module's docstring for why (NSE MCP failures must surface as
    # clear errors, not silently swap in synthetic data).
    market_data_provider: str = "mock"
    nse_mcp_bhavcopy_url: str = "https://mcp.nseindia.in/bhavcopy/cm/mcp"
    nse_mcp_cmmkt_url: str = "https://mcp.nseindia.in/cmmkt/mcp"
    # NSE's documented client config shows no auth requirement - this
    # exists defensively in case that changes; never set from anything
    # but an environment variable.
    nse_mcp_auth_token: Optional[str] = None
    # Cache TTLs - see caching_provider.py's module docstring for why
    # these specific defaults were chosen (NSE publishes no numeric rate
    # limit, so these track the data source's own actual refresh cadence).
    nse_mcp_live_cache_ttl_seconds: float = 60.0
    nse_mcp_historical_cache_ttl_seconds: float = 6 * 3600.0

    @classmethod
    def from_env(cls) -> "Settings":
        env_raw = os.environ.get("ENVIRONMENT", "development").strip().lower()
        try:
            environment = Environment(env_raw)
        except ValueError:
            raise ValueError(
                f"invalid ENVIRONMENT={env_raw!r}; must be one of "
                f"{[e.value for e in Environment]}"
            )

        return cls(
            environment=environment,
            app_version=os.environ.get("APP_VERSION", "0.0.0-dev"),
            database_url=os.environ.get("DATABASE_URL"),
            database_pool_size=_get_int("DATABASE_POOL_SIZE", 5),
            database_pool_max_overflow=_get_int("DATABASE_POOL_MAX_OVERFLOW", 10),
            database_pool_timeout_seconds=_get_int("DATABASE_POOL_TIMEOUT_SECONDS", 30),
            database_statement_timeout_ms=_get_int("DATABASE_STATEMENT_TIMEOUT_MS", 30000),
            redis_url=os.environ.get("REDIS_URL"),
            log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
            log_format=os.environ.get("LOG_FORMAT", "json").lower(),
            sentry_dsn=os.environ.get("SENTRY_DSN"),
            error_monitoring_sample_rate=_get_float("ERROR_MONITORING_SAMPLE_RATE", 1.0),
            cors_allowed_origins=_get_list("CORS_ALLOWED_ORIGINS", []),
            force_https=_get_bool("FORCE_HTTPS", True),
            secret_key=os.environ.get("SECRET_KEY"),
            rate_limit_requests_per_minute=_get_int("RATE_LIMIT_REQUESTS_PER_MINUTE", 120),
            rate_limit_burst=_get_int("RATE_LIMIT_BURST", 20),
            live_trading_enabled=_get_bool("LIVE_TRADING_ENABLED", False),
            broker_credentials_prefix=os.environ.get("BROKER_CREDENTIALS_PREFIX"),
            health_check_timeout_seconds=_get_float("HEALTH_CHECK_TIMEOUT_SECONDS", 5.0),
            market_data_provider=os.environ.get("MARKET_DATA_PROVIDER", "mock").strip().lower(),
            nse_mcp_bhavcopy_url=os.environ.get("NSE_MCP_BHAVCOPY_URL", "https://mcp.nseindia.in/bhavcopy/cm/mcp"),
            nse_mcp_cmmkt_url=os.environ.get("NSE_MCP_CMMKT_URL", "https://mcp.nseindia.in/cmmkt/mcp"),
            nse_mcp_auth_token=os.environ.get("NSE_MCP_AUTH_TOKEN"),
            nse_mcp_live_cache_ttl_seconds=_get_float("NSE_MCP_LIVE_CACHE_TTL_SECONDS", 60.0),
            nse_mcp_historical_cache_ttl_seconds=_get_float("NSE_MCP_HISTORICAL_CACHE_TTL_SECONDS", 6 * 3600.0),
        )

    def validate_for_environment(self) -> List[str]:
        """Returns a list of problems (empty = fine). Deliberately
        returns issues rather than raising, so callers (startup_checks.py,
        tests) decide what to do with them - a health-check endpoint might
        want to report these without crashing, while app startup wants to
        refuse to boot on certain ones."""
        problems: List[str] = []

        if self.environment == Environment.PRODUCTION:
            if not self.database_url:
                problems.append("DATABASE_URL is not set")
            if self.log_format != "json":
                problems.append("LOG_FORMAT should be 'json' in production for log aggregation")
            if not self.force_https:
                problems.append("FORCE_HTTPS is disabled in production")
            if not self.cors_allowed_origins:
                problems.append("CORS_ALLOWED_ORIGINS is empty - no origin will be allowed")
            if "*" in self.cors_allowed_origins:
                problems.append("CORS_ALLOWED_ORIGINS contains '*' - wildcard CORS is not safe in production")
            if not self.secret_key:
                problems.append("SECRET_KEY is not set")
            elif len(self.secret_key) < 32:
                problems.append("SECRET_KEY is shorter than 32 characters")

        if self.live_trading_enabled and not self.broker_credentials_prefix:
            problems.append("LIVE_TRADING_ENABLED is true but BROKER_CREDENTIALS_PREFIX is not set")

        if self.market_data_provider not in ("mock", "nse_mcp"):
            problems.append(f"MARKET_DATA_PROVIDER={self.market_data_provider!r} is not a known provider ('mock' or 'nse_mcp')")

        return problems
