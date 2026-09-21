import type { MarketStatusSummary, RankedStock, RankingFilterState } from "./types";
import type { ChartData, Timeframe } from "./candles";
import type { Alert, AlertType } from "./alerts";
import type { PaperPosition, PaperTradingSummary } from "./paperTrading";

/**
 * API client - REWIRED to call the real deployed backend.
 *
 * Set NEXT_PUBLIC_API_BASE_URL at build time to your backend's URL
 * (e.g. https://nifty200-scanner-xr5n.onrender.com) - see
 * frontend/Dockerfile's ARG/ENV for how this gets baked in.
 *
 * TWO FUNCTIONS REMAIN ON MOCK DATA, HONESTLY, BECAUSE NO REAL ENDPOINT
 * EXISTS FOR THEM YET: getMarketStatus() and getChartData(). Neither was
 * built in the backend's API layer - see the backend status report from
 * earlier in this project. Everything else below now calls the real,
 * deployed FastAPI backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  if (!API_BASE) {
    throw new Error(
      "NEXT_PUBLIC_API_BASE_URL is not set - the frontend has no backend URL to call. " +
      "Set it at build time to your deployed backend's URL."
    );
  }
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options?.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API request failed (${res.status} ${path}): ${body}`);
  }
  return res.json();
}

export async function getMarketStatus(): Promise<MarketStatusSummary> {
  return apiFetch<MarketStatusSummary>("/api/market-status");
}

export interface GetRankingsParams {
  filters?: Partial<RankingFilterState>;
  limit?: number;
}

interface RankingsResponseJson {
  generatedAt: string;
  skippedSymbols: Record<string, string>;
  stocks: RankedStock[];
}

export async function getRankings(params: GetRankingsParams = {}): Promise<RankedStock[]> {
  const f = params.filters;
  const query = new URLSearchParams();
  if (f?.direction && f.direction !== "ALL") query.set("direction", f.direction);
  if (f?.entryStatus && f.entryStatus !== "ALL") query.set("entry_status", f.entryStatus);
  if (f?.minScore !== null && f?.minScore !== undefined) query.set("min_score", String(f.minScore));
  if (params.limit) query.set("top", String(params.limit));

  const data = await apiFetch<RankingsResponseJson>(`/api/rankings?${query.toString()}`);
  let rows = data.stocks;

  // Filters the backend endpoint doesn't support server-side yet - kept
  // as client-side post-filters, same as before, so this behavior isn't
  // lost.
  if (f?.minRiskReward !== null && f?.minRiskReward !== undefined) {
    rows = rows.filter((r) => r.riskReward !== null && r.riskReward > f.minRiskReward!);
  }
  if (f?.minRelativeVolume !== null && f?.minRelativeVolume !== undefined) {
    rows = rows.filter((r) => r.relativeVolume > f.minRelativeVolume!);
  }
  return rows;
}

interface StockDetailResponseJson {
  stock: RankedStock;
  breakdown: { category: string; score: number; maxScore: number; explanation: string }[];
}

export async function getStockDetail(symbol: string): Promise<RankedStock | null> {
  try {
    const data = await apiFetch<StockDetailResponseJson>(`/api/stocks/${encodeURIComponent(symbol)}`);
    return data.stock;
  } catch {
    return null;
  }
}

export interface CategoryBreakdown {
  category: string;
  score: number;
  max: number;
}

export async function getStockBreakdown(symbol: string): Promise<CategoryBreakdown[]> {
  const data = await apiFetch<StockDetailResponseJson>(`/api/stocks/${encodeURIComponent(symbol)}`);
  return data.breakdown.map((b) => ({ category: b.category, score: b.score, max: b.maxScore }));
}

export async function getChartData(symbol: string, timeframe: Timeframe): Promise<ChartData> {
  return apiFetch<ChartData>(`/api/chart?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`);
}

/**
 * Polls the real backend every 15 seconds. No real WebSocket push exists
 * yet (see the backend status report) - this stays a poll for now, just
 * against real data instead of fake data.
 */
export function subscribeToLiveRankings(onUpdate: (rows: RankedStock[]) => void): () => void {
  const interval = setInterval(() => {
    getRankings().then(onUpdate).catch((err) => console.error("live rankings poll failed", err));
  }, 15000);
  return () => clearInterval(interval);
}

// ---------------------------------------------------------------------
// Alerts
// ---------------------------------------------------------------------

export async function getAlertHistory(params: { symbol?: string; alertType?: AlertType; limit?: number } = {}): Promise<Alert[]> {
  const query = new URLSearchParams();
  if (params.symbol) query.set("symbol", params.symbol);
  if (params.alertType) query.set("alert_type", params.alertType);
  if (params.limit) query.set("limit", String(params.limit));
  return apiFetch<Alert[]>(`/api/alerts?${query.toString()}`);
}

/**
 * IMPORTANT, HONEST LIMITATION: the real backend has NO automatic alert
 * generation loop yet (nothing calls AlertEngine.evaluate() on a
 * schedule - see backend/app/api/routes/alerts.py's own docstring). This
 * polls the real /api/alerts endpoint, but until a scheduler exists on
 * the backend, you will see the same (likely empty) history every time -
 * not because this is broken, but because nothing is generating new
 * alerts server-side yet.
 */
export function subscribeToAlerts(onNewAlerts: (alerts: Alert[]) => void): () => void {
  let seenIds = new Set<string>();
  const interval = setInterval(() => {
    getAlertHistory({ limit: 50 })
      .then((alerts) => {
        const fresh = alerts.filter((a) => !seenIds.has(a.id));
        if (fresh.length > 0) {
          fresh.forEach((a) => seenIds.add(a.id));
          onNewAlerts(fresh);
        }
      })
      .catch((err) => console.error("alert poll failed", err));
  }, 4000);
  return () => clearInterval(interval);
}

// ---------------------------------------------------------------------
// Paper trading
// ---------------------------------------------------------------------

export async function getOpenPositions(): Promise<PaperPosition[]> {
  return apiFetch<PaperPosition[]>("/api/paper-trading/positions?status=open");
}

export async function getClosedPositions(): Promise<PaperPosition[]> {
  return apiFetch<PaperPosition[]>("/api/paper-trading/positions?status=closed");
}

export async function getPaperTradingSummary(): Promise<PaperTradingSummary> {
  return apiFetch<PaperTradingSummary>("/api/paper-trading/summary");
}

interface OpenPositionResponseJson {
  approved: boolean;
  position: PaperPosition | null;
  rejectionReasons: string[];
  warnings: string[];
}

/**
 * "Allow the user to create a virtual position" - now calls the REAL,
 * risk-gated backend (RiskGatedPaperTradingEngine), which can genuinely
 * REJECT a position (duplicate symbol, daily loss limit, stale data,
 * etc.) - the mock version always succeeded, this one honestly won't.
 * On rejection, this throws an Error with the reasons joined together;
 * the calling component (components/PaperTradeButton.tsx) does not
 * currently catch this - per the instruction to keep existing UI
 * components unchanged, that component was NOT modified here. A
 * rejected request will currently leave that button showing "Opening…"
 * rather than a rejection message - a known, honest gap, not a silent
 * failure (the real reason is visible in the browser console).
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
  const data = await apiFetch<OpenPositionResponseJson>("/api/paper-trading/positions", {
    method: "POST",
    body: JSON.stringify(input),
  });
  if (!data.approved || !data.position) {
    throw new Error(`Position rejected: ${data.rejectionReasons.join("; ") || "unknown reason"}`);
  }
  return data.position;
}

export async function closePaperPositionManually(id: string, exitPrice: number): Promise<PaperPosition | null> {
  try {
    return await apiFetch<PaperPosition>(`/api/paper-trading/positions/${encodeURIComponent(id)}/close`, {
      method: "POST",
      body: JSON.stringify({ exitPrice }),
    });
  } catch {
    return null;
  }
}
