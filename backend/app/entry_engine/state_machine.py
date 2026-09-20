"""
TradeLifecycle: a per-(symbol, direction) state machine tracking a
candidate setup through 7 states, bar by bar.

HARD RULE, ENFORCED BY TEST NOT JUST CONVENTION: this module and every
other module in app.entry_engine has ZERO dependency on app.scoring. The
Opportunity Score measures setup QUALITY; it never decides WHEN to enter.
See tests/test_entry_engine_no_score_dependency.py, which inspects this
package's actual imports (via the `ast` module, not just grep) and fails
the build if that ever changes.

State transitions (see states.py for the enum):
  SETUP <-> CONFIRMATION   : entry method's "approaching" flag toggles
  SETUP/CONFIRMATION -> ENTRY_TRIGGER : entry method's "triggered" flag fires
  SETUP/CONFIRMATION -> INVALIDATED   : price closes past the opposing
                                        structural level (support for
                                        LONG, resistance for SHORT) before
                                        ever triggering, OR max_bars_
                                        without_trigger is exceeded
  ENTRY_TRIGGER -> POSITION_ACTIVE    : automatic, on the NEXT bar (entry
                                        executes at the trigger bar's
                                        close; exits are only ever
                                        evaluated on bars AFTER that)
  POSITION_ACTIVE -> TARGET_HIT       : bar's high (LONG) / low (SHORT)
                                        reaches the target
  POSITION_ACTIVE -> STOP_LOSS_HIT    : bar's low (LONG) / high (SHORT)
                                        reaches the stop
  (TARGET_HIT, STOP_LOSS_HIT, INVALIDATED are terminal - no further change)

CONVENTION: if a single bar's range touches BOTH the stop and the target,
this reports STOP_LOSS_HIT - OHLC data alone can't tell you which was
touched first intrabar, and assuming the better outcome would overstate
performance. This is a standard, conservative backtesting convention, not
a claim about what actually happened.
"""
from __future__ import annotations

from typing import List, Literal, Optional

import pandas as pd

from app.entry_engine.config import ENTRY_METHOD_ALLOWED_DIRECTIONS, EntryEngineConfig
from app.entry_engine.entry_methods import ENTRY_METHOD_FUNCTIONS, BarContext
from app.entry_engine.states import TERMINAL_STATES, TradeState
from app.entry_engine.stop_target import compute_stop, compute_target

Direction = Literal["LONG", "SHORT"]


def _valid(x) -> bool:
    return x is not None and not pd.isna(x)


class TradeLifecycle:
    def __init__(self, direction: Direction, config: Optional[EntryEngineConfig] = None):
        if direction not in ("LONG", "SHORT"):
            raise ValueError(f"direction must be 'LONG' or 'SHORT', got {direction!r}")
        self.config = config or EntryEngineConfig()

        allowed = ENTRY_METHOD_ALLOWED_DIRECTIONS[self.config.entry_method]
        if direction not in allowed:
            raise ValueError(
                f"entry method {self.config.entry_method.value!r} is not valid for {direction} "
                f"(valid for: {sorted(allowed)}). Choose a different entry_method or direction."
            )

        self.direction = direction
        self.state = TradeState.SETUP
        self.bars_in_setup = 0
        self.entry_price: Optional[float] = None
        self.stop: Optional[float] = None
        self.target: Optional[float] = None
        self._recent_swing_low: Optional[float] = None
        self._recent_swing_high: Optional[float] = None
        self._entry_fn = ENTRY_METHOD_FUNCTIONS[self.config.entry_method.value]

    def _update_swing_memory(self, ind_row: pd.Series) -> None:
        low = ind_row.get("swing_low_price")
        high = ind_row.get("swing_high_price")
        if _valid(low):
            self._recent_swing_low = low
        if _valid(high):
            self._recent_swing_high = high

    def _is_invalidated_pre_entry(self, ind_row: pd.Series) -> bool:
        if self.direction == "LONG":
            support = ind_row.get("support")
            return _valid(support) and ind_row["close"] < support
        else:
            resistance = ind_row.get("resistance")
            return _valid(resistance) and ind_row["close"] > resistance

    def _check_exit(self, ind_row: pd.Series) -> Optional[TradeState]:
        hit_stop = False
        hit_target = False
        if self.stop is not None:
            hit_stop = ind_row["low"] <= self.stop if self.direction == "LONG" else ind_row["high"] >= self.stop
        if self.target is not None:
            hit_target = ind_row["high"] >= self.target if self.direction == "LONG" else ind_row["low"] <= self.target

        if hit_stop:
            return TradeState.STOP_LOSS_HIT  # conservative: stop wins ties, see module docstring
        if hit_target:
            return TradeState.TARGET_HIT
        return None

    def step(self, ind_row: pd.Series, prev_ind_row: Optional[pd.Series], setup_row: pd.Series) -> TradeState:
        """Advances the state machine by exactly one bar and returns the
        state to report FOR THIS BAR. Call once per bar, in chronological
        order - this machine has memory and is not safe to call out of
        order or skip bars."""
        self._update_swing_memory(ind_row)

        if self.state == TradeState.ENTRY_TRIGGER:
            # The bar that reported ENTRY_TRIGGER already happened in the
            # previous call; from this bar onward we're evaluating exits.
            self.state = TradeState.POSITION_ACTIVE

        if self.state in TERMINAL_STATES:
            return self.state

        if self.state == TradeState.POSITION_ACTIVE:
            exit_state = self._check_exit(ind_row)
            if exit_state is not None:
                self.state = exit_state
            return self.state

        # SETUP or CONFIRMATION: check invalidation before checking entry -
        # a setup that has already structurally failed shouldn't be able
        # to "trigger" on the same bar it failed.
        if self._is_invalidated_pre_entry(ind_row):
            self.state = TradeState.INVALIDATED
            return self.state

        ctx = BarContext(ind=ind_row, prev_ind=prev_ind_row, setup=setup_row, direction=self.direction)
        approaching, triggered = self._entry_fn(ctx, self.config)

        if triggered:
            self.entry_price = float(ind_row["close"])
            self.stop = compute_stop(
                self.config.stop_method, self.entry_price, self.direction, ind_row, self.config,
                recent_swing_low=self._recent_swing_low, recent_swing_high=self._recent_swing_high,
            )
            self.target = compute_target(
                self.config.target_method, self.entry_price, self.stop, self.direction, ind_row, self.config
            )
            self.state = TradeState.ENTRY_TRIGGER
            return self.state

        self.bars_in_setup += 1
        if self.bars_in_setup > self.config.max_bars_without_trigger:
            self.state = TradeState.INVALIDATED
            return self.state

        self.state = TradeState.CONFIRMATION if approaching else TradeState.SETUP
        return self.state

    def run(self, indicators_df: pd.DataFrame, setup_df: pd.DataFrame) -> pd.DataFrame:
        """Runs the full sequence and returns a DataFrame with one row per
        input bar: timestamp, lifecycle_state, entry_price, stop_loss,
        target (the latter three NaN until/unless an entry has occurred)."""
        if len(indicators_df) != len(setup_df):
            raise ValueError("indicators_df and setup_df must have the same number of rows")

        records: List[dict] = []
        prev_ind_row: Optional[pd.Series] = None
        for i in range(len(indicators_df)):
            ind_row = indicators_df.iloc[i]
            setup_row = setup_df.iloc[i]
            state = self.step(ind_row, prev_ind_row, setup_row)
            records.append(
                {
                    "timestamp": ind_row["timestamp"],
                    "lifecycle_state": state.value,
                    "entry_price": self.entry_price,
                    "stop_loss": self.stop,
                    "target": self.target,
                }
            )
            prev_ind_row = ind_row

        return pd.DataFrame(records)
