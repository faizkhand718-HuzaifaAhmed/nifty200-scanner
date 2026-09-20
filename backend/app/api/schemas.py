"""
API request/response schemas. These are DELIBERATELY SEPARATE from every
engine's internal dataclasses (RankedStock is not RankingEngine's output
row; OptionAnalysisResult stays internal; etc.) - the API's shape is a
contract with the frontend, and keeping it distinct means an internal
engine refactor never silently breaks the API, and vice versa.

Field names use camelCase (via Pydantic aliases) to match
frontend/lib/types.ts exactly, field for field - this was a deliberate
choice to minimize Step 4's frontend rewiring: swapping a mock function
for a real fetch() should require changing as little else as possible.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Direction = Literal["LONG", "SHORT", "NONE"]
TradeDirection = Literal["LONG", "SHORT"]  # for anything that actually opens/closes a position - "NONE" is never valid there
EntryStatus = Literal["READY", "WATCH", "NONE"]


class CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


# --- Universe ---


class InstrumentOut(CamelModel):
    symbol: str
    exchange: str
    company_name: str = Field(alias="companyName")
    sector: Optional[str] = None


# --- Rankings / stock detail ---


class RankedStockOut(CamelModel):
    rank: int
    symbol: str
    exchange: str = "NSE"
    price: float
    change_pct: Optional[float] = Field(None, alias="changePct")
    volume: float
    relative_volume: float = Field(alias="relativeVolume")
    vwap: float
    rsi: Optional[float] = None
    adx: Optional[float] = None
    trend: str
    direction: Direction
    opportunity_score: float = Field(alias="opportunityScore")
    entry_status: EntryStatus = Field(alias="entryStatus")
    entry_price: float = Field(alias="entryPrice")
    stop_loss: Optional[float] = Field(None, alias="stopLoss")
    target: Optional[float] = None
    risk_reward: Optional[float] = Field(None, alias="riskReward")
    setup_explanation: str = Field(alias="setupExplanation")


class RankingsResponse(CamelModel):
    generated_at: datetime = Field(alias="generatedAt")
    skipped_symbols: dict = Field(default_factory=dict, alias="skippedSymbols")
    stocks: List[RankedStockOut]


class CategoryBreakdownOut(CamelModel):
    category: str
    score: float
    max_score: float = Field(alias="maxScore")
    explanation: str


class StockDetailResponse(CamelModel):
    stock: RankedStockOut
    breakdown: List[CategoryBreakdownOut]


# --- Backtest ---


class BacktestRunRequest(CamelModel):
    symbols: List[str]
    direction: TradeDirection = "LONG"
    timeframe: str = "15m"
    lookback_days: int = Field(30, alias="lookbackDays")
    min_score: float = Field(60.0, alias="minScore")
    starting_capital: float = Field(100000.0, alias="startingCapital")
    risk_per_trade_pct: float = Field(0.01, alias="riskPerTradePct")


class TradeOut(CamelModel):
    symbol: str
    direction: Direction
    entry_time: Optional[datetime] = Field(None, alias="entryTime")
    entry_price: Optional[float] = Field(None, alias="entryPrice")
    exit_time: Optional[datetime] = Field(None, alias="exitTime")
    exit_price: Optional[float] = Field(None, alias="exitPrice")
    exit_reason: Optional[str] = Field(None, alias="exitReason")
    net_pnl: Optional[float] = Field(None, alias="netPnl")
    r_multiple: Optional[float] = Field(None, alias="rMultiple")


class BacktestReportOut(CamelModel):
    total_trades: int = Field(alias="totalTrades")
    winning_trades: int = Field(alias="winningTrades")
    losing_trades: int = Field(alias="losingTrades")
    win_rate: Optional[float] = Field(None, alias="winRate")
    profit_factor: Optional[float] = Field(None, alias="profitFactor")
    max_drawdown: float = Field(alias="maxDrawdown")
    average_r: Optional[float] = Field(None, alias="averageR")
    expectancy: Optional[float] = None
    total_pnl: float = Field(alias="totalPnl")


class BacktestRunResponse(CamelModel):
    report: BacktestReportOut
    trades: List[TradeOut]
    open_positions: List[TradeOut] = Field(default_factory=list, alias="openPositions")


# --- Paper trading ---


class OpenPositionRequest(CamelModel):
    symbol: str
    direction: TradeDirection
    entry_price: float = Field(alias="entryPrice")
    stop_loss: float = Field(alias="stopLoss")
    target: Optional[float] = None
    opportunity_score_at_entry: Optional[float] = Field(None, alias="opportunityScoreAtEntry")
    market_condition: Optional[str] = Field(None, alias="marketCondition")
    reason_for_entry: Optional[str] = Field(None, alias="reasonForEntry")


class ClosePositionRequest(CamelModel):
    exit_price: float = Field(alias="exitPrice")


class PaperPositionOut(CamelModel):
    id: str
    symbol: str
    direction: Direction
    entry_price: float = Field(alias="entryPrice")
    quantity: int
    stop_loss: Optional[float] = Field(None, alias="stopLoss")
    target: Optional[float] = None
    entry_time: datetime = Field(alias="entryTime")
    opportunity_score_at_entry: Optional[float] = Field(None, alias="opportunityScoreAtEntry")
    market_condition: Optional[str] = Field(None, alias="marketCondition")
    reason_for_entry: Optional[str] = Field(None, alias="reasonForEntry")
    exit_time: Optional[datetime] = Field(None, alias="exitTime")
    exit_price: Optional[float] = Field(None, alias="exitPrice")
    exit_reason: Optional[str] = Field(None, alias="exitReason")
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = Field(None, alias="pnlPct")
    r_multiple: Optional[float] = Field(None, alias="rMultiple")


class OpenPositionResponse(CamelModel):
    approved: bool
    position: Optional[PaperPositionOut] = None
    rejection_reasons: List[str] = Field(default_factory=list, alias="rejectionReasons")
    warnings: List[str] = Field(default_factory=list)


class PaperTradingSummaryOut(CamelModel):
    open_positions_count: int = Field(alias="openPositionsCount")
    closed_positions_count: int = Field(alias="closedPositionsCount")
    todays_pnl: float = Field(alias="todaysPnl")
    win_rate: Optional[float] = Field(None, alias="winRate")
    average_r: Optional[float] = Field(None, alias="averageR")
    max_drawdown: float = Field(alias="maxDrawdown")


# --- Alerts ---


class AlertOut(CamelModel):
    id: str
    symbol: str
    alert_type: str = Field(alias="alertType")
    direction: Optional[Direction] = None
    message: str
    fired_at: datetime = Field(alias="firedAt")


# --- Options ---


class OptionsAnalysisRequest(CamelModel):
    underlying_symbol: str = Field(alias="underlyingSymbol")


class OptionsAnalysisResponseOut(CamelModel):
    underlying_symbol: str = Field(alias="underlyingSymbol")
    underlying_direction: Direction = Field(alias="underlyingDirection")
    underlying_opportunity_score: float = Field(alias="underlyingOpportunityScore")
    option_type: Optional[str] = Field(None, alias="optionType")
    expiry: Optional[date] = None
    strike: Optional[float] = None
    premium: Optional[float] = None
    volume: Optional[int] = None
    open_interest: Optional[int] = Field(None, alias="openInterest")
    change_in_open_interest: Optional[int] = Field(None, alias="changeInOpenInterest")
    implied_volatility: Optional[float] = Field(None, alias="impliedVolatility")
    bid: Optional[float] = None
    ask: Optional[float] = None
    spread_pct: Optional[float] = Field(None, alias="spreadPct")
    liquidity: Optional[str] = None
    risk_reward: Optional[float] = Field(None, alias="riskReward")
    selection_note: str = Field(alias="selectionNote")


# --- Errors ---


class ErrorResponse(CamelModel):
    error: str
    detail: Optional[str] = None


# --- NSE MCP daily scan (informational only - no entry/order fields) ---


class DataFreshness(str):
    """Not an enum on purpose - kept as plain string values documented
    here so the API can report a freshness label without over-committing
    to a fixed set that might not fit a future provider:
    "live" (fresh within the provider's own refresh cadence),
    "delayed" (older than the live cache TTL but from a live-capable
    provider), "cached" (served from the last-known-good cache after a
    live fetch failed), "historical" (end-of-day/Bhavcopy-sourced,
    inherently not live), "mock" (MockDataProvider - never real)."""


class CategoryScoreOut(CamelModel):
    name: str
    available: bool
    score: Optional[float] = None
    max_score: float = Field(alias="maxScore")
    explanation: str


class TechnicalSetupScoreOut(CamelModel):
    total_score: float = Field(alias="totalScore")
    categories: List[CategoryScoreOut]
    unavailable_categories: List[str] = Field(default_factory=list, alias="unavailableCategories")


class DailyScanRowOut(CamelModel):
    symbol: str
    price: float
    change_pct: Optional[float] = Field(None, alias="changePct")
    volume: int
    ema_20: Optional[float] = Field(None, alias="ema20")
    ema_50: Optional[float] = Field(None, alias="ema50")
    ema_200: Optional[float] = Field(None, alias="ema200")
    rsi: Optional[float] = None
    relative_volume: Optional[float] = Field(None, alias="relativeVolume")
    return_20d_pct: Optional[float] = Field(None, alias="return20dPct")
    pct_from_52w_high: Optional[float] = Field(None, alias="pctFrom52wHigh")
    pct_from_52w_low: Optional[float] = Field(None, alias="pctFrom52wLow")
    setup_score: TechnicalSetupScoreOut = Field(alias="setupScore")
    as_of: date = Field(alias="asOf")
    error: Optional[str] = None


class DailyScanResponse(CamelModel):
    generated_at: datetime = Field(alias="generatedAt")
    data_source: str = Field(alias="dataSource")           # "nse_mcp" or "mock"
    data_freshness: str = Field(alias="dataFreshness")      # see DataFreshness's docstring
    data_timestamp: str = Field(alias="dataTimestamp")      # "YYYY-MM-DD HH:MM:SS", exactly as requested
    is_stale: bool = Field(alias="isStale")
    stale_reason: Optional[str] = Field(None, alias="staleReason")
    rows: List[DailyScanRowOut]
    disclaimer: str = (
        "Technical Setup Score reflects measurable technical signals only. "
        "It is not a probability or guarantee of future price movement."
    )
