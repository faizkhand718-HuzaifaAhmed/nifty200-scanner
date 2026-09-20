"""
Application entrypoint. THIS FILE COULD NOT BE EXECUTED IN THE SANDBOX
THIS WAS BUILT IN - fastapi/uvicorn are not installable there (no network
access). It was syntax-checked (`python -m py_compile`) and carefully
reviewed, but not run. Run it for real yourself before deploying:
    uvicorn app.main:app --host 0.0.0.0 --port 8000

SCOPE: production infrastructure (health checks, readiness, metrics, a
monitored WebSocket endpoint, logging, error capture, rate limiting,
security headers, CORS, startup safety checks) PLUS the business API -
universe, rankings, stock detail, backtest, paper trading (via
RiskGatedPaperTradingEngine), alerts, and options analysis - each wired
in from app/api/routes/. Every route is a thin wrapper; no
trading/scoring/risk logic lives in this file. There is still no
authentication on these routes yet, and no scheduler automatically
running the ranking pipeline - both remain explicitly out of scope for
this step (see the status report this was delivered alongside).
"""
from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import alerts, backtest, nse_scan, options, paper_trading, rankings, stocks, universe
from app.core.config import Settings
from app.core.error_monitoring import ErrorMonitor
from app.core.health import check_database, liveness_check, readiness_check
from app.core.logging_config import configure_logging, new_correlation_id, set_correlation_id
from app.core.rate_limiter import InMemorySlidingWindowRateLimiter
from app.core.security import build_cors_origins, build_security_headers
from app.core.startup_checks import StartupConfigurationError, enforce_startup_checks
from app.websocket.connection_manager import WebSocketConnectionManager

settings = Settings.from_env()
configure_logging(settings)
logger = logging.getLogger("app")

error_monitor = ErrorMonitor(settings)
rate_limiter = InMemorySlidingWindowRateLimiter(
    requests_per_minute=settings.rate_limit_requests_per_minute, burst=settings.rate_limit_burst
)
ws_manager = WebSocketConnectionManager()

app = FastAPI(title="NIFTY 200 Opportunity Scanner", version=settings.app_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=build_cors_origins(settings),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Business API routes - each router only wraps existing, already-tested
# engines (Phases 2-17); see app/api/routes/*.py's own module docstrings
# for exactly which engine each one wraps. No trading/scoring/risk logic
# lives in this file or in app/api/ at all.
app.include_router(universe.router)
app.include_router(rankings.router)
app.include_router(stocks.router)
app.include_router(backtest.router)
app.include_router(paper_trading.router)
app.include_router(alerts.router)
app.include_router(options.router)
app.include_router(nse_scan.router)


@app.on_event("startup")
def on_startup() -> None:
    """Refuses to finish starting up if the configuration is dangerously
    inconsistent - see app.core.startup_checks. This is the deploy-time
    reinforcement of 'keep LIVE TRADING disabled by default'."""
    try:
        enforce_startup_checks(settings)
    except StartupConfigurationError:
        logger.critical("startup aborted due to fatal configuration problems")
        raise
    logger.info(
        "application started",
        extra={"environment": settings.environment.value, "version": settings.app_version, "live_trading_enabled": settings.live_trading_enabled},
    )


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    """One middleware doing three things together, in order: correlation
    ID assignment (for tracing a request across logs), rate limiting
    (protecting this app's own API), and security headers (applied to
    every response, including error responses)."""
    correlation_id = request.headers.get("X-Correlation-ID") or new_correlation_id()
    set_correlation_id(correlation_id)

    client_key = request.client.host if request.client else "unknown"
    result = rate_limiter.check(client_key, now=time.time())
    if not result.allowed:
        response = JSONResponse(
            status_code=429,
            content={"error": "rate limit exceeded", "retry_after_seconds": result.retry_after_seconds},
        )
        response.headers["Retry-After"] = str(int(result.retry_after_seconds) + 1)
        return response

    start = time.monotonic()
    try:
        response = await call_next(request)
    except Exception as exc:
        error_monitor.capture_exception(exc, context={"path": request.url.path, "method": request.method})
        raise
    duration_ms = (time.monotonic() - start) * 1000

    for key, value in build_security_headers(settings).items():
        response.headers[key] = value
    response.headers["X-Correlation-ID"] = correlation_id

    logger.info(
        "request completed",
        extra={
            "method": request.method, "path": request.url.path, "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2), "client": client_key,
        },
    )
    return response


@app.get("/health")
def health():
    """Liveness - see app.core.health's module docstring for why this
    never touches the database."""
    return liveness_check(settings.app_version)


@app.get("/health/ready")
def health_ready():
    """Readiness - checks the database. A future real deployment would
    plug in its actual session factory here; this wires the health-check
    LOGIC (already tested) to a real dependency."""
    from app.db.session import get_engine

    def ping():
        engine = get_engine(settings.database_url)
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")

    db_status = check_database(ping, timeout_seconds=settings.health_check_timeout_seconds)
    report = readiness_check([db_status])
    status_code = 200 if report.healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "healthy": report.healthy,
            "components": [
                {"name": c.name, "state": c.state.value, "latency_ms": c.latency_ms, "detail": c.detail}
                for c in report.components
            ],
        },
    )


@app.get("/metrics")
def metrics():
    """A minimal, dependency-free metrics surface - active WebSocket
    connections, live-trading flag state, environment. A real production
    deployment would likely replace/extend this with a proper
    Prometheus /metrics endpoint (via prometheus-fastapi-instrumentator
    or similar); this is the honest minimum this phase actually built and
    verified."""
    return {
        "environment": settings.environment.value,
        "version": settings.app_version,
        "live_trading_enabled": settings.live_trading_enabled,
        "websocket_active_connections": ws_manager.active_connection_count(),
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """A monitored WebSocket connection - tracks connect/disconnect and
    heartbeats via WebSocketConnectionManager (fully tested independent
    of FastAPI - see tests/test_websocket_connection_manager.py). Does
    NOT push any real trading data yet - broadcasting actual
    ranking/alert updates over this channel is future work, same
    boundary as the rest of this file (see the module docstring)."""
    await websocket.accept()
    connection_id = uuid.uuid4().hex
    ws_manager.connect(connection_id, now=time.time())
    logger.info("websocket connected", extra={"connection_id": connection_id})

    try:
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "heartbeat":
                ws_manager.record_heartbeat(connection_id, now=time.time())
            elif message.get("type") == "subscribe" and "channel" in message:
                ws_manager.subscribe(connection_id, message["channel"])
    except WebSocketDisconnect:
        logger.info("websocket disconnected", extra={"connection_id": connection_id})
    finally:
        ws_manager.disconnect(connection_id)
