"""
Pure edge-detection functions. Every alert here fires on a TRANSITION
(prev value/state -> curr value/state), never on a level being merely
"true this bar" - that's what keeps a score sitting at 85 from alerting
every single bar, and what keeps a terminal lifecycle state (STOP_LOSS_HIT
etc.) from re-alerting on every bar it persists afterward.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd


def score_crosses(prev_score: Optional[float], curr_score: Optional[float], threshold: float) -> bool:
    if prev_score is None or curr_score is None or pd.isna(prev_score) or pd.isna(curr_score):
        return False
    return prev_score < threshold <= curr_score


def direction_becomes(prev_direction: Optional[str], curr_direction: Optional[str], target: str) -> bool:
    return curr_direction == target and prev_direction != target


def state_becomes(prev_state: Optional[str], curr_state: Optional[str], target: str) -> bool:
    return curr_state == target and prev_state != target
