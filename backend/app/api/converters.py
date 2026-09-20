"""
Converts already-computed engine output into API schema objects. NOTHING
here computes a score, a signal, or a trade decision - every value comes
from a DataFrame row or dataclass an existing, tested engine already
produced. This is the "wrap, don't rewrite" boundary made concrete.
"""
from __future__ import annotations

from typing import Any, List, Optional

import pandas as pd

from app.api.schemas import (
    AlertOut,
    BacktestReportOut,
    CategoryBreakdownOut,
    InstrumentOut,
    OptionsAnalysisResponseOut,
    PaperPositionOut,
    PaperTradingSummaryOut,
    RankedStockOut,
    TradeOut,
)


def ranked_row_to_schema(row: "pd.Series") -> RankedStockOut:
    return RankedStockOut(
        rank=int(row["rank"]),
        symbol=row["symbol"],
        price=float(row["price"]),
        change_pct=_optional_float(row.get("change_pct")),
        volume=float(row.get("volume", 0.0) or 0.0),
        relative_volume=float(row.get("relative_volume", 0.0) or 0.0),
        vwap=float(row.get("vwap", 0.0) or 0.0),
        rsi=_optional_float(row.get("rsi")),
        adx=_optional_float(row.get("adx")),
        trend=str(row.get("trend", "")),
        direction=row["direction"],
        opportunity_score=float(row["opportunity_score"]),
        entry_status=row["entry_status"],
        entry_price=float(row["entry_price"]),
        stop_loss=_optional_float(row.get("stop_loss")),
        target=_optional_float(row.get("target")),
        risk_reward=_optional_float(row.get("risk_reward")),
        setup_explanation=str(row.get("setup_explanation", "")),
    )


def _optional_float(value: Any) -> Optional[float]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return float(value)


def score_breakdown_to_schema(scoring_row: "pd.Series", side: str) -> List[CategoryBreakdownOut]:
    """Builds the category breakdown directly from the scoring row's own
    per-category columns ({side}_{key}_score / {side}_{key}_max) - the
    same columns app.scoring.explanation.generate_explanation() reads,
    not a separate structure. There is no dedicated "breakdown dict"
    function in the scoring engine; this converter reads the real
    columns rather than assuming one exists."""
    from app.scoring.explanation import CATEGORY_LABELS

    out = []
    for key, label in CATEGORY_LABELS.items():
        score_col, max_col = f"{side}_{key}_score", f"{side}_{key}_max"
        if score_col not in scoring_row or max_col not in scoring_row:
            continue
        score = _optional_float(scoring_row[score_col]) or 0.0
        max_score = _optional_float(scoring_row[max_col]) or 0.0
        out.append(CategoryBreakdownOut(category=label, score=score, max_score=max_score, explanation=""))
    return out


def instrument_to_schema(instrument: Any) -> InstrumentOut:
    return InstrumentOut(
        symbol=instrument.symbol, exchange=instrument.exchange,
        company_name=instrument.company_name, sector=instrument.sector,
    )


def trade_record_to_schema(trade: Any) -> TradeOut:
    return TradeOut(
        symbol=trade.symbol, direction=trade.direction,
        entry_time=trade.entry_time, entry_price=trade.entry_price_filled,
        exit_time=trade.exit_time, exit_price=trade.exit_price_filled,
        exit_reason=trade.exit_reason, net_pnl=trade.net_pnl, r_multiple=trade.r_multiple,
    )


def backtest_report_to_schema(report: Any) -> BacktestReportOut:
    return BacktestReportOut(
        total_trades=report.total_trades, winning_trades=report.winning_trades,
        losing_trades=report.losing_trades, win_rate=report.win_rate,
        profit_factor=report.profit_factor, max_drawdown=report.max_drawdown,
        average_r=report.average_r, expectancy=report.expectancy, total_pnl=report.total_pnl,
    )


def paper_position_to_schema(position: Any) -> PaperPositionOut:
    return PaperPositionOut(
        id=position.id, symbol=position.symbol, direction=position.direction,
        entry_price=position.entry_price, quantity=position.quantity,
        stop_loss=position.stop_loss, target=position.target, entry_time=position.entry_time,
        opportunity_score_at_entry=position.opportunity_score_at_entry,
        market_condition=position.market_condition, reason_for_entry=position.reason_for_entry,
        exit_time=position.exit_time, exit_price=position.exit_price, exit_reason=position.exit_reason,
        pnl=position.pnl, pnl_pct=position.pnl_pct, r_multiple=position.r_multiple,
    )


def paper_summary_to_schema(summary: Any) -> PaperTradingSummaryOut:
    return PaperTradingSummaryOut(
        open_positions_count=summary.open_positions_count, closed_positions_count=summary.closed_positions_count,
        todays_pnl=summary.todays_pnl, win_rate=summary.win_rate,
        average_r=summary.average_r, max_drawdown=summary.max_drawdown,
    )


def alert_to_schema(alert: Any) -> AlertOut:
    return AlertOut(
        id=f"{alert.symbol}-{alert.alert_type.value}-{alert.candle_timestamp.isoformat()}",
        symbol=alert.symbol, alert_type=alert.alert_type.value, direction=alert.direction,
        message=alert.message, fired_at=alert.fired_at,
    )


def options_result_to_schema(result: Any) -> OptionsAnalysisResponseOut:
    return OptionsAnalysisResponseOut(
        underlying_symbol=result.underlying_symbol, underlying_direction=result.underlying_direction,
        underlying_opportunity_score=result.underlying_opportunity_score, option_type=result.option_type,
        expiry=result.expiry, strike=result.strike, premium=result.premium, volume=result.volume,
        open_interest=result.open_interest, change_in_open_interest=result.change_in_open_interest,
        implied_volatility=result.implied_volatility, bid=result.bid, ask=result.ask,
        spread_pct=result.spread_pct, liquidity=(result.liquidity.value if result.liquidity else None),
        risk_reward=result.risk_reward, selection_note=result.selection_note,
    )


def technical_setup_result_to_schema(result: Any):
    from app.api.schemas import CategoryScoreOut, TechnicalSetupScoreOut

    return TechnicalSetupScoreOut(
        total_score=result.total_score,
        categories=[
            CategoryScoreOut(name=c.name, available=c.available, score=c.score, max_score=c.max_score, explanation=c.explanation)
            for c in result.categories
        ],
        unavailable_categories=result.unavailable_categories,
    )


def daily_scan_row_to_schema(row: Any):
    from app.api.schemas import DailyScanRowOut

    return DailyScanRowOut(
        symbol=row.symbol, price=row.price, change_pct=row.change_pct, volume=row.volume,
        ema_20=row.ema_20, ema_50=row.ema_50, ema_200=row.ema_200, rsi=row.rsi,
        relative_volume=row.relative_volume, return_20d_pct=row.return_20d_pct,
        pct_from_52w_high=row.pct_from_52w_high, pct_from_52w_low=row.pct_from_52w_low,
        setup_score=technical_setup_result_to_schema(row.setup_score), as_of=row.as_of, error=row.error,
    )
