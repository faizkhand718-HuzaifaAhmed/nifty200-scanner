"""
Risk management configuration. Every limit here is a user-controlled
setting, not a hardcoded rule - none of these defaults are "correct"
values, they're a reasonable starting point to configure for your own
account and risk tolerance.

Two interpretive decisions made here (the spec didn't specify units/
semantics for these), read before relying on them:
  - max_position_value is a CURRENCY cap on one position's size
    (quantity x entry_price), not a share-count cap - share counts alone
    aren't comparable across stocks at very different prices.
  - Exceeding max_position_value CAPS the position size down (you still
    take the trade, just smaller) rather than rejecting it outright. If
    you want a hard rejection instead, that's a one-line change in
    engine.py's sizing step.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskConfig:
    account_capital: float
    risk_per_trade_pct: float = 0.01          # 1% of capital risked per trade
    max_daily_loss: float = 5000.0            # currency; trading stops for the day once hit
    max_open_positions: int = 5
    max_trades_per_day: int = 10
    max_position_value: float = 100000.0      # currency cap on one position's total value
    max_loss_per_trade: float = 5000.0        # currency; hard ceiling independent of risk_per_trade_pct
    min_risk_reward: float = 1.5              # below this -> warning, not rejection
    max_data_age_seconds: float = 60.0        # market data older than this blocks new trades

    def validate(self) -> None:
        if self.account_capital <= 0:
            raise ValueError("account_capital must be positive")
        if not (0 < self.risk_per_trade_pct <= 1):
            raise ValueError("risk_per_trade_pct must be between 0 and 1")
        if self.max_daily_loss <= 0:
            raise ValueError("max_daily_loss must be positive")
        if self.max_open_positions <= 0:
            raise ValueError("max_open_positions must be positive")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be positive")
        if self.max_position_value <= 0:
            raise ValueError("max_position_value must be positive")
        if self.max_loss_per_trade <= 0:
            raise ValueError("max_loss_per_trade must be positive")
        if self.min_risk_reward <= 0:
            raise ValueError("min_risk_reward must be positive")
        if self.max_data_age_seconds <= 0:
            raise ValueError("max_data_age_seconds must be positive")

    def effective_max_risk_amount(self) -> float:
        """The smaller of the percentage-based risk and the hard per-
        trade loss ceiling - whichever is more conservative governs."""
        return min(self.account_capital * self.risk_per_trade_pct, self.max_loss_per_trade)
