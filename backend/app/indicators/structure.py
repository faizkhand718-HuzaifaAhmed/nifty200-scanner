"""
Higher High / Higher Low / Lower High / Lower Low market structure.

This requires detecting SWING points first (a bar whose high/low is more
extreme than the `n` bars on either side of it) - and a swing point is,
by definition, only confirmable once `n` bars AFTER it have occurred. This
module makes that lag explicit rather than hiding it: a swing at bar i is
stamped at row i+n (the first row where it's actually knowable), not at
row i itself. Reading row i's own flag would be look-ahead; reading row
i+n's flag (which says "we now know bar i was a swing") is not.

Default n=2 (a standard "2-bar fractal") - adjustable, and worth
confirming this matches your intended swing sensitivity.
"""
from __future__ import annotations

import pandas as pd


def swing_points(high: pd.Series, low: pd.Series, n: int = 2) -> pd.DataFrame:
    """
    Returns columns: swing_high_confirmed, swing_high_price,
    swing_low_confirmed, swing_low_price - each indexed like `high`/`low`,
    with the "confirmed" flags/prices stamped at the CONFIRMATION row
    (i + n), not the original swing bar's own row.
    """
    if n <= 0:
        raise ValueError("n must be positive")

    length = len(high)
    swing_high_confirmed = pd.Series(False, index=high.index)
    swing_high_price = pd.Series(float("nan"), index=high.index)
    swing_low_confirmed = pd.Series(False, index=high.index)
    swing_low_price = pd.Series(float("nan"), index=high.index)

    high_vals = high.to_numpy()
    low_vals = low.to_numpy()

    for i in range(n, length - n):
        before_high_max = high_vals[i - n : i].max()
        after_high_max = high_vals[i + 1 : i + n + 1].max()
        if high_vals[i] > before_high_max and high_vals[i] > after_high_max:
            confirm_at = i + n
            swing_high_confirmed.iloc[confirm_at] = True
            swing_high_price.iloc[confirm_at] = high_vals[i]

        before_low_min = low_vals[i - n : i].min()
        after_low_min = low_vals[i + 1 : i + n + 1].min()
        if low_vals[i] < before_low_min and low_vals[i] < after_low_min:
            confirm_at = i + n
            swing_low_confirmed.iloc[confirm_at] = True
            swing_low_price.iloc[confirm_at] = low_vals[i]

    return pd.DataFrame(
        {
            "swing_high_confirmed": swing_high_confirmed,
            "swing_high_price": swing_high_price,
            "swing_low_confirmed": swing_low_confirmed,
            "swing_low_price": swing_low_price,
        }
    )


def classify_structure(swings: pd.DataFrame) -> pd.DataFrame:
    """
    Given the output of swing_points(), compares each newly-confirmed
    swing to the PREVIOUS confirmed swing of the same type (high-to-high,
    low-to-low) to flag Higher High / Lower High / Higher Low / Lower Low.
    The first swing of each type has nothing to compare against, so it
    gets no flag (neither True) - not a fabricated classification.
    """
    index = swings.index
    higher_high = pd.Series(False, index=index)
    lower_high = pd.Series(False, index=index)
    higher_low = pd.Series(False, index=index)
    lower_low = pd.Series(False, index=index)

    prev_swing_high = None
    prev_swing_low = None
    for idx in index:
        if bool(swings.at[idx, "swing_high_confirmed"]):
            price = swings.at[idx, "swing_high_price"]
            if prev_swing_high is not None:
                if price > prev_swing_high:
                    higher_high.at[idx] = True
                elif price < prev_swing_high:
                    lower_high.at[idx] = True
            prev_swing_high = price

        if bool(swings.at[idx, "swing_low_confirmed"]):
            price = swings.at[idx, "swing_low_price"]
            if prev_swing_low is not None:
                if price > prev_swing_low:
                    higher_low.at[idx] = True
                elif price < prev_swing_low:
                    lower_low.at[idx] = True
            prev_swing_low = price

    return pd.DataFrame(
        {"higher_high": higher_high, "lower_high": lower_high, "higher_low": higher_low, "lower_low": lower_low}
    )


def market_structure(high: pd.Series, low: pd.Series, n: int = 2) -> pd.DataFrame:
    """Convenience wrapper combining swing_points() + classify_structure()
    into one DataFrame with all 8 columns."""
    swings = swing_points(high, low, n)
    structure = classify_structure(swings)
    return pd.concat([swings, structure], axis=1)
