"""
Historical data pipeline: fetch -> clean -> indicators -> setup -> score,
for a DATE RANGE (as opposed to Phase 7's scanner.py, which does the same
thing for "today so far"). This realizes the "Date range, Stock, NIFTY
200, Timeframe" inputs from the phase spec as an actual function call,
reusing Phase 3's HistoricalOHLCVProvider, Phase 4's IndicatorEngine,
Phase 5's SetupDetectionEngine, and Phase 6's OpportunityScoringEngine
exactly as they already exist - no new indicator/setup/scoring math here.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

from app.indicators.adapters import candles_to_dataframe
from app.indicators.engine import IndicatorEngine
from app.market_data.base import HistoricalOHLCVProvider
from app.market_data.calendar import NSECalendar
from app.market_data.enums import Timeframe
from app.market_data.validation import validate_and_clean
from app.scoring.engine import OpportunityScoringEngine
from app.setup_detection.engine import SetupDetectionEngine


def build_historical_indicators(
    symbol: str,
    exchange: str,
    provider: HistoricalOHLCVProvider,
    calendar: NSECalendar,
    timeframe: Timeframe,
    start: date,
    end: date,
    indicator_engine: IndicatorEngine,
    nifty_close_df: Optional[pd.DataFrame] = None,
) -> Optional[pd.DataFrame]:
    """Fetches and cleans historical candles for `symbol` over
    [start, end], then runs the full IndicatorEngine. Returns None if no
    data is available (never fabricated)."""
    candles = provider.get_historical_candles(symbol, exchange, timeframe, start, end)
    if not candles:
        return None
    cleaned, _report = validate_and_clean(candles, timeframe, calendar)
    df = candles_to_dataframe(cleaned, include_incomplete=False)
    if df.empty:
        return None
    return indicator_engine.compute(df, nifty_df=nifty_close_df)


def build_backtest_dataset(
    symbols: Sequence[str],
    exchange: str,
    provider: HistoricalOHLCVProvider,
    calendar: NSECalendar,
    timeframe: Timeframe,
    start: date,
    end: date,
    nifty_symbol: str = "NIFTY 200",
    indicator_engine: Optional[IndicatorEngine] = None,
    setup_engine: Optional[SetupDetectionEngine] = None,
    scoring_engine: Optional[OpportunityScoringEngine] = None,
) -> Tuple[Dict[str, Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]], List[str]]:
    """
    Builds the (indicators_df, setup_df, scoring_df) tuple for every
    symbol in `symbols` - pass the full NIFTY 200 universe list to
    realize the "NIFTY 200" backtest option, or a single-element list for
    a single-stock backtest. Returns (dataset, skipped_symbols) - a
    symbol with no data available is skipped, not silently zero-filled.
    """
    indicator_engine = indicator_engine or IndicatorEngine()
    setup_engine = setup_engine or SetupDetectionEngine()
    scoring_engine = scoring_engine or OpportunityScoringEngine()

    nifty_indicators_df = build_historical_indicators(
        nifty_symbol, exchange, provider, calendar, timeframe, start, end, indicator_engine
    )
    nifty_close_df = None
    if nifty_indicators_df is not None:
        nifty_close_df = pd.DataFrame({"timestamp": nifty_indicators_df["timestamp"], "close": nifty_indicators_df["close"]})

    dataset: Dict[str, Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]] = {}
    skipped: List[str] = []

    for symbol in symbols:
        indicators_df = build_historical_indicators(
            symbol, exchange, provider, calendar, timeframe, start, end, indicator_engine, nifty_close_df
        )
        if indicators_df is None or indicators_df.empty:
            skipped.append(symbol)
            continue
        setup_df = setup_engine.compute(indicators_df, nifty_df=nifty_indicators_df)
        scoring_df = scoring_engine.compute(indicators_df, setup_df, nifty_indicators_df=nifty_indicators_df)
        dataset[symbol] = (indicators_df, setup_df, scoring_df)

    return dataset, skipped
