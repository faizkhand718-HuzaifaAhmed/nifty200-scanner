/**
 * Chart data contracts.
 *
 * CRITICAL RULE: every overlay value here (vwap, ema9, ema20, ema50,
 * ema200, prevDayHigh, prevDayLow, support, resistance) and every setup
 * marker MUST originate from the backend's already-computed output
 * (app.indicators.engine.IndicatorEngine.compute() and
 * app.setup_detection.engine.SetupDetectionEngine.compute() - see
 * backend/app/indicators/engine.py and backend/app/setup_detection/engine.py).
 *
 * The frontend NEVER recomputes an indicator from raw candles. There is
 * no EMA/VWAP/RSI math anywhere in this app outside of
 * lib/mockChartData.ts, and that file exists ONLY to fake a backend
 * response shape until the real HTTP endpoint exists - it is explicitly
 * NOT part of the production signal path and must be deleted (not
 * "kept as a fallback") once the real API is wired up. See that file's
 * header comment for why this distinction matters.
 */

export type Timeframe = "1m" | "3m" | "5m" | "10m" | "15m" | "30m" | "1d";

export const TIMEFRAMES: Timeframe[] = ["1m", "3m", "5m", "10m", "15m", "30m", "1d"];

export const TIMEFRAME_LABELS: Record<Timeframe, string> = {
  "1m": "1m",
  "3m": "3m",
  "5m": "5m",
  "10m": "10m",
  "15m": "15m",
  "30m": "30m",
  "1d": "Daily",
};

/** One OHLCV bar. `time` is a Unix seconds timestamp (lightweight-charts'
 * native time format). Matches app.market_data.schemas.Candle 1:1 (minus
 * is_complete, which the chart doesn't need to render). */
export interface ChartCandle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/** One point of an overlay line series, aligned to a candle's `time`. */
export interface OverlayPoint {
  time: number;
  value: number;
}

/** Every available overlay, as parallel time-aligned series. A given
 * overlay may have fewer points than there are candles (e.g. EMA200
 * needs warm-up, prev-day levels don't exist on the first day) -
 * missing points are simply absent, never backfilled with a guess. */
export interface ChartOverlays {
  vwap: OverlayPoint[];
  ema9: OverlayPoint[];
  ema20: OverlayPoint[];
  ema50: OverlayPoint[];
  ema200: OverlayPoint[];
  prevDayHigh: OverlayPoint[];
  prevDayLow: OverlayPoint[];
  support: OverlayPoint[];
  resistance: OverlayPoint[];
}

export type SetupMarkerType = "breakout" | "breakdown" | "retest_long" | "retest_short";

/** A buy/sell setup marker - mirrors Phase 5's boolean setup-detection
 * columns (long_breakout, long_retest, short_breakdown, short_retest).
 * `time` must be an actual candle time this marker is attached to. */
export interface SetupMarker {
  time: number;
  type: SetupMarkerType;
  direction: "LONG" | "SHORT";
}

/** The current trade plan (Phase 7's RankingEngine output) - rendered as
 * fixed horizontal lines, not a time series, since these are single
 * current values, not a history. Any of these can be null (e.g. no valid
 * direction, or no usable stop/target level). */
export interface TradePlanLevels {
  entry: number | null;
  stopLoss: number | null;
  target: number | null;
}

export interface ChartData {
  symbol: string;
  timeframe: Timeframe;
  /** False when the backend genuinely has no data for this
   * symbol/timeframe combination (e.g. an intraday timeframe against a
   * data source that only provides daily bars) - the chart must show a
   * clear "not available" message in this case, never an empty chart
   * that looks broken or, worse, looks like real data with nothing in
   * it. See app/api/services/chart_service.py's module docstring. */
  available: boolean;
  candles: ChartCandle[];
  overlays: ChartOverlays;
  markers: SetupMarker[];
  tradePlan: TradePlanLevels;
}

export type OverlayKey = keyof ChartOverlays;

export const OVERLAY_LABELS: Record<OverlayKey, string> = {
  vwap: "VWAP",
  ema9: "EMA 9",
  ema20: "EMA 20",
  ema50: "EMA 50",
  ema200: "EMA 200",
  prevDayHigh: "Prev day high",
  prevDayLow: "Prev day low",
  support: "Support",
  resistance: "Resistance",
};

export const OVERLAY_COLORS: Record<OverlayKey, string> = {
  vwap: "#4C8DFF",
  ema9: "#E8B339",
  ema20: "#D4537E",
  ema50: "#7F77DD",
  ema200: "#8B93A1",
  prevDayHigh: "#5B6270",
  prevDayLow: "#5B6270",
  support: "#3DD68C",
  resistance: "#F0596B",
};
