"""
GET /api/nse-scan - the NSE-MCP-compatible NIFTY 200 scanner. Informational
only: price, indicators, Technical Setup Score. No stop-loss, target, or
order logic - nothing here calls app.entry_engine, app.risk_management,
or app.brokers.

ERROR HANDLING, EXACTLY AS SPECIFIED: if the configured provider fails,
this endpoint does NOT fabricate data. It returns the LAST successfully
retrieved scan (if one exists), clearly marked is_stale=true with its
original timestamp and a stale_reason explaining what happened - or, if
there has never been a successful scan yet, a clear 502/503 error with no
`rows` at all. Never a silent substitution of synthetic data for real
data.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.api import state
from app.api.converters import daily_scan_row_to_schema
from app.api.schemas import DailyScanResponse
from app.api.services.daily_scan import build_nifty_daily_frame, compute_daily_scan_row
from app.core.config import Settings
from app.market_data.exceptions import MarketDataError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/nse-scan", tags=["nse-scan"])


@dataclass
class _LastGoodScan:
    response: DailyScanResponse
    fetched_at: datetime


_last_good_scan: Optional[_LastGoodScan] = None


def _reset_for_tests() -> None:
    global _last_good_scan
    _last_good_scan = None


def _run_scan(symbols: List[str]) -> DailyScanResponse:
    settings = Settings.from_env()
    provider = state.get_market_data_provider()

    nifty_frame = build_nifty_daily_frame(provider)
    rows = [compute_daily_scan_row(symbol, provider, nifty_frame=nifty_frame) for symbol in symbols]

    now = datetime.now(timezone.utc)
    data_source = settings.market_data_provider
    freshness = "historical" if data_source == "nse_mcp" else "mock"

    return DailyScanResponse(
        generated_at=now, data_source=data_source, data_freshness=freshness,
        data_timestamp=now.strftime("%Y-%m-%d %H:%M:%S"), is_stale=False, stale_reason=None,
        rows=[daily_scan_row_to_schema(r) for r in rows],
    )


@router.get("", response_model=DailyScanResponse)
def get_nse_scan(
    symbols: Optional[str] = Query(None, description="comma-separated symbols; omit to use the configured NIFTY 200 universe"),
):
    global _last_good_scan

    if symbols:
        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    else:
        from app.api.routes.rankings import _get_symbols

        symbol_list = _get_symbols()

    if not symbol_list:
        raise HTTPException(status_code=422, detail="no symbols to scan")

    try:
        response = _run_scan(symbol_list)
        _last_good_scan = _LastGoodScan(response=response, fetched_at=datetime.now(timezone.utc))
        return response
    except MarketDataError as exc:
        logger.error("NSE scan failed", extra={"error": str(exc)})
        if _last_good_scan is not None:
            stale_response = _last_good_scan.response.model_copy(deep=True)
            stale_response.is_stale = True
            stale_response.stale_reason = f"NSE MCP is currently unavailable ({exc}); showing the last successfully retrieved data."
            return stale_response
        raise HTTPException(
            status_code=502,
            detail=f"NSE MCP is currently unavailable and no previously retrieved data exists: {exc}",
        )
