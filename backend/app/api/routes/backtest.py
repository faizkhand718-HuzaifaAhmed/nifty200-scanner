"""
POST /api/backtest/run - wraps app.backtesting.historical_pipeline's
build_backtest_dataset() and app.backtesting.engine.run_universe()
directly. No backtest math is reimplemented here.

Runs SYNCHRONOUSLY within the request for v1 - no background job queue
exists yet. Fine for the symbol counts/date ranges this system has
actually been tested with; if a real deployment needs long-running
backtests, that's a background-job phase of its own, not a quick patch
here.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException

from app.api import state
from app.api.converters import backtest_report_to_schema, trade_record_to_schema
from app.api.schemas import BacktestRunRequest, BacktestRunResponse
from app.backtesting.config import BacktestConfig
from app.backtesting.engine import run_universe
from app.backtesting.historical_pipeline import build_backtest_dataset
from app.entry_engine.config import EntryEngineConfig, EntryMethod, StopMethod, TargetMethod
from app.market_data.enums import Timeframe

router = APIRouter(prefix="/api/backtest", tags=["backtest"])

_TIMEFRAME_MAP = {tf.value: tf for tf in Timeframe}


@router.post("/run", response_model=BacktestRunResponse)
def run_backtest(request: BacktestRunRequest):
    if not request.symbols:
        raise HTTPException(status_code=422, detail="symbols must not be empty")
    timeframe = _TIMEFRAME_MAP.get(request.timeframe)
    if timeframe is None:
        raise HTTPException(status_code=422, detail=f"unknown timeframe: {request.timeframe!r}")

    end = date.today()
    start = end - timedelta(days=request.lookback_days)

    dataset, skipped = build_backtest_dataset(
        symbols=request.symbols, exchange="NSE", provider=state.get_market_data_provider(),
        calendar=state.get_calendar(), timeframe=timeframe, start=start, end=end,
    )
    if not dataset:
        raise HTTPException(status_code=404, detail=f"no historical data available for any requested symbol (skipped: {skipped})")

    config = BacktestConfig(
        direction=request.direction,
        entry_config=EntryEngineConfig(
            entry_method=EntryMethod.BREAKOUT, stop_method=StopMethod.SUPPORT_RESISTANCE, target_method=TargetMethod.RISK_REWARD_2
        ),
        min_score=request.min_score,
        starting_capital=request.starting_capital,
        risk_per_trade_pct=request.risk_per_trade_pct,
    )
    trades, open_trades, report = run_universe(dataset, config)

    return BacktestRunResponse(
        report=backtest_report_to_schema(report),
        trades=[trade_record_to_schema(t) for t in trades],
        open_positions=[trade_record_to_schema(t) for t in open_trades],
    )
