"""
AlertEngine: evaluates all configured alert conditions for one symbol's
latest bar update and returns any NEW alerts, already deduped against the
provided AlertHistory. This engine introduces no new price/indicator math
of its own - every condition reads values that Phases 4-7 and 10 already
computed. VWAP reclaim/rejection specifically REUSE Phase 10's own
crossing-detection functions (app.entry_engine.entry_methods) rather than
reimplementing that logic differently - the same "don't calculate signals
differently in two places" principle Phase 9 required of the frontend
applies here, within the backend, too.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

import pandas as pd

from app.alerts.config import AlertConfig, AlertType
from app.alerts.history import AlertHistory
from app.alerts.models import Alert
from app.entry_engine.config import EntryEngineConfig
from app.entry_engine.entry_methods import BarContext, vwap_reclaim, vwap_rejection


class AlertEngine:
    def __init__(self, config: Optional[AlertConfig] = None, history: Optional[AlertHistory] = None):
        self.config = config if config is not None else AlertConfig()
        self.history = history if history is not None else AlertHistory()
        # Only used to satisfy vwap_reclaim/vwap_rejection's config
        # parameter - they don't use approach_tolerance_pct to decide
        # `triggered` (only `approaching`, which we don't use here), so
        # the specific values here don't affect alert firing.
        self._entry_cfg = EntryEngineConfig()

    def evaluate(
        self,
        symbol: str,
        ind_row: pd.Series,
        prev_ind_row: Optional[pd.Series],
        setup_row: pd.Series,
        scoring_row: Optional[pd.Series] = None,
        prev_scoring_row: Optional[pd.Series] = None,
        ranking_direction: Optional[str] = None,
        prev_ranking_direction: Optional[str] = None,
        lifecycle_state: Optional[str] = None,
        prev_lifecycle_state: Optional[str] = None,
        lifecycle_direction: Optional[str] = None,
    ) -> List[Alert]:
        """
        Every parameter is OPTIONAL except symbol/ind_row/setup_row - a
        caller only tracking, say, breakout alerts doesn't need to supply
        scoring or lifecycle data. Conditions whose required inputs are
        missing simply don't fire (never fabricated).
        """
        candle_ts = ind_row["timestamp"]
        new_alerts: List[Alert] = []
        cfg = self.config

        def emit(alert_type: AlertType, direction: Optional[str], message: str, context: Optional[dict] = None) -> None:
            if alert_type not in cfg.enabled_types:
                return
            key = (symbol, alert_type, direction, candle_ts)
            if self.history.has_fired(key):
                return
            alert = Alert(
                symbol=symbol,
                alert_type=alert_type,
                direction=direction,
                message=message,
                candle_timestamp=candle_ts,
                fired_at=datetime.now(timezone.utc),
                channels=cfg.channels_for(alert_type),
                context=context or {},
            )
            self.history.add(alert)
            new_alerts.append(alert)

        # --- Score crosses 80 / 90 (each side independently) ---
        if scoring_row is not None and prev_scoring_row is not None:
            for side in ("long", "short"):
                curr = scoring_row.get(f"{side}_score")
                prev = prev_scoring_row.get(f"{side}_score")
                if self._crosses(prev, curr, cfg.score_threshold_80):
                    emit(AlertType.SCORE_CROSSES_80, side.upper(), f"{symbol} {side.upper()} score crossed {cfg.score_threshold_80:.0f}", {"score": curr})
                if self._crosses(prev, curr, cfg.score_threshold_90):
                    emit(AlertType.SCORE_CROSSES_90, side.upper(), f"{symbol} {side.upper()} score crossed {cfg.score_threshold_90:.0f}", {"score": curr})

        # --- LONG / SHORT setup identified (Phase 7's leading direction) ---
        if self._becomes(prev_ranking_direction, ranking_direction, "LONG"):
            emit(AlertType.LONG_SETUP, "LONG", f"{symbol} LONG setup identified")
        if self._becomes(prev_ranking_direction, ranking_direction, "SHORT"):
            emit(AlertType.SHORT_SETUP, "SHORT", f"{symbol} SHORT setup identified")

        # --- Breakout / Breakdown (Phase 5 booleans, direction-locked) ---
        if bool(setup_row.get("long_breakout", False)):
            emit(AlertType.BREAKOUT, "LONG", f"{symbol} breakout above resistance")
        if bool(setup_row.get("short_breakdown", False)):
            emit(AlertType.BREAKDOWN, "SHORT", f"{symbol} breakdown below support")

        # --- VWAP reclaim / rejection (reuses Phase 10's crossing logic) ---
        if prev_ind_row is not None:
            long_ctx = BarContext(ind=ind_row, prev_ind=prev_ind_row, setup=setup_row, direction="LONG")
            _, reclaimed = vwap_reclaim(long_ctx, self._entry_cfg)
            if reclaimed:
                emit(AlertType.VWAP_RECLAIM, "LONG", f"{symbol} reclaimed VWAP")

            short_ctx = BarContext(ind=ind_row, prev_ind=prev_ind_row, setup=setup_row, direction="SHORT")
            _, rejected = vwap_rejection(short_ctx, self._entry_cfg)
            if rejected:
                emit(AlertType.VWAP_REJECTION, "SHORT", f"{symbol} rejected at VWAP")

        # --- Entry trigger / stop loss / target (Phase 10 lifecycle transitions) ---
        if lifecycle_state is not None:
            if self._becomes(prev_lifecycle_state, lifecycle_state, "ENTRY_TRIGGER"):
                emit(AlertType.ENTRY_TRIGGER, lifecycle_direction, f"{symbol} entry triggered")
            if self._becomes(prev_lifecycle_state, lifecycle_state, "STOP_LOSS_HIT"):
                emit(AlertType.STOP_LOSS, lifecycle_direction, f"{symbol} stop loss hit")
            if self._becomes(prev_lifecycle_state, lifecycle_state, "TARGET_HIT"):
                emit(AlertType.TARGET, lifecycle_direction, f"{symbol} target hit")

        return new_alerts

    @staticmethod
    def _crosses(prev, curr, threshold: float) -> bool:
        if prev is None or curr is None or pd.isna(prev) or pd.isna(curr):
            return False
        return prev < threshold <= curr

    @staticmethod
    def _becomes(prev, curr, target: str) -> bool:
        return curr == target and prev != target
