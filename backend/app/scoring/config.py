"""
Configurable weights and normalization constants for the Opportunity
Scoring Engine.

ScoringWeights controls how much each category is worth out of 100.
ScoringNormalization controls the "full credit" scaling points used to
turn continuous indicator values (ADX, RSI, ATR%, relative volume,
relative strength) into 0-1 fractions before they're multiplied by a
category's weight.

None of the ScoringNormalization defaults are backtested "correct" values
- they are reasonable starting points to be tuned once backtesting (a
later phase) can actually measure their effect on outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass
class ScoringWeights:
    trend: float = 20.0
    volume: float = 15.0
    vwap: float = 15.0
    momentum: float = 10.0
    ema_structure: float = 10.0
    breakout: float = 10.0
    market_confirmation: float = 10.0
    relative_strength: float = 5.0
    risk: float = 5.0

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    def total(self) -> float:
        return sum(self.as_dict().values())

    def validate(self) -> None:
        values = self.as_dict()
        negative = [k for k, v in values.items() if v < 0]
        if negative:
            raise ValueError(f"weights must be non-negative, got negative values for: {negative}")
        total = self.total()
        if abs(total - 100.0) > 1e-6:
            raise ValueError(
                f"weights must sum to 100 (got {total}). Adjust the individual "
                f"weights, or build via ScoringWeights.rescaled(...) to "
                f"auto-normalize arbitrary relative weights to 100."
            )

    @classmethod
    def rescaled(cls, **kwargs) -> "ScoringWeights":
        """Build weights from arbitrary relative values and rescale them to
        sum to exactly 100 - useful if you want to specify weights by
        relative importance (e.g. trend=4, volume=3, ...) without doing
        the sum-to-100 arithmetic yourself."""
        instance = cls(**kwargs)
        total = instance.total()
        if total <= 0:
            raise ValueError("weights must sum to a positive number")
        factor = 100.0 / total
        return cls(**{k: v * factor for k, v in instance.as_dict().items()})


@dataclass
class ScoringNormalization:
    # ADX value that earns full Trend-strength credit (direction must also
    # be correct, or Trend's ADX component contributes 0 regardless).
    adx_full: float = 40.0

    # Distance from VWAP (as a fraction of price) that earns full VWAP
    # credit, e.g. 0.005 = 0.5% away from VWAP -> full marks.
    vwap_distance_full_pct: float = 0.005

    # Relative volume multiple that earns full Volume credit (baseline is
    # 1.0x = average volume, no credit; this is the multiple for 100%).
    relative_volume_full: float = 2.0

    # Relative-strength-vs-NIFTY value that earns full Relative Strength
    # credit, e.g. 0.03 = 3% rolling outperformance -> full marks.
    relative_strength_full: float = 0.03

    # Risk/Volatility: the "sweet spot" ATR as a fraction of price, and how
    # far (in the same units) you can be from it before the Risk category
    # score hits 0. Too LOW volatility (can't realistically profit) and
    # too HIGH volatility (excessive risk) are both penalized.
    ideal_atr_pct: float = 0.008
    atr_tolerance_pct: float = 0.008

    # NIFTY's own ADX value that earns full Market Confirmation strength
    # credit (direction must also agree, or this contributes 0).
    nifty_adx_full: float = 30.0
