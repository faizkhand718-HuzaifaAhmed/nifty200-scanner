"""
Alert data model.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Set, Tuple

from app.alerts.config import AlertChannel, AlertType


@dataclass
class Alert:
    symbol: str
    alert_type: AlertType
    direction: Optional[str]  # "LONG" / "SHORT" / None
    message: str
    candle_timestamp: Any  # whatever timestamp type the bar carries (pd.Timestamp typically)
    fired_at: datetime
    channels: Set[AlertChannel]
    context: Dict[str, Any] = field(default_factory=dict)

    @property
    def dedup_key(self) -> Tuple[str, AlertType, Optional[str], Any]:
        """Two alerts with the same key are the same event - the second
        must never be re-emitted. Includes direction because a symbol can
        have independent LONG and SHORT alert streams (e.g. both sides'
        scores crossing 80 on the same candle)."""
        return (self.symbol, self.alert_type, self.direction, self.candle_timestamp)
