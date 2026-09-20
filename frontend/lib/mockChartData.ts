/**
 * ============================================================================
 * MOCK-ONLY FILE. NOT PART OF THE PRODUCTION SIGNAL PATH.
 * ============================================================================
 *
 * This file computes EMA/VWAP/support-resistance math IN THE BROWSER. That
 * is normally exactly what this project forbids - see lib/candles.ts's
 * header comment. It exists here, and ONLY here, to fake a plausible
 * response shape for lib/api.ts's getChartData() while no real backend
 * HTTP endpoint exists yet.
 *
 * When the real endpoint exists (returning the actual output of
 * backend/app/indicators/engine.py's IndicatorEngine.compute() and
 * backend/app/setup_detection/engine.py's SetupDetectionEngine.compute()),
 * DELETE THIS FILE ENTIRELY and point getChartData() at that endpoint. Do
 * not keep this as a "fallback" - a fallback that recomputes indicators
 * differently than the backend is exactly the frontend/backend signal
 * mismatch this phase was asked to prevent.
 *
 * The math below deliberately mirrors the backend's actual formulas
 * (see backend/app/indicators/trend.py's ema(), volume.py's vwap()) so the
 * mock at least *looks* like real output - but "looks like" is not "is",
 * and floating-point/rounding/warm-up differences are expected and fine
 * for a mock that will be thrown away.
 */
import type { ChartCandle, ChartData, ChartOverlays, OverlayPoint, SetupMarker, Timeframe } from "./candles";
import { mockRankedStocks } from "./mockData";

const TIMEFRAME_MINUTES: Record<Timeframe, number> = {
  "1m": 1,
  "3m": 3,
  "5m": 5,
  "10m": 10,
  "15m": 15,
  "30m": 30,
  "1d": 375, // one full session, for generating one bar per day
};

function seededRandom(seed: number): () => number {
  let s = seed % 2147483647;
  if (s <= 0) s += 2147483646;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

function hashString(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (h << 5) - h + s.charCodeAt(i);
    h |= 0;
  }
  return Math.abs(h) || 1;
}

function ema(values: number[], span: number): (number | null)[] {
  const alpha = 2 / (span + 1);
  const out: (number | null)[] = [];
  let prev: number | null = null;
  for (const v of values) {
    prev = prev === null ? v : alpha * v + (1 - alpha) * prev;
    out.push(prev);
  }
  return out;
}

function generateCandles(symbol: string, timeframe: Timeframe, count: number): ChartCandle[] {
  const rng = seededRandom(hashString(`${symbol}:${timeframe}`));
  const stepSeconds = TIMEFRAME_MINUTES[timeframe] * 60;
  const nowSeconds = Math.floor(Date.now() / 1000);
  const startingBase = mockRankedStocks.find((r) => r.symbol === symbol)?.price ?? 500;

  let price = startingBase * 0.97;
  const candles: ChartCandle[] = [];
  for (let i = 0; i < count; i++) {
    const time = nowSeconds - (count - i) * stepSeconds;
    const drift = (rng() - 0.48) * price * 0.006;
    const open = price;
    const close = Math.max(1, open + drift);
    const high = Math.max(open, close) + rng() * price * 0.0025;
    const low = Math.min(open, close) - rng() * price * 0.0025;
    const volume = Math.round(50000 + rng() * 200000);
    candles.push({ time, open, high, low, close, volume });
    price = close;
  }
  return candles;
}

function toPoints(candles: ChartCandle[], values: (number | null)[]): OverlayPoint[] {
  const points: OverlayPoint[] = [];
  for (let i = 0; i < candles.length; i++) {
    const v = values[i];
    const candle = candles[i];
    if (v !== null && v !== undefined && candle !== undefined) points.push({ time: candle.time, value: v });
  }
  return points;
}

function buildOverlays(candles: ChartCandle[]): ChartOverlays {
  const closes = candles.map((c) => c.close);

  // VWAP: cumulative from the start of this mock series (a real
  // intraday VWAP resets daily - see backend/app/indicators/volume.py's
  // vwap(); this mock simplification is fine for a demo, not for real use).
  let cumPV = 0;
  let cumVol = 0;
  const vwapValues: number[] = candles.map((c) => {
    const typical = (c.high + c.low + c.close) / 3;
    cumPV += typical * c.volume;
    cumVol += c.volume;
    return cumVol > 0 ? cumPV / cumVol : typical;
  });

  // Previous-day high/low and a simple pivot-style support/resistance,
  // approximated by splitting the mock series into fixed-size "session"
  // chunks rather than real calendar days - a demo simplification.
  const sessionSize = Math.max(20, Math.floor(candles.length / 6));
  const prevDayHighPts: OverlayPoint[] = [];
  const prevDayLowPts: OverlayPoint[] = [];
  const supportPts: OverlayPoint[] = [];
  const resistancePts: OverlayPoint[] = [];
  for (let s = sessionSize; s < candles.length; s += sessionSize) {
    const prevSession = candles.slice(Math.max(0, s - sessionSize), s);
    const prevHigh = Math.max(...prevSession.map((c) => c.high));
    const prevLow = Math.min(...prevSession.map((c) => c.low));
    const prevClose = prevSession[prevSession.length - 1]?.close ?? prevHigh;
    const pivot = (prevHigh + prevLow + prevClose) / 3;
    const nextSessionEnd = Math.min(candles.length, s + sessionSize);
    for (let i = s; i < nextSessionEnd; i++) {
      const candle = candles[i];
      if (!candle) continue;
      prevDayHighPts.push({ time: candle.time, value: prevHigh });
      prevDayLowPts.push({ time: candle.time, value: prevLow });
      resistancePts.push({ time: candle.time, value: 2 * pivot - prevLow });
      supportPts.push({ time: candle.time, value: 2 * pivot - prevHigh });
    }
  }

  return {
    vwap: toPoints(candles, vwapValues),
    ema9: toPoints(candles, ema(closes, 9)),
    ema20: toPoints(candles, ema(closes, 20)),
    ema50: toPoints(candles, ema(closes, 50)),
    ema200: toPoints(candles, ema(closes, 200)),
    prevDayHigh: prevDayHighPts,
    prevDayLow: prevDayLowPts,
    support: supportPts,
    resistance: resistancePts,
  };
}

function buildMarkers(candles: ChartCandle[], rng: () => number): SetupMarker[] {
  // Simplified stand-in for Phase 5's real breakout/breakdown/retest
  // booleans: flags a bar as a breakout when its close exceeds the
  // trailing 20-bar high, a breakdown on the mirror condition. Real
  // markers come directly from the backend's setup_detection columns.
  const markers: SetupMarker[] = [];
  const window = 20;
  for (let i = window; i < candles.length; i++) {
    const candle = candles[i];
    if (!candle) continue;
    const trailing = candles.slice(i - window, i);
    const trailingHigh = Math.max(...trailing.map((c) => c.high));
    const trailingLow = Math.min(...trailing.map((c) => c.low));
    if (candle.close > trailingHigh) {
      markers.push({ time: candle.time, type: "breakout", direction: "LONG" });
    } else if (candle.close < trailingLow) {
      markers.push({ time: candle.time, type: "breakdown", direction: "SHORT" });
    }
  }
  return markers;
}

export function generateMockChartData(symbol: string, timeframe: Timeframe): ChartData {
  const count = timeframe === "1d" ? 90 : 180;
  const candles = generateCandles(symbol, timeframe, count);
  const overlays = buildOverlays(candles);
  const rng = seededRandom(hashString(`${symbol}:${timeframe}:markers`));
  const markers = buildMarkers(candles, rng);

  const row = mockRankedStocks.find((r) => r.symbol === symbol);
  const tradePlan = {
    entry: row?.entryPrice ?? null,
    stopLoss: row?.stopLoss ?? null,
    target: row?.target ?? null,
  };

  return { symbol, timeframe, candles, overlays, markers, tradePlan };
}
