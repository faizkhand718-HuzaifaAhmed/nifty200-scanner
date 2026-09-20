"""
Per-symbol pipeline: fetch -> clean -> indicators -> setup, for ONE
symbol. This is steps 2-4 of the phase spec for a single stock; see
scanner.py for looping this across the whole universe (step 1) and
adding scoring (step 5).
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from app.indicators.adapters import candles_to_dataframe
from app.indicators.engine import IndicatorEngine
from app.market_data.base import IntradayOHLCVProvider
from app.market_data.calendar import NSECalendar
from app.market_data.enums import Timeframe
from app.market_data.validation import validate_and_clean
from app.setup_detection.engine import SetupDetectionEngine


def build_symbol_indicators(
    symbol: str,
    exchange: str,
    provider: IntradayOHLCVProvider,
    calendar: NSECalendar,
    timeframe: Timeframe,
    indicator_engine: IndicatorEngine,
    nifty_close_df: Optional[pd.DataFrame] = None,
) -> Optional[pd.DataFrame]:
    """
    Fetches today's intraday candles for `symbol`, cleans them (duplicate/
    gap/out-of-session/misalignment handling from Phase 3 - never
    fabricating missing data), and returns the full IndicatorEngine
    output. Returns None if there isn't enough data yet (e.g. before
    market open, or a data error) - a symbol with no data should be
    skipped, not scored as if it had zero of everything.
    """
    candles = provider.get_intraday_candles(symbol, exchange, timeframe)
    if not candles:
        return None
    cleaned, _report = validate_and_clean(candles, timeframe, calendar)
    df = candles_to_dataframe(cleaned, include_incomplete=False)
    if df.empty:
        return None
    return indicator_engine.compute(df, nifty_df=nifty_close_df)


def build_symbol_setup(
    indicators_df: pd.DataFrame,
    nifty_indicators_df: Optional[pd.DataFrame],
    setup_engine: SetupDetectionEngine,
) -> pd.DataFrame:
    return setup_engine.compute(indicators_df, nifty_df=nifty_indicators_df)
