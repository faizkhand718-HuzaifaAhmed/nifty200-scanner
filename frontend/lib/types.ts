/**
 * Data contracts for the dashboard. These field names deliberately mirror
 * the Python backend's actual output columns (see
 * backend/app/ranking/engine.py RankingEngine._build_row, and
 * backend/app/market_data/schemas.py MarketStatus) so wiring in the real
 * API later is a matter of fetching and passing through, not renaming.
 */

export type Direction = "LONG" | "SHORT" | "NONE";
export type EntryStatus = "READY" | "WATCH" | "NONE";
export type MarketSessionState = "PRE_OPEN" | "OPEN" | "CLOSED" | "HOLIDAY";

/** One row of the ranked table - matches RankingEngine.rank()'s output columns. */
export interface RankedStock {
  rank: number;
  symbol: string;
  exchange: string;
  price: number;
  changePct: number | null;
  volume: number;
  relativeVolume: number;
  vwap: number;
  rsi: number | null;
  adx: number | null;
  /** Category breakdown string from OpportunityScoringEngine.breakdown(), e.g. "15.0/20". */
  trend: string;
  direction: Direction;
  opportunityScore: number;
  entryStatus: EntryStatus;
  entryPrice: number;
  stopLoss: number | null;
  target: number | null;
  riskReward: number | null;
  setupExplanation: string;
}

/** Top section - mirrors app.market_data.schemas.MarketStatus plus a few
 * derived fields (direction/regime/strength) the dashboard displays. */
export interface MarketStatusSummary {
  state: MarketSessionState;
  reason: string | null;
  indexName: string;
  price: number;
  changePct: number;
  vwap: number;
  /** Derived from NIFTY's own EMA20-vs-EMA50 (see setup_detection conditions). */
  direction: "Bullish" | "Bearish" | "Neutral";
  /** Derived label, e.g. "Trending" / "Ranging" - not yet a backend field;
   * see lib/api.ts for the placeholder derivation until a real endpoint exists. */
  regime: "Trending" | "Ranging";
  /** NIFTY's own ADX value plus a plain-language strength label. */
  adx: number;
  strengthLabel: "Weak" | "Moderate" | "Strong";
}

export interface RankingFilterState {
  direction: Direction | "ALL";
  entryStatus: EntryStatus | "ALL";
  minScore: number | null;
  minRiskReward: number | null;
  minRelativeVolume: number | null;
}

export type ViewSize = 1 | 3 | 5 | 10 | 200;
