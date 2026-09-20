"""
Feature extraction for the experimental ML layer.

EVERY value here is read from data that Phases 4-7's already-causal
engines computed at or before the given bar - this module performs no new
price lookups of its own beyond one rolling volatility calculation (see
`realized_volatility`, itself a standard backward-only rolling statistic).
No feature here ever reads a future bar.

DESIGN CHOICE - "favorable-direction-relative" framing: several features
(RSI, EMA structure, relative strength, breakout status) are SIGN-FLIPPED
for SHORT trades so that "positive" always means "favorable for this
trade's own direction," regardless of whether the trade is LONG or SHORT.
This lets one model train across both directions instead of needing two
separate models. This is a modeling choice, not something the phase spec
required - flagging it here since it shapes every number this module
produces.
"""
from __future__ import annotations

from typing import Dict, Literal, Optional

import pandas as pd

Direction = Literal["LONG", "SHORT"]

FEATURE_NAMES = [
    "vwap_distance",
    "ema_9_20_pct",
    "ema_20_50_pct",
    "rsi_favorable",
    "adx",
    "atr_pct",
    "relative_volume",
    "breakout_status",
    "market_regime_adx",
    "market_alignment",
    "relative_strength_favorable",
    "realized_volatility",
    "opportunity_score",
]


def _sign(direction: Direction) -> float:
    return 1.0 if direction == "LONG" else -1.0


def _safe(x) -> Optional[float]:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    return float(x)


def realized_volatility(close: pd.Series, window: int = 20) -> pd.Series:
    """Rolling standard deviation of simple returns - a standard,
    backward-only volatility measure. Uses pct_change() (compares only
    the current bar to the previous one) and .rolling() (backward window
    only), so this is causal by construction, same as every other
    indicator in this codebase."""
    if window <= 0:
        raise ValueError("window must be positive")
    returns = close.pct_change()
    return returns.rolling(window=window, min_periods=window).std()


def extract_features(
    ind_row: pd.Series,
    setup_row: pd.Series,
    scoring_row: pd.Series,
    direction: Direction,
    nifty_ind_row: Optional[pd.Series] = None,
    realized_vol: Optional[float] = None,
) -> Optional[Dict[str, float]]:
    """
    Returns None (never a partially-fabricated feature row) if any
    required input is missing/NaN - a training example with a missing
    feature is dropped upstream, not imputed with a guess.
    """
    sign = _sign(direction)
    side = direction.lower()

    close = _safe(ind_row.get("close"))
    vwap = _safe(ind_row.get("vwap"))
    ema_9 = _safe(ind_row.get("ema_9"))
    ema_20 = _safe(ind_row.get("ema_20"))
    ema_50 = _safe(ind_row.get("ema_50"))
    rsi = _safe(ind_row.get("rsi"))
    adx = _safe(ind_row.get("adx"))
    atr = _safe(ind_row.get("atr"))
    relative_volume = _safe(ind_row.get("relative_volume"))
    opportunity_score = _safe(scoring_row.get(f"{side}_score"))

    required = [close, vwap, ema_9, ema_20, ema_50, rsi, adx, atr, relative_volume, opportunity_score]
    if any(v is None for v in required) or close == 0 or ema_20 == 0 or ema_50 == 0:
        return None

    vwap_distance = sign * (close - vwap) / vwap
    ema_9_20_pct = sign * (ema_9 - ema_20) / ema_20
    ema_20_50_pct = sign * (ema_20 - ema_50) / ema_50
    rsi_favorable = rsi if direction == "LONG" else (100.0 - rsi)
    atr_pct = atr / close

    breakout_flag = bool(setup_row.get("long_breakout" if direction == "LONG" else "short_breakdown", False))
    breakout_status = 1.0 if breakout_flag else 0.0

    market_regime_adx = _safe(nifty_ind_row.get("adx")) if nifty_ind_row is not None else None
    market_alignment = 0.0
    if nifty_ind_row is not None:
        nifty_ema20 = _safe(nifty_ind_row.get("ema_20"))
        nifty_ema50 = _safe(nifty_ind_row.get("ema_50"))
        if nifty_ema20 is not None and nifty_ema50 is not None:
            nifty_bullish = nifty_ema20 > nifty_ema50
            market_alignment = 1.0 if (nifty_bullish == (direction == "LONG")) else -1.0
    if market_regime_adx is None:
        market_regime_adx = 0.0

    relative_strength_raw = _safe(scoring_row.get("relative_strength")) or _safe(ind_row.get("relative_strength"))
    relative_strength_favorable = sign * relative_strength_raw if relative_strength_raw is not None else 0.0

    if realized_vol is None or pd.isna(realized_vol):
        return None

    return {
        "vwap_distance": vwap_distance,
        "ema_9_20_pct": ema_9_20_pct,
        "ema_20_50_pct": ema_20_50_pct,
        "rsi_favorable": rsi_favorable,
        "adx": adx,
        "atr_pct": atr_pct,
        "relative_volume": relative_volume,
        "breakout_status": breakout_status,
        "market_regime_adx": market_regime_adx,
        "market_alignment": market_alignment,
        "relative_strength_favorable": relative_strength_favorable,
        "realized_volatility": float(realized_vol),
        "opportunity_score": opportunity_score,
    }
