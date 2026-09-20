"""
GET /api/universe - wraps app.universe.service.UniverseService directly.
No universe logic is reimplemented here.
"""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.api.converters import instrument_to_schema
from app.api.schemas import InstrumentOut

router = APIRouter(prefix="/api/universe", tags=["universe"])


@router.get("", response_model=List[InstrumentOut])
def get_universe(
    index_name: str = Query("NIFTY200"),
    as_of: Optional[date] = Query(None),
):
    """Requires DATABASE_URL to be configured - the universe is
    persistent, point-in-time data by design (Phase 2), unlike rankings,
    which can run without a database. Returns 503, not a crash, if the
    database isn't reachable."""
    from app.db.session import get_engine, get_sessionmaker
    from app.universe.service import UniverseService

    try:
        engine = get_engine()
        Session = get_sessionmaker(str(engine.url))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=f"database not configured: {exc}")

    try:
        with Session() as session:
            service = UniverseService(session)
            instruments = service.get_active_universe(index_name=index_name, as_of=as_of)
            return [instrument_to_schema(i) for i in instruments]
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}")
