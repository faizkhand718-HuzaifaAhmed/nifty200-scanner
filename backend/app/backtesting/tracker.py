"""
SymbolBacktestTracker: processes one symbol's historical bars in
chronological order, generating a TradeRecord for every trade the
configured entry/stop/target rules would have produced.

This is where the minimum-score GATE lives - and ONLY here, never inside
app.entry_engine, which has zero awareness of scores at all (see that
package's own architectural test). The score decides whether a candidate
setup is worth tracking; app.entry_engine.TradeLifecycle decides, using
only price action, whether and when it actually enters.

Multiple trades per symbol: once a tracked lifecycle reaches a terminal
state, a fresh one starts immediately, so a multi-month backtest captures
every qualifying opportunity for this symbol, not just the first.
"""
from __future__ import annotations

from typing import List, Optional

import pandas as pd

from app.backtesting.config import BacktestConfig
from app.backtesting.position_sizing import compute_quantity
from app.backtesting.trade_record import TradeRecord, build_trade_record, close_trade
from app.entry_engine.state_machine import TradeLifecycle
from app.entry_engine.states import TradeState


class SymbolBacktestTracker:
    def __init__(self, symbol: str, config: BacktestConfig):
        self.symbol = symbol
        self.config = config
        self.current_lifecycle: Optional[TradeLifecycle] = None
        self.current_trade: Optional[TradeRecord] = None
        self.completed_trades: List[TradeRecord] = []
        self.open_trade: Optional[TradeRecord] = None  # still active when the backtest period ends

    def _score_of(self, scoring_row: Optional[pd.Series]) -> Optional[float]:
        if scoring_row is None:
            return None
        value = scoring_row.get(f"{self.config.direction.lower()}_score")
        if value is None or pd.isna(value):
            return None
        return float(value)

    def step(
        self,
        ind_row: pd.Series,
        prev_ind_row: Optional[pd.Series],
        setup_row: pd.Series,
        scoring_row: Optional[pd.Series],
    ) -> None:
        score = self._score_of(scoring_row)

        if self.current_lifecycle is None:
            if score is None or score < self.config.min_score:
                return  # nothing being tracked, and this bar doesn't qualify to start
            self.current_lifecycle = TradeLifecycle(self.config.direction, self.config.entry_config)

        prev_state = self.current_lifecycle.state
        state = self.current_lifecycle.step(ind_row, prev_ind_row, setup_row)

        if state == TradeState.ENTRY_TRIGGER and prev_state != TradeState.ENTRY_TRIGGER:
            entry_price = self.current_lifecycle.entry_price
            stop = self.current_lifecycle.stop
            target = self.current_lifecycle.target
            if entry_price is None or stop is None:
                # No usable stop -> can't size or risk-manage the position;
                # treat as if the setup never triggered rather than take an
                # unmanaged trade.
                self.current_lifecycle = None
                return
            quantity = compute_quantity(self.config.starting_capital, self.config.risk_per_trade_pct, entry_price, stop)
            if quantity is None:
                self.current_lifecycle = None
                return
            self.current_trade = build_trade_record(
                symbol=self.symbol, direction=self.config.direction, entry_time=ind_row["timestamp"],
                entry_price_theoretical=entry_price, stop_price=stop, target_price=target,
                quantity=quantity, costs=self.config.cost_model,
            )
            return

        if state in (TradeState.TARGET_HIT, TradeState.STOP_LOSS_HIT) and self.current_trade is not None:
            exit_price = self.current_lifecycle.target if state == TradeState.TARGET_HIT else self.current_lifecycle.stop
            closed = close_trade(
                self.current_trade, exit_time=ind_row["timestamp"], exit_price_theoretical=exit_price,
                exit_reason=state.value, costs=self.config.cost_model,
            )
            self.completed_trades.append(closed)
            self.current_lifecycle = None
            self.current_trade = None
            return

        if state == TradeState.INVALIDATED:
            self.current_lifecycle = None
            self.current_trade = None
            return

        # SETUP / CONFIRMATION / POSITION_ACTIVE: check the score-based
        # abandonment rule only while not yet in a real position.
        if state in (TradeState.SETUP, TradeState.CONFIRMATION):
            if score is None or score < self.config.min_score:
                self.current_lifecycle = None

    def finalize(self) -> None:
        """Call once after the last bar. If a position was still live
        (either ENTRY_TRIGGER on the very last bar, which never got a
        chance to be evaluated as POSITION_ACTIVE, or genuinely
        POSITION_ACTIVE) when the data ran out, record it as open rather
        than silently discarding it or fabricating an exit price."""
        if self.current_trade is not None:
            self.open_trade = self.current_trade
