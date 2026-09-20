"""
RiskGatedPaperTradingEngine: combines Phase 16's RiskManager with Phase 13's
PaperTradingEngine in the one correct order - evaluate risk first, only open
a position if approved.

WHY THIS EXISTS (a QA-audit finding, not a bug in either module): each
module behaves correctly for its own scope - PaperTradingEngine.open_position()
was always documented as a bare "track whatever I'm told to track" primitive,
and RiskManager was always documented as the gatekeeper. But nothing
structurally FORCED a caller to check risk before opening a position, and
the existing frontend "Paper trade this setup" button (Phase 13) calls
open_position() directly with no risk check in front of it at all - meaning
duplicate positions, oversized positions, and trades placed after the daily
loss limit was hit could all slip through in practice, even though every
individual safeguard was correctly implemented.

This class is the fix: it is the ONLY supported way to open a risk-checked
paper position going forward, and there is no code path through it that
skips RiskManager.evaluate_trade(). Existing direct callers of
PaperTradingEngine.open_position() (like PaperTradeButton.tsx, once a real
backend endpoint exists) should be migrated to call this instead.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from app.paper_trading.engine import PaperTradingEngine
from app.paper_trading.models import PaperPosition
from app.risk_management.engine import RiskManager
from app.risk_management.models import ProposedTrade, RiskDecision


@dataclass
class RiskGatedOpenResult:
    decision: RiskDecision
    position: Optional[PaperPosition] = None

    @property
    def opened(self) -> bool:
        return self.position is not None


class RiskGatedPaperTradingEngine:
    def __init__(self, risk_manager: RiskManager, paper_engine: Optional[PaperTradingEngine] = None):
        self.risk_manager = risk_manager
        self.paper_engine = paper_engine or PaperTradingEngine()

    def try_open_position(
        self,
        proposed: ProposedTrade,
        now: datetime,
        opportunity_score_at_entry: Optional[float] = None,
        market_condition: Optional[str] = None,
        reason_for_entry: Optional[str] = None,
    ) -> RiskGatedOpenResult:
        """Always evaluates risk first. Returns a result with
        position=None (and the rejection reasons in .decision) if risk
        management does not approve - there is no way to reach the
        PaperTradingEngine.open_position() call below without passing
        that check."""
        decision = self.risk_manager.evaluate_trade(proposed, now=now)
        if not decision.approved:
            return RiskGatedOpenResult(decision=decision, position=None)

        position = self.paper_engine.open_position(
            symbol=proposed.symbol,
            direction=proposed.direction,
            entry_price=proposed.entry_price,
            quantity=decision.position_size,
            stop_loss=proposed.stop_loss,
            target=proposed.target,
            entry_time=now,
            opportunity_score_at_entry=opportunity_score_at_entry,
            market_condition=market_condition,
            reason_for_entry=reason_for_entry,
        )
        self.risk_manager.record_trade_opened(proposed.symbol)
        return RiskGatedOpenResult(decision=decision, position=position)

    def close_position(self, position_id: str, exit_time: Any, exit_price: float) -> PaperPosition:
        """Closes the position AND updates RiskManager's daily P&L/open-
        position tracking together - closing through PaperTradingEngine
        alone would leave RiskManager's state stale (still counting the
        position as open, missing the realized P&L for the daily-loss
        check), silently reintroducing the same class of gap this class
        exists to close."""
        position = self.paper_engine.close_position_manually(position_id, exit_time, exit_price)
        self.risk_manager.record_trade_closed(position.symbol, realized_pnl=position.pnl or 0.0)
        return position
