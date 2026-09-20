import type { MarketStatusSummary, RankedStock } from "./types";

/**
 * PLACEHOLDER DATA. Shaped exactly like the real backend's output (see
 * lib/types.ts's comments pointing at the Python source), so swapping
 * this file's callers for real fetch() calls in lib/api.ts is the only
 * change needed once the FastAPI endpoints from the Phase 1 architecture
 * exist. Do not treat these numbers as real market data.
 */

export const mockMarketStatus: MarketStatusSummary = {
  state: "OPEN",
  reason: null,
  indexName: "NIFTY 200",
  price: 13842.15,
  changePct: 0.62,
  vwap: 13819.4,
  direction: "Bullish",
  regime: "Trending",
  adx: 27.4,
  strengthLabel: "Moderate",
};

const rawRows: Array<Omit<RankedStock, "rank">> = [
  { symbol: "RELIANCE", exchange: "NSE", price: 2948.6, changePct: 1.84, volume: 4200000, relativeVolume: 2.4, vwap: 2941.1, rsi: 68.2, adx: 31.5, trend: "18.0/20", direction: "LONG", opportunityScore: 87, entryStatus: "READY", entryPrice: 2948.6, stopLoss: 2905.1, target: 3032.0, riskReward: 1.92, setupExplanation: "LONG Opportunity Score: 87.0/100 (87%) - a measure of current Setup Quality and Signal Strength, not a probability of profit. Strongly confirmed: Trend, VWAP, EMA Structure, Breakout/Breakdown. Partially confirmed: Volume, Market Confirmation. This score reflects currently-aligned technical conditions only; it is not a guarantee of any outcome and has not yet been validated against historical performance." },
  { symbol: "TATASTEEL", exchange: "NSE", price: 162.85, changePct: 2.41, volume: 18600000, relativeVolume: 1.9, vwap: 161.05, rsi: 71.4, adx: 28.9, trend: "16.0/20", direction: "LONG", opportunityScore: 81, entryStatus: "READY", entryPrice: 162.85, stopLoss: 159.4, target: 169.2, riskReward: 1.83, setupExplanation: "LONG Opportunity Score: 81.0/100 (81%) - a measure of current Setup Quality and Signal Strength, not a probability of profit. Strongly confirmed: Trend, Volume. Partially confirmed: VWAP, Breakout/Breakdown." },
  { symbol: "ICICIBANK", exchange: "NSE", price: 1284.2, changePct: 1.12, volume: 7800000, relativeVolume: 1.6, vwap: 1279.9, rsi: 63.7, adx: 24.2, trend: "14.0/20", direction: "LONG", opportunityScore: 76, entryStatus: "WATCH", entryPrice: 1284.2, stopLoss: 1264.0, target: 1318.5, riskReward: 1.7, setupExplanation: "LONG Opportunity Score: 76.0/100 (76%) - a measure of current Setup Quality and Signal Strength, not a probability of profit. Partially confirmed: Trend, VWAP, Volume, Market Confirmation." },
  { symbol: "ZOMATO", exchange: "NSE", price: 261.35, changePct: -2.31, volume: 22100000, relativeVolume: 2.1, vwap: 263.8, rsi: 29.6, adx: 26.8, trend: "15.0/20", direction: "SHORT", opportunityScore: 74, entryStatus: "WATCH", entryPrice: 261.35, stopLoss: 267.8, target: 248.9, riskReward: 1.93, setupExplanation: "SHORT Opportunity Score: 74.0/100 (74%) - a measure of current Setup Quality and Signal Strength, not a probability of profit. Strongly confirmed: Trend, Momentum. Partially confirmed: VWAP, Breakout/Breakdown, Market Confirmation." },
  { symbol: "HDFCBANK", exchange: "NSE", price: 1698.75, changePct: 0.68, volume: 5400000, relativeVolume: 1.3, vwap: 1695.2, rsi: 59.1, adx: 19.4, trend: "11.0/20", direction: "LONG", opportunityScore: 62, entryStatus: "WATCH", entryPrice: 1698.75, stopLoss: 1678.0, target: 1728.0, riskReward: 1.41, setupExplanation: "LONG Opportunity Score: 62.0/100 (62%) - a measure of current Setup Quality and Signal Strength, not a probability of profit. Partially confirmed: Trend, VWAP, Momentum." },
  { symbol: "INFY", exchange: "NSE", price: 1842.1, changePct: -0.94, volume: 6100000, relativeVolume: 1.1, vwap: 1846.5, rsi: 38.4, adx: 17.2, trend: "9.0/20", direction: "SHORT", opportunityScore: 54, entryStatus: "NONE", entryPrice: 1842.1, stopLoss: 1858.9, target: 1814.6, riskReward: 1.63, setupExplanation: "SHORT Opportunity Score: 54.0/100 (54%) - a measure of current Setup Quality and Signal Strength, not a probability of profit. Partially confirmed: Trend, Momentum. Not confirmed: Volume, Market Confirmation." },
  { symbol: "BAJFINANCE", exchange: "NSE", price: 7124.5, changePct: 0.21, volume: 1200000, relativeVolume: 0.8, vwap: 7118.9, rsi: 52.0, adx: 14.6, trend: "7.0/20", direction: "NONE", opportunityScore: 38, entryStatus: "NONE", entryPrice: 7124.5, stopLoss: null, target: null, riskReward: null, setupExplanation: "LONG Opportunity Score: 38.0/100 (38%) - a measure of current Setup Quality and Signal Strength, not a probability of profit. Not confirmed: Trend, Volume, Breakout/Breakdown." },
  { symbol: "ADANIENT", exchange: "NSE", price: 2410.9, changePct: -1.42, volume: 9700000, relativeVolume: 1.7, vwap: 2422.3, rsi: 33.1, adx: 22.5, trend: "12.0/20", direction: "SHORT", opportunityScore: 58, entryStatus: "WATCH", entryPrice: 2410.9, stopLoss: 2448.0, target: 2358.0, riskReward: 1.43, setupExplanation: "SHORT Opportunity Score: 58.0/100 (58%) - a measure of current Setup Quality and Signal Strength, not a probability of profit. Partially confirmed: Trend, VWAP, Volume." },
  { symbol: "LT", exchange: "NSE", price: 3652.4, changePct: 0.55, volume: 2900000, relativeVolume: 1.0, vwap: 3648.7, rsi: 56.3, adx: 16.1, trend: "8.0/20", direction: "LONG", opportunityScore: 44, entryStatus: "NONE", entryPrice: 3652.4, stopLoss: null, target: null, riskReward: null, setupExplanation: "LONG Opportunity Score: 44.0/100 (44%) - a measure of current Setup Quality and Signal Strength, not a probability of profit. Not confirmed: Trend, Breakout/Breakdown." },
  { symbol: "AXISBANK", exchange: "NSE", price: 1142.15, changePct: 0.33, volume: 4000000, relativeVolume: 0.9, vwap: 1140.8, rsi: 54.8, adx: 15.0, trend: "6.0/20", direction: "NONE", opportunityScore: 35, entryStatus: "NONE", entryPrice: 1142.15, stopLoss: null, target: null, riskReward: null, setupExplanation: "LONG Opportunity Score: 35.0/100 (35%) - a measure of current Setup Quality and Signal Strength, not a probability of profit. Not confirmed: Trend, Volume, Momentum." },
  { symbol: "SBIN", exchange: "NSE", price: 812.4, changePct: 1.05, volume: 11200000, relativeVolume: 1.5, vwap: 808.9, rsi: 61.2, adx: 21.0, trend: "13.0/20", direction: "LONG", opportunityScore: 68, entryStatus: "WATCH", entryPrice: 812.4, stopLoss: 799.5, target: 831.0, riskReward: 1.44, setupExplanation: "LONG Opportunity Score: 68.0/100 (68%) - a measure of current Setup Quality and Signal Strength, not a probability of profit. Partially confirmed: Trend, VWAP, Volume." },
  { symbol: "HINDUNILVR", exchange: "NSE", price: 2384.7, changePct: -0.48, volume: 1800000, relativeVolume: 0.7, vwap: 2389.1, rsi: 46.7, adx: 12.3, trend: "4.0/20", direction: "NONE", opportunityScore: 26, entryStatus: "NONE", entryPrice: 2384.7, stopLoss: null, target: null, riskReward: null, setupExplanation: "SHORT Opportunity Score: 26.0/100 (26%) - a measure of current Setup Quality and Signal Strength, not a probability of profit. Not confirmed: Trend, Volume, Momentum, Breakout/Breakdown." },
  { symbol: "BHARTIARTL", exchange: "NSE", price: 1598.2, changePct: 1.63, volume: 3600000, relativeVolume: 1.8, vwap: 1589.6, rsi: 66.9, adx: 25.7, trend: "15.0/20", direction: "LONG", opportunityScore: 79, entryStatus: "READY", entryPrice: 1598.2, stopLoss: 1574.0, target: 1638.0, riskReward: 1.65, setupExplanation: "LONG Opportunity Score: 79.0/100 (79%) - a measure of current Setup Quality and Signal Strength, not a probability of profit. Strongly confirmed: Trend, VWAP. Partially confirmed: Volume, Breakout/Breakdown." },
  { symbol: "KOTAKBANK", exchange: "NSE", price: 1756.9, changePct: -1.08, volume: 3100000, relativeVolume: 1.4, vwap: 1764.2, rsi: 35.5, adx: 23.1, trend: "13.0/20", direction: "SHORT", opportunityScore: 65, entryStatus: "WATCH", entryPrice: 1756.9, stopLoss: 1778.0, target: 1720.0, riskReward: 1.75, setupExplanation: "SHORT Opportunity Score: 65.0/100 (65%) - a measure of current Setup Quality and Signal Strength, not a probability of profit. Partially confirmed: Trend, VWAP, Momentum." },
  { symbol: "ITC", exchange: "NSE", price: 468.3, changePct: 0.12, volume: 8900000, relativeVolume: 0.9, vwap: 467.5, rsi: 51.0, adx: 10.4, trend: "3.0/20", direction: "NONE", opportunityScore: 21, entryStatus: "NONE", entryPrice: 468.3, stopLoss: null, target: null, riskReward: null, setupExplanation: "LONG Opportunity Score: 21.0/100 (21%) - a measure of current Setup Quality and Signal Strength, not a probability of profit. Not confirmed: Trend, Volume, Momentum, Market Confirmation." },
];

export const mockRankedStocks: RankedStock[] = rawRows
  .slice()
  .sort((a, b) => b.opportunityScore - a.opportunityScore)
  .map((row, i) => ({ ...row, rank: i + 1 }));
