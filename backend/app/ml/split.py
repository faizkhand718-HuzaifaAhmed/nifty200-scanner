"""
Chronological train/validation/test split. NEVER shuffles - a random
shuffle of time-series trade examples would leak future information into
training via autocorrelated samples (nearby-in-time trades share overlapping
indicator history). Train is strictly earliest, validation strictly after
train, test strictly after validation.
"""
from __future__ import annotations

from typing import List, Tuple, TypeVar

from app.ml.labels import TrainingExample

T = TypeVar("T", bound=TrainingExample)


def chronological_split(
    examples: List[T], train_frac: float = 0.6, val_frac: float = 0.2
) -> Tuple[List[T], List[T], List[T]]:
    if not (0 < train_frac < 1) or not (0 < val_frac < 1) or train_frac + val_frac >= 1:
        raise ValueError("train_frac and val_frac must be positive and sum to less than 1")

    ordered = sorted(examples, key=lambda ex: ex.entry_time)
    n = len(ordered)
    train_end = int(n * train_frac)
    val_end = train_end + int(n * val_frac)

    return ordered[:train_end], ordered[train_end:val_end], ordered[val_end:]
