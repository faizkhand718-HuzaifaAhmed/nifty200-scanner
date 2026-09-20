import { mockMarketStatus, mockRankedStocks } from "./mockData";
import { generateMockChartData } from "./mockChartData";
import { generateNextMockAlerts } from "./mockAlerts";
import { listOpenPositions, listClosedPositions, openMockPosition, closeMockPositionManually } from "./mockPaperTrading";
import type { MarketStatusSummary, RankedStock, RankingFilterState } from "./types";
import type { ChartData, Timeframe } from "./candles";
import type { Alert, AlertType } from "./alerts";
import type { PaperPosition, PaperTradingSummary } from "./paperTrading";

/**
 * API client. Every function here returns mock data today because the
 * FastAPI backend (Phase 1 architecture: GET /rankings, GET /stocks/
 * {symbol}, WebSocket for live push) doesn't exist as an HTTP service
 * yet - only the underlying Python engines (Phases 2-7) do. The shape of
 * these functions matches what the real calls will look like, so wiring
 * them up later is:
 *
 *   export async function getRankings(...) {
 *     const res = await fetch(`${API_BASE}/rankings?...`);
 *     return res.json();
 *   }
 *
 * not a redesign. Do not treat the data returned here as real market data.
 */

const SIMULATED_LATENCY_MS = 150;

function delay<T>(value: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), SIMULATED_LATENCY_MS));
}

export async function getMarketStatus(): Promise<MarketStatusSummary> {
  // TODO: replace with `fetch('/api/market-status')` once the backend
  // exposes app.market_data.calendar.NSECalendar.get_market_status() (and
  // NIFTY's own indicator snapshot for direction/regime/strength) over HTTP.
  return delay(mockMarketStatus);
}

export interface GetRankingsParams {
  filters?: Partial<RankingFilterState>;
  limit?: number;
}

export async function getRankings(params: GetRankingsParams = {}): Promise<RankedStock[]> {
  // TODO: replace with a real call to GET /rankings, passing `filters` and
  // `limit` as query params - the backend's RankingEngine.rank() +
  // app.ranking.filters.apply_filters()/top_n() already implement exactly
  // this contract (see backend/app/ranking/engine.py and filters.py).
  let rows = mockRankedStocks.slice();

  const f = params.filters;
  if (f?.direction && f.direction !== "ALL") {
    rows = rows.filter((r) => r.direction === f.direction);
  }
  if (f?.entryStatus && f.entryStatus !== "ALL") {
    rows = rows.filter((r) => r.entryStatus === f.entryStatus);
  }
  if (f?.minScore !== null && f?.minScore !== undefined) {
    rows = rows.filter((r) => r.opportunityScore > f.minScore!);
  }
  if (f?.minRiskReward !== null && f?.minRiskReward !== undefined) {
    rows = rows.filter((r) => r.riskReward !== null && r.riskReward > f.minRiskReward!);
  }
  if (f?.minRelativeVolume !== null && f?.minRelativeVolume !== undefined) {
    rows = rows.filter((r) => r.relativeVolume > f.minRelativeVolume!);
  }

  rows = rows.map((r, i) => ({ ...r, rank: i + 1 }));
  if (params.limit) rows = rows.slice(0, params.limit);
  return delay(rows);
}

export async function getStockDetail(symbol: string): Promise<RankedStock | null> {
  // TODO: replace with `fetch(`/api/stocks/${symbol}`)`. The detail page
  // will eventually want more than this row alone (full indicator history
  // for charting, the full setup-detection component breakdown from
  // Phase 5, etc.) - this is a placeholder until that endpoint exists.
  const row = mockRankedStocks.find((r) => r.symbol === symbol) ?? null;
  return delay(row);
}

/**
 * Full 9-category score breakdown for the detail page - matches
 * OpportunityScoringEngine.breakdown()'s output shape exactly (see
 * backend/app/scoring/engine.py). The summary ranking table only carries
 * Trend/Volume/VWAP forward (per the Phase 7 spec); the detail page shows
 * all nine, which is what makes it "detailed".
 */
export interface CategoryBreakdown {
  category: string;
  score: number;
  max: number;
}

const MOCK_BREAKDOWNS: Record<string, CategoryBreakdown[]> = {
  RELIANCE: [
    { category: "Trend", score: 18, max: 20 },
    { category: "Volume", score: 12, max: 15 },
    { category: "VWAP", score: 15, max: 15 },
    { category: "Momentum", score: 8, max: 10 },
    { category: "EMA Structure", score: 10, max: 10 },
    { category: "Breakout/Breakdown", score: 8, max: 10 },
    { category: "Market Confirmation", score: 7, max: 10 },
    { category: "Relative Strength", score: 4, max: 5 },
    { category: "Risk/Volatility", score: 5, max: 5 },
  ],
  ZOMATO: [
    { category: "Trend", score: 17, max: 20 },
    { category: "Volume", score: 9, max: 15 },
    { category: "VWAP", score: 10, max: 15 },
    { category: "Momentum", score: 9, max: 10 },
    { category: "EMA Structure", score: 7, max: 10 },
    { category: "Breakout/Breakdown", score: 6, max: 10 },
    { category: "Market Confirmation", score: 6, max: 10 },
    { category: "Relative Strength", score: 3, max: 5 },
    { category: "Risk/Volatility", score: 3, max: 5 },
  ],
};

function defaultBreakdown(score: number): CategoryBreakdown[] {
  // Even split placeholder for symbols without a hand-authored mock -
  // clearly a placeholder, not a real per-category computation.
  const weights: [string, number][] = [
    ["Trend", 20], ["Volume", 15], ["VWAP", 15], ["Momentum", 10], ["EMA Structure", 10],
    ["Breakout/Breakdown", 10], ["Market Confirmation", 10], ["Relative Strength", 5], ["Risk/Volatility", 5],
  ];
  const fraction = score / 100;
  return weights.map(([category, max]) => ({ category, max, score: Math.round(max * fraction * 10) / 10 }));
}

export async function getStockBreakdown(symbol: string): Promise<CategoryBreakdown[]> {
  // TODO: replace with the real per-symbol breakdown from GET
  // /stocks/{symbol}, sourced from OpportunityScoringEngine.breakdown().
  const row = mockRankedStocks.find((r) => r.symbol === symbol);
  const breakdown = MOCK_BREAKDOWNS[symbol] ?? defaultBreakdown(row?.opportunityScore ?? 0);
  return delay(breakdown);
}

export async function getChartData(symbol: string, timeframe: Timeframe): Promise<ChartData> {
  // TODO: replace with `fetch(`/api/chart?symbol=${symbol}&timeframe=${timeframe}`)`.
  // The real endpoint returns IndicatorEngine.compute()'s candle+overlay
  // columns and SetupDetectionEngine.compute()'s breakout/retest booleans
  // DIRECTLY - see lib/candles.ts's header comment. generateMockChartData
  // (lib/mockChartData.ts) is a quarantined stand-in, not a template for
  // how the real integration should work.
  return delay(generateMockChartData(symbol, timeframe));
}

/**
 * Live-update hook placeholder. The real implementation subscribes to the
 * Phase 1 architecture's WebSocket channel for rank-update events (see
 * docs/architecture Section 12/14) and calls `onUpdate` with fresh rows as
 * they arrive - "ranking must automatically update when new data arrives"
 * happens there, not by polling. Until that channel exists, callers should
 * just re-call getRankings() on their own refresh interval.
 */
export function subscribeToLiveRankings(onUpdate: (rows: RankedStock[]) => void): () => void {
  const interval = setInterval(() => {
    getRankings().then(onUpdate);
  }, 15000);
  return () => clearInterval(interval);
}

// ---------------------------------------------------------------------
// Alerts (Phase 11)
// ---------------------------------------------------------------------

/**
 * TODO: replace with `fetch('/api/alerts?symbol=...&type=...&limit=...')`.
 * The real endpoint reads straight from backend/app/alerts/history.py's
 * AlertHistory.list() - same filter shape, same most-recent-first order.
 */
export async function getAlertHistory(params: { symbol?: string; alertType?: AlertType; limit?: number } = {}): Promise<Alert[]> {
  let results = mockAlertLog.slice().reverse();
  if (params.symbol) results = results.filter((a) => a.symbol === params.symbol);
  if (params.alertType) results = results.filter((a) => a.alertType === params.alertType);
  if (params.limit) results = results.slice(0, params.limit);
  return delay(results);
}

const mockAlertLog: Alert[] = [];

/**
 * TODO: replace with a WebSocket subscription to the backend's alert
 * channel (AlertEngine.evaluate() is called once per bar per symbol
 * server-side; this would push each NEW Alert the moment it's generated,
 * not poll). Until then this polls the mock generator every 4 seconds -
 * each new alert it returns is genuinely new (the mock generator only
 * ever returns alerts once, same dedup contract the real backend
 * guarantees via AlertHistory).
 */
export function subscribeToAlerts(onNewAlerts: (alerts: Alert[]) => void): () => void {
  const interval = setInterval(() => {
    const fresh = generateNextMockAlerts();
    if (fresh.length > 0) {
      mockAlertLog.push(...fresh);
      onNewAlerts(fresh);
    }
  }, 4000);
  return () => clearInterval(interval);
}

// ---------------------------------------------------------------------
// Paper trading (Phase 13)
// ---------------------------------------------------------------------

/**
 * TODO: replace with `fetch('/api/paper-trading/positions?status=open')`.
 * The real endpoint reads from backend/app/paper_trading/engine.py's
 * PaperTradingEngine.get_open_positions()/get_closed_positions().
 */
export async function getOpenPositions(): Promise<PaperPosition[]> {
  return delay(listOpenPositions());
}

export async function getClosedPositions(): Promise<PaperPosition[]> {
  return delay(listClosedPositions());
}

/**
 * TODO: replace with `fetch('/api/paper-trading/summary')`, backed by
 * app.paper_trading.metrics.compute_summary().
 */
export async function getPaperTradingSummary(): Promise<PaperTradingSummary> {
  const open = listOpenPositions();
  const closed = listClosedPositions();
  const today = new Date();
  const todaysPnl = closed
    .filter((p) => p.exitTime && new Date(p.exitTime).toDateString() === today.toDateString())
    .reduce((sum, p) => sum + (p.pnl ?? 0), 0);
  const wins = closed.filter((p) => (p.pnl ?? 0) > 0).length;
  const winRate = closed.length > 0 ? wins / closed.length : null;
  const rValues = closed.map((p) => p.rMultiple).filter((r): r is number => r !== null);
  const averageR = rValues.length > 0 ? rValues.reduce((a, b) => a + b, 0) / rValues.length : null;

  let equity = 0, peak = 0, maxDd = 0;
  for (const p of [...closed].sort((a, b) => (a.exitTime ?? "").localeCompare(b.exitTime ?? ""))) {
    equity += p.pnl ?? 0;
    peak = Math.max(peak, equity);
    maxDd = Math.max(maxDd, peak - equity);
  }

  return delay({
    openPositionsCount: open.length,
    closedPositionsCount: closed.length,
    todaysPnl,
    winRate,
    averageR,
    maxDrawdown: maxDd,
  });
}

/**
 * "Allow the user to create a virtual position" - called from a UI
 * button (see components/PaperTradeButton.tsx), never automatically.
 * TODO: replace with `fetch('/api/paper-trading/positions', {method:'POST', ...})`,
 * backed by PaperTradingEngine.open_position() (or paper_trade_from_lifecycle()
 * when triggered from a live entry signal).
 */
export async function openPaperPosition(input: {
  symbol: string;
  direction: "LONG" | "SHORT";
  entryPrice: number;
  quantity: number;
  stopLoss: number | null;
  target: number | null;
  opportunityScoreAtEntry: number | null;
  marketCondition: string | null;
  reasonForEntry: string | null;
}): Promise<PaperPosition> {
  return delay(openMockPosition(input));
}

export async function closePaperPositionManually(id: string, exitPrice: number): Promise<PaperPosition | null> {
  return delay(closeMockPositionManually(id, exitPrice));
}
