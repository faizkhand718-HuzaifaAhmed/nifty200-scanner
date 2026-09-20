"""
Per-category scoring functions. Each returns a 0-1 FRACTION (not a
final point value) - engine.py multiplies by the category's configured
weight. Every function is a pure, independently-testable transformation
of already-causal Phase 4/5 values: elementwise arithmetic and .clip()
only, no new rolling/ewm/expanding computation - so no new look-ahead risk
is introduced at this layer.

Missing/NaN inputs are treated as "no credit" (fraction 0), never
fabricated into a positive contribution.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd


def _bool_to_float(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype(bool).astype(float)


def trend_score(
    adx: pd.Series,
    plus_di: pd.Series,
    minus_di: pd.Series,
    price_structure_confirmed: pd.Series,
    adx_min: float,
    adx_full: float,
    bullish: bool,
) -> pd.Series:
    """Half from ADX trend-strength (only if direction agrees), half from
    the price-structure regime (Phase 5's Higher-High/Higher-Low or
    Lower-High/Lower-Low state)."""
    direction_ok = (plus_di > minus_di) if bullish else (minus_di > plus_di)
    strength_fraction = ((adx - adx_min) / (adx_full - adx_min)).clip(lower=0, upper=1)
    strength_fraction = strength_fraction.where(direction_ok, 0.0).fillna(0.0)
    structure_fraction = _bool_to_float(price_structure_confirmed)
    return 0.5 * strength_fraction + 0.5 * structure_fraction


def vwap_score(close: pd.Series, vwap: pd.Series, distance_full_pct: float, bullish: bool) -> pd.Series:
    """Fraction of full credit based on how far price sits on the
    favorable side of VWAP, as a percentage of price."""
    distance_pct = (close - vwap) / vwap if bullish else (vwap - close) / vwap
    return (distance_pct / distance_full_pct).clip(lower=0, upper=1).fillna(0.0)


def momentum_score(rsi: pd.Series, zone_min: float, zone_max: float) -> pd.Series:
    """Peaks at the CENTER of the configured RSI zone, tapering to 0 at
    the zone's edges (and staying 0 outside it) - rewards being solidly
    within the zone, not just barely qualifying."""
    mid = (zone_min + zone_max) / 2.0
    half_width = (zone_max - zone_min) / 2.0
    return (1 - (rsi - mid).abs() / half_width).clip(lower=0, upper=1).fillna(0.0)


def ema_structure_score(ema_condition_1: pd.Series, ema_condition_2: pd.Series) -> pd.Series:
    """Simple count-based fraction: each of the two EMA alignment checks
    (9v20, 20v50) is worth half."""
    return (_bool_to_float(ema_condition_1) + _bool_to_float(ema_condition_2)) / 2.0


def volume_score(volume_above_average: pd.Series, relative_volume: pd.Series, relative_volume_full: float) -> pd.Series:
    """Half from the simple above-average check, half from how far above
    baseline (1.0x) relative volume actually is."""
    rel_fraction = ((relative_volume - 1.0) / (relative_volume_full - 1.0)).clip(lower=0, upper=1).fillna(0.0)
    avg_fraction = _bool_to_float(volume_above_average)
    return 0.5 * rel_fraction + 0.5 * avg_fraction


def breakout_score(breakout_or_breakdown: pd.Series, retest: pd.Series) -> pd.Series:
    """Half for the breakout/breakdown itself, half for a confirmed
    retest - both together earn full credit."""
    return 0.5 * _bool_to_float(breakout_or_breakdown) + 0.5 * _bool_to_float(retest)


def market_confirmation_score(
    direction_confirmed: Optional[pd.Series], nifty_adx: pd.Series, nifty_adx_full: float
) -> pd.Series:
    """Gated by direction (NIFTY must be moving the same way), scaled by
    how strongly NIFTY itself is trending (its own ADX)."""
    if direction_confirmed is None:
        return pd.Series(0.0, index=nifty_adx.index)
    strength_fraction = (nifty_adx / nifty_adx_full).clip(lower=0, upper=1).fillna(0.0)
    return _bool_to_float(direction_confirmed) * strength_fraction


def relative_strength_score(
    relative_strength: Optional[pd.Series], full: float, bullish: bool, index: pd.Index
) -> pd.Series:
    if relative_strength is None:
        return pd.Series(0.0, index=index)
    value = relative_strength if bullish else -relative_strength
    return (value / full).clip(lower=0, upper=1).fillna(0.0)


def risk_score(atr: pd.Series, close: pd.Series, ideal_atr_pct: float, tolerance_pct: float) -> pd.Series:
    """Peaks at the configured 'ideal' ATR-as-percent-of-price, penalizing
    both too little volatility (can't realistically profit) and too much
    (excessive risk). Direction-agnostic - identical for LONG and SHORT."""
    atr_pct = atr / close
    return (1 - (atr_pct - ideal_atr_pct).abs() / tolerance_pct).clip(lower=0, upper=1).fillna(0.0)
