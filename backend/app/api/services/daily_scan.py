"""
Daily-timeframe scan service for the NSE MCP data path. This is
deliberately informational only - it produces price/indicator/score data
for display, never a stop-loss, target, or entry price. Nothing in this
module touches app.entry_engine, app.risk_management, or app.brokers -
there is no automated trading or order execution anywhere in this path,
per the explicit scope for this integration.

Reuses IndicatorEngine (Phase 4) unmodified - EMA/RSI/etc. math is
timeframe-agnostic. Adds only the daily-specific pieces that were never
part of Phase 4's intraday-oriented indicator set (52-week high/low,
period returns, daily relative volume - see
app/indicators/daily_extras.py) and the Technical Setup Score itself (see
app/scoring/technical_setup_score.py's module docstring for why that's
new code rather than a reuse of Phase 6's intraday-tuned engine).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, List, Optional

import pandas as pd

from app.indicators.daily_extras import daily_relative_volume, fifty_two_week_high_low, period_return_pct
from app.indicators.engine import IndicatorEngine
from app.market_data.enums import Timeframe
from app.market_data.exceptions import MarketDataError
from app.scoring.technical_setup_score import TechnicalSetupScoreConfig, TechnicalSetupResult, compute_technical_setup_score

if TYPE_CHECKING:
    from app.market_data.schemas import Candle

LOOKBACK_TRADING_DAYS = 260


@dataclass
class DailyScanRow:
    symbol: str
    price: float
    change_pct: Optional[float]
    volume: int
    ema_20: Optional[float]
    ema_50: Optional[float]
    ema_200: Optional[float]
    rsi: Optional[float]
    relative_volume: Optional[float]
    return_20d_pct: Optional[float]
    pct_from_52w_high: Optional[float]
    pct_from_52w_low: Optional[float]
    setup_score: TechnicalSetupResult
    as_of: date
    error: Optional[str] = None


def _candles_to_frame(candles: List[Candle]) -> pd.DataFrame:
    rows = [{"timestamp": c.timestamp, "open": c.open, "high": c.high, "low": c.low, "close": c.close, "volume": c.volume} for c in candles]
    return pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)


def compute_daily_scan_row(
    symbol: str,
    provider,
    exchange: str = "NSE",
    nifty_frame: Optional[pd.DataFrame] = None,
    config: Optional[TechnicalSetupScoreConfig] = None,
) -> DailyScanRow:
    """`nifty_frame` (already-fetched NIFTY daily indicator DataFrame) is
    passed in rather than fetched here, so the caller fetches it ONCE per
    scan rather than once per symbol - avoiding 200 redundant NSE MCP
    calls for the same index data."""
    end = date.today()
    start = end - timedelta(days=int(LOOKBACK_TRADING_DAYS * 1.6) + 10)

    try:
        candles = provider.get_historical_candles(symbol, exchange, Timeframe.DAY, start, end)
    except MarketDataError as exc:
        empty_score = compute_technical_setup_score(0, None, None, None, None, None, None, None, None, None, config)
        return DailyScanRow(
            symbol=symbol, price=0.0, change_pct=None, volume=0, ema_20=None, ema_50=None, ema_200=None,
            rsi=None, relative_volume=None, return_20d_pct=None, pct_from_52w_high=None, pct_from_52w_low=None,
            setup_score=empty_score, as_of=end, error=str(exc),
        )

    if not candles:
        raise MarketDataError(f"no historical candles returned for {symbol}")

    df = _candles_to_frame(candles)
    indicators = IndicatorEngine().compute(df)

    fifty_two = fifty_two_week_high_low(indicators["close"], indicators["high"], indicators["low"])
    indicators = pd.concat([indicators, fifty_two], axis=1)
    indicators["return_20d_pct"] = period_return_pct(indicators["close"], periods=20)
    indicators["relative_volume_daily"] = daily_relative_volume(indicators["volume"], window=20)

    last = indicators.iloc[-1]
    prev = indicators.iloc[-2] if len(indicators) >= 2 else None
    change_pct = ((last["close"] - prev["close"]) / prev["close"] * 100) if prev is not None else None

    nifty_return_20d = None
    if nifty_frame is not None and "return_20d_pct" in nifty_frame.columns and not nifty_frame.empty:
        nifty_val = nifty_frame.iloc[-1].get("return_20d_pct")
        nifty_return_20d = float(nifty_val) if nifty_val == nifty_val else None

    def _val(x):
        return float(x) if x is not None and x == x else None

    # EMA warm-up gating: pandas' .ewm() (which IndicatorEngine uses,
    # consistently, project-wide) produces A number even with very few
    # bars - mathematically valid, but not what "20/50/200-day moving
    # average" means if there genuinely aren't 20/50/200 days of history
    # yet. Gated HERE, in this reporting layer, rather than changing
    # IndicatorEngine's own EMA behavior (which is used the same way
    # everywhere else in this project and shouldn't change for one
    # caller). "Insufficient data" per the user's explicit instruction,
    # not a number computed on too little history.
    bars_available = len(indicators)
    ema_20 = _val(last.get("ema_20")) if bars_available >= 20 else None
    ema_50 = _val(last.get("ema_50")) if bars_available >= 50 else None
    ema_200 = _val(last.get("ema_200")) if bars_available >= 200 else None

    setup_score = compute_technical_setup_score(
        close=float(last["close"]),
        ema_20=ema_20, ema_50=ema_50, ema_200=ema_200,
        rsi=_val(last.get("rsi")), daily_relative_volume=_val(last.get("relative_volume_daily")),
        return_20d_pct=_val(last.get("return_20d_pct")),
        stock_return_pct_for_relative_strength=_val(last.get("return_20d_pct")),
        nifty_return_pct_for_relative_strength=nifty_return_20d,
        pct_from_52w_high=_val(last.get("pct_from_52w_high")),
        config=config,
    )

    return DailyScanRow(
        symbol=symbol, price=float(last["close"]), change_pct=change_pct, volume=int(last["volume"]),
        ema_20=ema_20, ema_50=ema_50, ema_200=ema_200,
        rsi=_val(last.get("rsi")), relative_volume=_val(last.get("relative_volume_daily")),
        return_20d_pct=_val(last.get("return_20d_pct")),
        pct_from_52w_high=_val(last.get("pct_from_52w_high")), pct_from_52w_low=_val(last.get("pct_from_52w_low")),
        setup_score=setup_score, as_of=last["timestamp"].date() if hasattr(last["timestamp"], "date") else end,
    )


def build_nifty_daily_frame(provider, index_symbol: str = "NIFTY 50", exchange: str = "NSE") -> Optional[pd.DataFrame]:
    """Fetched ONCE per scan for relative-strength comparison. Returns
    None (never fabricated) if NIFTY history can't be fetched - every
    row's relative_strength category then reports "insufficient data"
    rather than guessing."""
    end = date.today()
    start = end - timedelta(days=int(LOOKBACK_TRADING_DAYS * 1.6) + 10)
    try:
        candles = provider.get_historical_candles(index_symbol, exchange, Timeframe.DAY, start, end)
    except MarketDataError:
        return None
    if not candles:
        return None
    df = _candles_to_frame(candles)
    df["return_20d_pct"] = period_return_pct(df["close"], periods=20)
    return df
