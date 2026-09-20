"""
GET /api/stocks/{symbol} - thin wrapper around
app.api.services.stock_analysis.analyze_symbol(), which itself only
sequences existing Phase 4-7 engine calls for one symbol.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.converters import ranked_row_to_schema, score_breakdown_to_schema
from app.api.schemas import StockDetailResponse
from app.api.services.stock_analysis import analyze_symbol

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("/{symbol}", response_model=StockDetailResponse)
def get_stock_detail(symbol: str):
    ranked_row, scoring_row = analyze_symbol(symbol)
    leading_side = "long" if float(scoring_row["long_score"]) >= float(scoring_row["short_score"]) else "short"

    return StockDetailResponse(
        stock=ranked_row_to_schema(ranked_row),
        breakdown=score_breakdown_to_schema(scoring_row, leading_side),
    )
