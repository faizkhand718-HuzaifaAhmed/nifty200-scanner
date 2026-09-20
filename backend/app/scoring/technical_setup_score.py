"""
Technical Setup Score: a transparent, rules-based 0-100 score built
specifically for the daily-timeframe data NSE MCP actually provides.

WHY THIS IS SEPARATE FROM app.scoring.engine.OpportunityScoringEngine
(Phase 6): that engine's categories - VWAP distance, EMA structure
against an intraday session, Market Confirmation via same-day NIFTY
correlation, Breakout via intraday pivot levels - are built around
INTRADAY 15-minute data. None of that data exists in the NSE MCP path
(see app/market_data/providers/nse_mcp_provider.py's module docstring).
Rather than force daily EOD data through an engine designed for intraday
bars, this is new code for the categories that genuinely make sense on
daily data, as specified: Trend, Momentum, Volume, RSI, Relative
strength, Breakout/52-week position.

THIS IS NOT A PROBABILITY. Every score here is a deterministic function
of already-computed indicator values - see compute() for the exact
formula behind every category, and TechnicalSetupResult.explanation for
a human-readable breakdown. Call it "Technical Setup Score," never a
probability or guarantee of price movement - enforced by naming
throughout this module and the API schema it feeds.

Any category whose required data is unavailable contributes 0 to both
the numerator AND denominator - the total is rescaled to /100 using only
the categories that were actually computable, and each category's
`available` flag says exactly which ones those were. This is "Insufficient
data," made structural rather than a fabricated 0 that would silently
drag the score down.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass
class TechnicalSetupScoreConfig:
    trend_weight: float = 20.0
    momentum_weight: float = 15.0
    volume_weight: float = 15.0
    rsi_weight: float = 15.0
    relative_strength_weight: float = 15.0
    breakout_52week_weight: float = 20.0

    momentum_return_floor_pct: float = -5.0
    momentum_return_ceiling_pct: float = 15.0
    momentum_lookback_days: int = 20
    volume_relvol_floor: float = 0.5
    volume_relvol_ceiling: float = 1.5
    rsi_ideal: float = 60.0
    rsi_full_score_floor: float = 45.0
    rsi_full_score_ceiling: float = 70.0
    rsi_zero_score_floor: float = 30.0
    rsi_zero_score_ceiling: float = 85.0
    relative_strength_lookback_days: int = 20
    relative_strength_floor_pct: float = -5.0
    relative_strength_ceiling_pct: float = 10.0
    breakout_floor_pct_from_high: float = -25.0
    breakout_ceiling_pct_from_high: float = 0.0

    def validate(self) -> None:
        weights = [
            self.trend_weight, self.momentum_weight, self.volume_weight,
            self.rsi_weight, self.relative_strength_weight, self.breakout_52week_weight,
        ]
        if any(w < 0 for w in weights):
            raise ValueError("category weights must be non-negative")
        if sum(weights) <= 0:
            raise ValueError("at least one category weight must be positive")


@dataclass
class CategoryResult:
    name: str
    available: bool
    score: Optional[float] = None
    max_score: float = 0.0
    explanation: str = ""


@dataclass
class TechnicalSetupResult:
    total_score: float
    categories: List[CategoryResult] = field(default_factory=list)
    unavailable_categories: List[str] = field(default_factory=list)

    def as_breakdown_dict(self) -> Dict[str, Dict]:
        return {
            c.name: {"available": c.available, "score": c.score, "max_score": c.max_score, "explanation": c.explanation}
            for c in self.categories
        }


def _linear_score(value: Optional[float], floor: float, ceiling: float, weight: float) -> Optional[float]:
    if value is None:
        return None
    if ceiling == floor:
        return weight if value >= ceiling else 0.0
    fraction = (value - floor) / (ceiling - floor)
    return _clip(fraction) * weight


def _trapezoid_score(value: Optional[float], zero_floor: float, full_floor: float, full_ceiling: float, zero_ceiling: float, weight: float) -> Optional[float]:
    if value is None:
        return None
    if value <= zero_floor or value >= zero_ceiling:
        return 0.0
    if full_floor <= value <= full_ceiling:
        return weight
    if value < full_floor:
        return _clip((value - zero_floor) / (full_floor - zero_floor)) * weight
    return _clip((zero_ceiling - value) / (zero_ceiling - full_ceiling)) * weight


def compute_technical_setup_score(
    close: float,
    ema_20: Optional[float],
    ema_50: Optional[float],
    ema_200: Optional[float],
    rsi: Optional[float],
    daily_relative_volume: Optional[float],
    return_20d_pct: Optional[float],
    stock_return_pct_for_relative_strength: Optional[float],
    nifty_return_pct_for_relative_strength: Optional[float],
    pct_from_52w_high: Optional[float],
    config: Optional[TechnicalSetupScoreConfig] = None,
) -> TechnicalSetupResult:
    cfg = config or TechnicalSetupScoreConfig()
    cfg.validate()
    categories: List[CategoryResult] = []

    if ema_20 is not None and ema_50 is not None and ema_200 is not None:
        checks = [close > ema_20, ema_20 > ema_50, ema_50 > ema_200]
        aligned = sum(checks)
        score = (aligned / 3) * cfg.trend_weight
        categories.append(CategoryResult(
            "trend", True, score, cfg.trend_weight,
            f"{aligned}/3 EMA alignment conditions met (close>EMA20>EMA50>EMA200 = fully bullish)",
        ))
    else:
        categories.append(CategoryResult("trend", False, None, cfg.trend_weight, "insufficient EMA history"))

    score = _linear_score(return_20d_pct, cfg.momentum_return_floor_pct, cfg.momentum_return_ceiling_pct, cfg.momentum_weight)
    categories.append(CategoryResult(
        "momentum", score is not None, score, cfg.momentum_weight,
        f"{cfg.momentum_lookback_days}-day return {return_20d_pct:.2f}%" if return_20d_pct is not None else "insufficient price history",
    ))

    score = _linear_score(daily_relative_volume, cfg.volume_relvol_floor, cfg.volume_relvol_ceiling, cfg.volume_weight)
    categories.append(CategoryResult(
        "volume", score is not None, score, cfg.volume_weight,
        f"volume is {daily_relative_volume:.2f}x the 20-day average" if daily_relative_volume is not None else "insufficient volume history",
    ))

    score = _trapezoid_score(rsi, cfg.rsi_zero_score_floor, cfg.rsi_full_score_floor, cfg.rsi_full_score_ceiling, cfg.rsi_zero_score_ceiling, cfg.rsi_weight)
    categories.append(CategoryResult(
        "rsi", score is not None, score, cfg.rsi_weight,
        f"RSI is {rsi:.1f}" if rsi is not None else "insufficient price history",
    ))

    relative_return = None
    if stock_return_pct_for_relative_strength is not None and nifty_return_pct_for_relative_strength is not None:
        relative_return = stock_return_pct_for_relative_strength - nifty_return_pct_for_relative_strength
    score = _linear_score(relative_return, cfg.relative_strength_floor_pct, cfg.relative_strength_ceiling_pct, cfg.relative_strength_weight)
    categories.append(CategoryResult(
        "relative_strength", score is not None, score, cfg.relative_strength_weight,
        f"{relative_return:+.2f}% vs NIFTY over the same period" if relative_return is not None else "NIFTY index data unavailable for comparison",
    ))

    score = _linear_score(pct_from_52w_high, cfg.breakout_floor_pct_from_high, cfg.breakout_ceiling_pct_from_high, cfg.breakout_52week_weight)
    categories.append(CategoryResult(
        "breakout_52week", score is not None, score, cfg.breakout_52week_weight,
        f"{pct_from_52w_high:.2f}% from the 52-week high" if pct_from_52w_high is not None else "insufficient history for a 52-week range",
    ))

    available = [c for c in categories if c.available]
    unavailable = [c.name for c in categories if not c.available]
    available_weight = sum(c.max_score for c in available)
    total = (sum(c.score for c in available) / available_weight * 100) if available_weight > 0 else 0.0

    return TechnicalSetupResult(total_score=total, categories=categories, unavailable_categories=unavailable)
