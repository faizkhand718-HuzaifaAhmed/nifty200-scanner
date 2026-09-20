"""
Shared per-symbol analysis glue, used by both routes/stocks.py and
routes/options.py so the "fetch indicators, setup, score, then rank one
symbol" sequence exists in exactly one place at the API layer. Still no
engine logic here - this only sequences calls to
app.ranking.pipeline/app.ranking.engine/app.scoring.engine exactly as
app.ranking.scanner.scan_universe does for a whole universe, just for
one symbol.
"""
from __future__ import annotations

from typing import Optional, Tuple

import pandas as pd
from fastapi import HTTPException

from app.api import state
from app.indicators.engine import IndicatorEngine
from app.market_data.enums import Timeframe
from app.ranking.engine import RankingEngine, SymbolSnapshot
from app.ranking.pipeline import build_symbol_indicators, build_symbol_setup
from app.scoring.engine import OpportunityScoringEngine
from app.setup_detection.engine import SetupDetectionEngine


def analyze_symbol(symbol: str) -> Tuple[pd.Series, pd.Series]:
    """Returns (ranked_row, scoring_row) for one symbol - the same rows
    RankingEngine/OpportunityScoringEngine already produce, just isolated
    to a single symbol rather than a whole universe scan. Raises
    HTTPException (502/404) on failure, so route handlers can call this
    directly without repeating error handling."""
    provider = state.get_market_data_provider()
    calendar = state.get_calendar()
    indicator_engine = IndicatorEngine()

    nifty_indicators_df: Optional[pd.DataFrame] = None
    try:
        nifty_indicators_df = build_symbol_indicators(
            "NIFTY 200", "NSE", provider, calendar, Timeframe.FIFTEEN_MIN, indicator_engine
        )
    except Exception:
        pass  # Market Confirmation/Relative Strength omitted, same graceful degradation as scan_universe

    try:
        indicators_df = build_symbol_indicators(
            symbol, "NSE", provider, calendar, Timeframe.FIFTEEN_MIN, indicator_engine, nifty_indicators_df
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"could not fetch market data for {symbol}: {exc}")

    if indicators_df is None or indicators_df.empty:
        raise HTTPException(status_code=404, detail=f"no data available for {symbol}")

    setup_df = build_symbol_setup(indicators_df, nifty_indicators_df, SetupDetectionEngine())
    scoring_df = OpportunityScoringEngine().compute(indicators_df, setup_df, nifty_indicators_df=nifty_indicators_df)

    snapshot = SymbolSnapshot(
        symbol=symbol, indicators_row=indicators_df.iloc[-1], setup_row=setup_df.iloc[-1], scoring_row=scoring_df.iloc[-1],
    )
    ranked_df = RankingEngine().rank([snapshot])
    if ranked_df.empty:
        raise HTTPException(status_code=404, detail=f"could not rank {symbol}")

    return ranked_df.iloc[0], scoring_df.iloc[-1]
