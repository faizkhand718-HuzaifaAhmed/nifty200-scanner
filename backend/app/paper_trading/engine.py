"""
PaperTradingEngine: manages virtual (paper) positions in memory. Opening
a position is always an explicit, caller-initiated action (see
open_position() below) - this engine never opens a position on its own
just because an entry signal exists elsewhere in the system. Closing
happens either automatically (a tracked bar's price reaches the stop or
target - see update_open_positions()) or manually (close_position_manually()).

NO REAL ORDERS ARE EVER SENT. See tests/test_paper_trading_no_real_orders.py.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from app.backtesting.costs import CostModel
from app.paper_trading.models import Direction, ExitReason, PaperPosition, close_position


class PaperTradingEngine:
    def __init__(self, cost_model: Optional[CostModel] = None):
        # None means "show clean gross P&L" - the default, matching the
        # simple field list this phase asked for. Pass a CostModel for
        # brokerage/fee-adjusted P&L (see models.py's close_position docstring).
        self.cost_model = cost_model
        self._positions: Dict[str, PaperPosition] = {}
        self._order: List[str] = []  # insertion order, for stable listing

    def open_position(
        self,
        symbol: str,
        direction: Direction,
        entry_price: float,
        quantity: int,
        stop_loss: Optional[float],
        target: Optional[float],
        entry_time: Any,
        opportunity_score_at_entry: Optional[float] = None,
        market_condition: Optional[str] = None,
        reason_for_entry: Optional[str] = None,
    ) -> PaperPosition:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if direction not in ("LONG", "SHORT"):
            raise ValueError("direction must be 'LONG' or 'SHORT'")

        position = PaperPosition(
            id=str(uuid.uuid4()), symbol=symbol, direction=direction, entry_price=entry_price,
            quantity=quantity, stop_loss=stop_loss, target=target, entry_time=entry_time,
            opportunity_score_at_entry=opportunity_score_at_entry,
            market_condition=market_condition, reason_for_entry=reason_for_entry,
        )
        self._positions[position.id] = position
        self._order.append(position.id)
        return position

    def close_position_manually(self, position_id: str, exit_time: Any, exit_price: float) -> PaperPosition:
        position = self._require_open(position_id)
        closed = close_position(position, exit_time, exit_price, "MANUAL_CLOSE", self.cost_model)
        self._positions[position_id] = closed
        return closed

    def update_open_positions(self, symbol: str, timestamp: Any, high: float, low: float) -> List[PaperPosition]:
        """
        Checks every OPEN position for `symbol` against this bar's
        high/low and closes any that reached their stop or target. If a
        single bar's range touches BOTH, this resolves to STOP_LOSS_HIT -
        the same conservative convention Phase 12's backtest engine uses,
        for the same reason (OHLC data alone can't tell you which was
        touched first intrabar). Returns the list of positions closed by
        this call (empty if none).
        """
        closed_now: List[PaperPosition] = []
        for position_id in list(self._order):
            position = self._positions[position_id]
            if not position.is_open or position.symbol != symbol:
                continue

            hit_stop = False
            hit_target = False
            if position.stop_loss is not None:
                hit_stop = low <= position.stop_loss if position.direction == "LONG" else high >= position.stop_loss
            if position.target is not None:
                hit_target = high >= position.target if position.direction == "LONG" else low <= position.target

            if hit_stop:
                closed = close_position(position, timestamp, position.stop_loss, "STOP_LOSS_HIT", self.cost_model)
            elif hit_target:
                closed = close_position(position, timestamp, position.target, "TARGET_HIT", self.cost_model)
            else:
                continue

            self._positions[position_id] = closed
            closed_now.append(closed)
        return closed_now

    def get_open_positions(self) -> List[PaperPosition]:
        return [self._positions[pid] for pid in self._order if self._positions[pid].is_open]

    def get_closed_positions(self) -> List[PaperPosition]:
        return [self._positions[pid] for pid in self._order if not self._positions[pid].is_open]

    def get_position(self, position_id: str) -> Optional[PaperPosition]:
        return self._positions.get(position_id)

    def _require_open(self, position_id: str) -> PaperPosition:
        position = self._positions.get(position_id)
        if position is None:
            raise KeyError(f"no position with id {position_id!r}")
        if not position.is_open:
            raise ValueError(f"position {position_id!r} is already closed")
        return position
