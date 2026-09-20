"""
GET /api/rankings - wraps app.ranking.scanner.scan_universe() and
app.ranking.engine.RankingEngine.rank() directly. No scoring/ranking
logic is reimplemented here.

Runs the scan ON-DEMAND, synchronously, per request - there is no
scheduler yet (that's Step 3 of this rollout), so this is intentionally
simple for v1: correct, but not cached or automatically refreshed.

Works WITHOUT a database: the symbol universe comes from Phase 2's
UniverseService if DATABASE_URL is configured, falling back to the same
CSV file the universe CLI uses (config/universe/nifty200_sample.csv) if
not - preserving the "a database is not actually required for current
functionality" property the last audit called out.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.api import state
from app.api.converters import ranked_row_to_schema
from app.api.schemas import RankingsResponse
from app.market_data.enums import Timeframe
from app.ranking.engine import RankingEngine
from app.ranking.filters import RankingFilters, apply_filters, top_n as top_n_filter
from app.ranking.scanner import scan_universe

router = APIRouter(prefix="/api/rankings", tags=["rankings"])

_FALLBACK_UNIVERSE_FILE = Path(__file__).resolve().parents[3] / "config" / "universe" / "nifty200_sample.csv"


def _get_symbols() -> List[str]:
    try:
        from app.db.session import get_engine, get_sessionmaker
        from app.universe.service import UniverseService

        engine = get_engine()
        Session = get_sessionmaker(str(engine.url))
        with Session() as session:
            instruments = UniverseService(session).get_active_universe(index_name="NIFTY200")
            if instruments:
                return [i.symbol for i in instruments]
    except Exception:
        pass  # falls through to the CSV fallback below - never crashes the endpoint

    from app.universe.loader import load_records

    return [r.symbol for r in load_records(_FALLBACK_UNIVERSE_FILE)]


@router.get("", response_model=RankingsResponse)
def get_rankings(
    direction: Optional[str] = Query(None, pattern="^(LONG|SHORT)$"),
    min_score: Optional[float] = Query(None, ge=0, le=100),
    entry_status: Optional[str] = Query(None, pattern="^(READY|WATCH|NONE)$"),
    top: Optional[int] = Query(None, ge=1, le=200),
):
    symbols = _get_symbols()
    if not symbols:
        raise HTTPException(status_code=503, detail="no symbol universe available")

    scan_result = scan_universe(
        symbols=symbols, exchange="NSE", provider=state.get_market_data_provider(),
        calendar=state.get_calendar(), timeframe=Timeframe.FIFTEEN_MIN,
    )
    ranked_df = RankingEngine().rank(scan_result.snapshots)

    filters = RankingFilters(direction=direction, min_score=min_score, entry_status=entry_status)
    ranked_df = apply_filters(ranked_df, filters)
    if top is not None:
        ranked_df = top_n_filter(ranked_df, top)

    return RankingsResponse(
        generated_at=datetime.now(timezone.utc),
        skipped_symbols=scan_result.skipped,
        stocks=[ranked_row_to_schema(row) for _, row in ranked_df.iterrows()],
    )
