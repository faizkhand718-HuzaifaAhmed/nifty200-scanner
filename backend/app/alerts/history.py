"""
In-memory alert history. Deliberately a plain, swappable store (an
injected dependency of AlertEngine, not a global) - a DB-backed
implementation with the same three methods (has_fired, add, list) can
replace this later without touching AlertEngine at all.
"""
from __future__ import annotations

from typing import List, Optional, Set

from app.alerts.config import AlertType
from app.alerts.models import Alert


class AlertHistory:
    def __init__(self):
        self._alerts: List[Alert] = []
        self._seen_keys: Set[tuple] = set()

    def has_fired(self, dedup_key: tuple) -> bool:
        return dedup_key in self._seen_keys

    def add(self, alert: Alert) -> None:
        self._seen_keys.add(alert.dedup_key)
        self._alerts.append(alert)

    def list(
        self,
        symbol: Optional[str] = None,
        alert_type: Optional[AlertType] = None,
        limit: Optional[int] = None,
    ) -> List[Alert]:
        """Most-recent-first, optionally filtered."""
        results = self._alerts
        if symbol is not None:
            results = [a for a in results if a.symbol == symbol]
        if alert_type is not None:
            results = [a for a in results if a.alert_type == alert_type]
        results = list(reversed(results))
        if limit is not None:
            results = results[:limit]
        return results

    def clear(self) -> None:
        self._alerts.clear()
        self._seen_keys.clear()

    def __len__(self) -> int:
        return len(self._alerts)
