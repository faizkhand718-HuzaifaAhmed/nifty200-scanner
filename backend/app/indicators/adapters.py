"""
Bridges Phase 3's Candle objects into the plain pandas DataFrame contract
IndicatorEngine expects, so the indicators module has no import dependency
on the market_data module (and could be reused against any OHLCV source
that can be shaped into this DataFrame contract).
"""
from __future__ import annotations

from typing import List

import pandas as pd

from app.market_data.schemas import Candle


def candles_to_dataframe(candles: List[Candle], include_incomplete: bool = False) -> pd.DataFrame:
    """
    Converts Candle objects (ideally already run through
    app.market_data.validation.validate_and_clean) into a DataFrame with
    columns [timestamp, open, high, low, close, volume], sorted ascending.

    By default the currently-forming candle (is_complete=False) is
    EXCLUDED. Computing indicators as if a partial bar were final is a form
    of look-ahead risk - you'd be reacting to a price/volume that hasn't
    actually finished forming yet. Pass include_incomplete=True only if you
    explicitly want a live, still-moving snapshot and understand the last
    row is provisional and will change on the next call.
    """
    rows = [c for c in candles if include_incomplete or c.is_complete]
    rows.sort(key=lambda c: c.timestamp)
    return pd.DataFrame(
        {
            "timestamp": [c.timestamp for c in rows],
            "open": [c.open for c in rows],
            "high": [c.high for c in rows],
            "low": [c.low for c in rows],
            "close": [c.close for c in rows],
            "volume": [c.volume for c in rows],
        }
    )
