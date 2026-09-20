"""
Scans a symbol universe (e.g. the NIFTY 200 from Phase 2's UniverseService,
or any given list), running the per-symbol pipeline plus scoring (Phase 6),
and returns the list of SymbolSnapshot ready for RankingEngine.rank().
This is steps 1-5 of the phase spec end to end - call this again any time
new market data arrives and feed the result to RankingEngine.rank() for
an automatically up-to-date ranking; nothing here is cached.

Symbols that fail to produce data (no candles yet, a data/computation
error) are SKIPPED, not silently scored as 0 - a missing stock should be
absent from the ranking, not falsely ranked last. Failures are recorded
in the returned ScanResult so callers can see what was skipped and why.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import pandas as pd

from app.indicators.engine import IndicatorEngine
from app.market_data.base import IntradayOHLCVProvider
from app.market_data.calendar import NSECalendar
from app.market_data.enums import Timeframe
from app.ranking.engine import SymbolSnapshot
from app.ranking.pipeline import build_symbol_indicators, build_symbol_setup
from app.scoring.engine import OpportunityScoringEngine
from app.setup_detection.engine import SetupDetectionEngine

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    snapshots: List[SymbolSnapshot] = field(default_factory=list)
    skipped: Dict[str, str] = field(default_factory=dict)  # symbol -> reason


def scan_universe(
    symbols: Sequence[str],
    exchange: str,
    provider: IntradayOHLCVProvider,
    calendar: NSECalendar,
    timeframe: Timeframe,
    nifty_symbol: str = "NIFTY 200",
    indicator_engine: Optional[IndicatorEngine] = None,
    setup_engine: Optional[SetupDetectionEngine] = None,
    scoring_engine: Optional[OpportunityScoringEngine] = None,
) -> ScanResult:
    indicator_engine = indicator_engine or IndicatorEngine()
    setup_engine = setup_engine or SetupDetectionEngine()
    scoring_engine = scoring_engine or OpportunityScoringEngine()

    result = ScanResult()

    nifty_indicators_df: Optional[pd.DataFrame] = None
    try:
        nifty_indicators_df = build_symbol_indicators(
            nifty_symbol, exchange, provider, calendar, timeframe, indicator_engine
        )
    except Exception:
        logger.exception("Failed to fetch/compute NIFTY data - continuing without it")

    if nifty_indicators_df is None:
        logger.warning("No NIFTY data available - Market Confirmation and Relative Strength will be omitted")

    nifty_close_df: Optional[pd.DataFrame] = None
    if nifty_indicators_df is not None:
        nifty_close_df = pd.DataFrame(
            {"timestamp": nifty_indicators_df["timestamp"], "close": nifty_indicators_df["close"]}
        )

    for symbol in symbols:
        try:
            indicators_df = build_symbol_indicators(
                symbol, exchange, provider, calendar, timeframe, indicator_engine, nifty_close_df
            )
            if indicators_df is None or indicators_df.empty:
                result.skipped[symbol] = "no data available"
                continue

            setup_df = build_symbol_setup(indicators_df, nifty_indicators_df, setup_engine)
            scoring_df = scoring_engine.compute(indicators_df, setup_df, nifty_indicators_df=nifty_indicators_df)

            result.snapshots.append(
                SymbolSnapshot(
                    symbol=symbol,
                    indicators_row=indicators_df.iloc[-1],
                    setup_row=setup_df.iloc[-1],
                    scoring_row=scoring_df.iloc[-1],
                )
            )
        except Exception as exc:  # noqa: BLE001 - one bad symbol must not kill the whole scan
            logger.exception("Failed to process %s", symbol)
            result.skipped[symbol] = f"{type(exc).__name__}: {exc}"

    return result
