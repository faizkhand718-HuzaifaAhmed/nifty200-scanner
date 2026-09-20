"""
Backtest configuration. Combines Phase 10's EntryEngineConfig (entry
rule, stop-loss method, target method - unchanged from Phase 10, same
methods, same meaning) with backtest-specific settings: minimum score
gate, position sizing, and transaction costs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.backtesting.costs import CostModel
from app.entry_engine.config import EntryEngineConfig

Direction = Literal["LONG", "SHORT"]


@dataclass
class BacktestConfig:
    direction: Direction = "LONG"
    entry_config: EntryEngineConfig = field(default_factory=EntryEngineConfig)
    cost_model: CostModel = field(default_factory=CostModel)

    # Minimum Opportunity Score (Phase 6) required to START watching a
    # candidate setup - and, if the score later drops below this before
    # the setup ever triggers, to ABANDON it. This gates whether a setup
    # is worth watching; it never decides WHEN to enter (see
    # app/entry_engine's own no-scoring-dependency rule, which this
    # module does not violate - the score check happens here, in the
    # backtest layer, entirely outside app.entry_engine).
    min_score: float = 60.0

    starting_capital: float = 100000.0
    risk_per_trade_pct: float = 0.01  # 1% of capital risked per trade

    def validate(self) -> None:
        self.cost_model.validate()
        if self.direction not in ("LONG", "SHORT"):
            raise ValueError("direction must be 'LONG' or 'SHORT'")
        if not (0 <= self.min_score <= 100):
            raise ValueError("min_score must be between 0 and 100")
        if self.starting_capital <= 0:
            raise ValueError("starting_capital must be positive")
        if not (0 < self.risk_per_trade_pct <= 1):
            raise ValueError("risk_per_trade_pct must be between 0 and 1")
