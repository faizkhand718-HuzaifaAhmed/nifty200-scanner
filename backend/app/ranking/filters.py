"""
Filters and top-N selection applied AFTER ranking (see engine.py). Kept
separate from ranking logic so either can change independently.

Note on "Volume > X": the table's displayed "Volume" column is the
Volume CATEGORY SCORE from Phase 6 (a string like "11.2/15"), which isn't
meaningfully comparable across stocks with a numeric ">" filter. This
filter instead operates on `relative_volume` (current volume as a
multiple of trailing average) - a normalized, cross-sectionally
comparable number. Flagging this interpretation explicitly since "Volume"
is used two different ways in this phase (a display score vs. a filter
metric).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class RankingFilters:
    direction: Optional[str] = None              # "LONG" or "SHORT"
    entry_status: Optional[str] = None            # "WATCH" or "READY"
    min_score: Optional[float] = None             # Score > X
    min_risk_reward: Optional[float] = None       # R:R > X
    min_relative_volume: Optional[float] = None   # Volume > X (relative-volume multiple)


def apply_filters(df: pd.DataFrame, filters: RankingFilters) -> pd.DataFrame:
    if df.empty:
        return df

    mask = pd.Series(True, index=df.index)
    if filters.direction is not None:
        mask &= df["direction"] == filters.direction.upper()
    if filters.entry_status is not None:
        mask &= df["entry_status"] == filters.entry_status.upper()
    if filters.min_score is not None:
        mask &= df["opportunity_score"] > filters.min_score
    if filters.min_risk_reward is not None:
        mask &= df["risk_reward"].fillna(-float("inf")) > filters.min_risk_reward
    if filters.min_relative_volume is not None:
        mask &= df["relative_volume"].fillna(-float("inf")) > filters.min_relative_volume

    filtered = df[mask].reset_index(drop=True)
    if not filtered.empty:
        filtered["rank"] = range(1, len(filtered) + 1)  # re-rank after filtering
    return filtered


def top_n(df: pd.DataFrame, n: Optional[int]) -> pd.DataFrame:
    """n=None (or omitted) returns the full ranked set (up to 200)."""
    if n is None:
        return df
    if n <= 0:
        raise ValueError("n must be positive")
    return df.iloc[:n].reset_index(drop=True)
