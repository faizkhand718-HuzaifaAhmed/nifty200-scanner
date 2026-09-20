"""
GET /api/alerts - wraps app.alerts.history.AlertHistory.list() directly.

There is no automatic alert GENERATION loop yet - that requires the
scheduler (a later step of this rollout) to actually call
app.alerts.engine.AlertEngine.evaluate() on each new bar. This endpoint
serves whatever history has accumulated in the shared AlertHistory
instance (app.api.state.get_alert_history()) so far; it does not generate
new alerts itself.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Query

from app.api import state
from app.api.converters import alert_to_schema
from app.api.schemas import AlertOut
from app.alerts.config import AlertType

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=List[AlertOut])
def get_alerts(
    symbol: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    limit: Optional[int] = Query(100, ge=1, le=1000),
):
    history = state.get_alert_history()
    parsed_type = None
    if alert_type is not None:
        try:
            parsed_type = AlertType(alert_type)
        except ValueError:
            parsed_type = None  # unknown type -> no matches, not an error; keeps this endpoint tolerant of stale frontend values

    alerts = history.list(symbol=symbol, alert_type=parsed_type, limit=limit)
    return [alert_to_schema(a) for a in alerts]
