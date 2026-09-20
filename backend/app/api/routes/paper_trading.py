"""
Paper trading routes - wrap app.paper_trading.risk_gated_engine's
RiskGatedPaperTradingEngine, NEVER app.paper_trading.engine.PaperTradingEngine
directly. This is deliberate, per the explicit instruction this was built
under: using the raw engine here would reopen the duplicate-position gap
documented as Critical Finding #1 in QA_AUDIT_REPORT.md.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException

from app.api import state
from app.api.converters import paper_position_to_schema, paper_summary_to_schema
from app.api.schemas import (
    ClosePositionRequest,
    OpenPositionRequest,
    OpenPositionResponse,
    PaperPositionOut,
    PaperTradingSummaryOut,
)
from app.paper_trading.metrics import compute_summary
from app.risk_management.models import ProposedTrade

router = APIRouter(prefix="/api/paper-trading", tags=["paper-trading"])


@router.get("/positions", response_model=List[PaperPositionOut])
def list_positions(status: str = "open"):
    engine = state.get_paper_trading_engine()
    if status == "open":
        positions = engine.paper_engine.get_open_positions()
    elif status == "closed":
        positions = engine.paper_engine.get_closed_positions()
    else:
        raise HTTPException(status_code=422, detail="status must be 'open' or 'closed'")
    return [paper_position_to_schema(p) for p in positions]


@router.get("/summary", response_model=PaperTradingSummaryOut)
def get_summary():
    engine = state.get_paper_trading_engine()
    open_positions = engine.paper_engine.get_open_positions()
    closed_positions = engine.paper_engine.get_closed_positions()
    summary = compute_summary(open_positions, closed_positions, as_of=datetime.now(timezone.utc).date())
    return paper_summary_to_schema(summary)


@router.post("/positions", response_model=OpenPositionResponse)
def open_position(request: OpenPositionRequest):
    engine = state.get_paper_trading_engine()
    proposed = ProposedTrade(
        symbol=request.symbol, direction=request.direction, entry_price=request.entry_price,
        stop_loss=request.stop_loss, target=request.target, market_data_timestamp=datetime.now(timezone.utc),
    )
    result = engine.try_open_position(
        proposed, now=datetime.now(timezone.utc),
        opportunity_score_at_entry=request.opportunity_score_at_entry,
        market_condition=request.market_condition, reason_for_entry=request.reason_for_entry,
    )
    return OpenPositionResponse(
        approved=result.opened,
        position=(paper_position_to_schema(result.position) if result.opened else None),
        rejection_reasons=result.decision.rejection_reasons,
        warnings=result.decision.warnings,
    )


@router.post("/positions/{position_id}/close", response_model=PaperPositionOut)
def close_position(position_id: str, request: ClosePositionRequest):
    engine = state.get_paper_trading_engine()
    existing = engine.paper_engine.get_position(position_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"no position with id {position_id!r}")
    if not existing.is_open:
        raise HTTPException(status_code=409, detail=f"position {position_id!r} is already closed")

    closed = engine.close_position(position_id, exit_time=datetime.now(timezone.utc), exit_price=request.exit_price)
    return paper_position_to_schema(closed)
