"""
RiskManager: the single gatekeeper every proposed trade passes through
before it can actually be taken. Evaluates safeguards in a fixed order
(cheapest/most-fundamental checks first) and stops at the first hard
rejection - a rejected trade's later checks are simply not evaluated,
since they no longer matter.

INDEPENDENCE FROM THE SIGNAL ENGINE: this module has no import of
app.setup_detection, app.scoring, app.entry_engine, app.ranking, app.ml,
app.alerts, or app.backtesting anywhere in this package - see
tests/test_risk_management_independence.py, which inspects the actual
Python imports via the `ast` module and fails the build if that ever
changes. RiskManager only ever receives a ProposedTrade (models.py) - a
plain data structure with no memory of which engine produced it.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from app.risk_management.config import RiskConfig
from app.risk_management.daily_state import DailyRiskState
from app.risk_management.models import ProposedTrade, RiskDecision
from app.risk_management.position_sizing import compute_position_size, compute_risk_reward


class RiskManager:
    def __init__(self, config: RiskConfig, state: Optional[DailyRiskState] = None, today: Optional[date] = None):
        config.validate()
        self.config = config
        self.state = state if state is not None else DailyRiskState(current_date=today or date.today())

    def evaluate_trade(self, proposed: ProposedTrade, now: datetime) -> RiskDecision:
        """
        `now` is an explicit parameter (never read from the real clock
        internally) - same principle every stateful engine in this
        codebase follows, so evaluation stays deterministic and testable.
        """
        cfg = self.config

        # 1. Stale market data - a hard rejection; nothing else matters
        # if the price we'd be trading on might not reflect reality.
        if proposed.market_data_timestamp is not None:
            age_seconds = (now - proposed.market_data_timestamp).total_seconds()
            if age_seconds > cfg.max_data_age_seconds:
                return RiskDecision(
                    approved=False,
                    rejection_reasons=[
                        f"market data is stale: {age_seconds:.0f}s old, exceeds the "
                        f"{cfg.max_data_age_seconds:.0f}s limit"
                    ],
                )

        # 2. Daily loss limit already breached.
        if self.state.realized_pnl_today <= -cfg.max_daily_loss:
            return RiskDecision(
                approved=False,
                rejection_reasons=[
                    f"daily loss limit reached: realized P&L today is "
                    f"{self.state.realized_pnl_today:.2f}, limit is -{cfg.max_daily_loss:.2f}"
                ],
            )

        # 3. Max trades per day.
        if self.state.trades_taken_today >= cfg.max_trades_per_day:
            return RiskDecision(
                approved=False,
                rejection_reasons=[f"maximum trades per day reached ({cfg.max_trades_per_day})"],
            )

        # 4. Max open positions.
        if len(self.state.open_position_symbols) >= cfg.max_open_positions:
            return RiskDecision(
                approved=False,
                rejection_reasons=[f"maximum open positions reached ({cfg.max_open_positions})"],
            )

        # 5. Duplicate position in the same symbol.
        if self.state.has_open_position(proposed.symbol):
            return RiskDecision(
                approved=False,
                rejection_reasons=[f"a position in {proposed.symbol} is already open"],
            )

        # 6. Position sizing: Position Size = Max Risk Amount / Stop Loss Distance.
        max_risk_amount = cfg.effective_max_risk_amount()
        quantity = compute_position_size(max_risk_amount, proposed.entry_price, proposed.stop_loss)
        if quantity is None:
            return RiskDecision(
                approved=False,
                rejection_reasons=["could not size the position - check the stop-loss distance"],
            )

        # 7. Cap by max_position_value - CAPS the size down rather than
        # rejecting (see config.py's docstring for why).
        position_value = quantity * proposed.entry_price
        if position_value > cfg.max_position_value:
            capped_quantity = int(cfg.max_position_value / proposed.entry_price)
            if capped_quantity <= 0:
                return RiskDecision(
                    approved=False,
                    rejection_reasons=[
                        f"max_position_value ({cfg.max_position_value:.2f}) is smaller than the "
                        f"price of a single share ({proposed.entry_price:.2f})"
                    ],
                )
            quantity = capped_quantity
            position_value = quantity * proposed.entry_price

        actual_risk_amount = quantity * abs(proposed.entry_price - proposed.stop_loss)

        # 8. Risk/Reward - a WARNING, not a rejection, per the spec's
        # own wording ("show a clear warning").
        warnings = []
        risk_reward = compute_risk_reward(proposed.entry_price, proposed.stop_loss, proposed.target, proposed.direction)
        if risk_reward is not None and risk_reward < cfg.min_risk_reward:
            warnings.append(
                f"Risk/Reward {risk_reward:.2f} is below the configured minimum of {cfg.min_risk_reward:.2f}"
            )
        elif risk_reward is None and proposed.target is not None:
            warnings.append("could not compute Risk/Reward for this trade (check entry/stop/target)")

        return RiskDecision(
            approved=True,
            position_size=quantity,
            position_value=position_value,
            risk_amount=actual_risk_amount,
            risk_reward=risk_reward,
            warnings=warnings,
        )

    def record_trade_opened(self, symbol: str) -> None:
        self.state.record_trade_opened(symbol)

    def record_trade_closed(self, symbol: str, realized_pnl: float) -> None:
        self.state.record_trade_closed(symbol, realized_pnl)

    def reset_for_new_day(self, new_date: date) -> None:
        self.state.reset_for_new_day(new_date)
