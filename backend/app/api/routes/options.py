"""
GET /api/options/{symbol} - wraps app.options_analysis.engine.OptionsAnalysisEngine
directly. The underlying LONG/SHORT signal comes from the exact same
analyze_symbol() helper routes/stocks.py uses (Phase 6/7's real scoring/
ranking output) - this route never decides direction itself, preserving
the "first determine the underlying signal, then pick a contract"
separation Phase 14 was built around.
"""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException

from app.api import state
from app.api.converters import options_result_to_schema
from app.api.schemas import OptionsAnalysisResponseOut
from app.api.services.stock_analysis import analyze_symbol
from app.options_analysis.engine import OptionsAnalysisEngine
from app.options_analysis.underlying_signal import UnderlyingSignal

router = APIRouter(prefix="/api/options", tags=["options"])


def _optional(value):
    return None if value is None or (isinstance(value, float) and pd.isna(value)) else float(value)


@router.get("/{symbol}", response_model=OptionsAnalysisResponseOut)
def get_options_analysis(symbol: str):
    ranked_row, _scoring_row = analyze_symbol(symbol)
    direction = ranked_row["direction"]

    signal = UnderlyingSignal(
        symbol=symbol,
        direction=direction,
        opportunity_score=float(ranked_row["opportunity_score"]),
        entry=_optional(ranked_row["entry_price"]) if direction != "NONE" else None,
        stop=_optional(ranked_row["stop_loss"]),
        target=_optional(ranked_row["target"]),
    )

    provider = state.get_market_data_provider()
    if not hasattr(provider, "get_option_chain"):
        raise HTTPException(status_code=503, detail="the configured market-data provider does not support option chains")

    try:
        chain = provider.get_option_chain(symbol)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"could not fetch option chain for {symbol}: {exc}")

    result = OptionsAnalysisEngine().analyze(signal, {chain.expiry: chain})
    return options_result_to_schema(result)
