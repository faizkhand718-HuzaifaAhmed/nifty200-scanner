"""
Price-structure regime derived from Phase 4's sparse swing-confirmation
flags (higher_high, lower_high, higher_low, lower_low - each True only at
the bar where that specific swing was CONFIRMED; see
app.indicators.structure). Most bars are not a confirmation bar, so this
module forward-fills "the most recently confirmed swing type" per side
(highs, lows) so every bar has a usable current regime, not just the rare
confirmation bars.

Causality: ffill() only ever propagates a value already seen at an earlier
row forward to later rows - it never reads ahead. This stays fully causal.
"""
from __future__ import annotations

import pandas as pd


def _last_confirmed_type(higher_flags: pd.Series, lower_flags: pd.Series) -> pd.Series:
    event = pd.Series(pd.NA, index=higher_flags.index, dtype="object")
    event = event.mask(higher_flags.fillna(False).astype(bool), "higher")
    event = event.mask(lower_flags.fillna(False).astype(bool), "lower")
    return event.ffill()


def price_structure_regime(
    higher_high: pd.Series, lower_high: pd.Series, higher_low: pd.Series, lower_low: pd.Series
) -> pd.DataFrame:
    """Returns columns ['high_swing_state', 'low_swing_state'], each one of
    'higher' / 'lower' / <NA> (no confirmed swing yet for that side)."""
    return pd.DataFrame(
        {
            "high_swing_state": _last_confirmed_type(higher_high, lower_high),
            "low_swing_state": _last_confirmed_type(higher_low, lower_low),
        }
    )


def price_structure_bullish(regime: pd.DataFrame, require_both: bool = True) -> pd.Series:
    """Classic Dow-theory uptrend: higher highs AND higher lows, by
    default. Pass require_both=False to accept either alone."""
    is_higher_high = regime["high_swing_state"] == "higher"
    is_higher_low = regime["low_swing_state"] == "higher"
    return (is_higher_high & is_higher_low) if require_both else (is_higher_high | is_higher_low)


def price_structure_bearish(regime: pd.DataFrame, require_both: bool = True) -> pd.Series:
    """Classic Dow-theory downtrend: lower highs AND lower lows, by
    default. Pass require_both=False to accept either alone."""
    is_lower_high = regime["high_swing_state"] == "lower"
    is_lower_low = regime["low_swing_state"] == "lower"
    return (is_lower_high & is_lower_low) if require_both else (is_lower_high | is_lower_low)
