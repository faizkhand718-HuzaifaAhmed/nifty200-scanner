import type { Alert, AlertType } from "./alerts";
import { mockRankedStocks } from "./mockData";

/**
 * MOCK ONLY. Simulates alerts arriving over time the way the real
 * AlertEngine (backend/app/alerts/engine.py) would push them - a rotating
 * sample of alert types across a few symbols. Replace entirely once the
 * real alert endpoint/WebSocket channel exists (see lib/api.ts).
 */

let idCounter = 0;
function nextId(): string {
  idCounter += 1;
  return `mock-alert-${idCounter}`;
}

const SAMPLE_SEQUENCE: Array<{ symbol: string; alertType: AlertType; direction: "LONG" | "SHORT" | null; message: string }> = [
  { symbol: "RELIANCE", alertType: "LONG_SETUP", direction: "LONG", message: "RELIANCE LONG setup identified" },
  { symbol: "RELIANCE", alertType: "SCORE_CROSSES_80", direction: "LONG", message: "RELIANCE LONG score crossed 80" },
  { symbol: "RELIANCE", alertType: "BREAKOUT", direction: "LONG", message: "RELIANCE breakout above resistance" },
  { symbol: "RELIANCE", alertType: "ENTRY_TRIGGER", direction: "LONG", message: "RELIANCE entry triggered" },
  { symbol: "ZOMATO", alertType: "SHORT_SETUP", direction: "SHORT", message: "ZOMATO SHORT setup identified" },
  { symbol: "ZOMATO", alertType: "VWAP_REJECTION", direction: "SHORT", message: "ZOMATO rejected at VWAP" },
  { symbol: "ZOMATO", alertType: "BREAKDOWN", direction: "SHORT", message: "ZOMATO breakdown below support" },
  { symbol: "TATASTEEL", alertType: "SCORE_CROSSES_90", direction: "LONG", message: "TATASTEEL LONG score crossed 90" },
  { symbol: "RELIANCE", alertType: "TARGET", direction: "LONG", message: "RELIANCE target hit" },
  { symbol: "ADANIENT", alertType: "STOP_LOSS", direction: "SHORT", message: "ADANIENT stop loss hit" },
];

let cursor = 0;

/** Call this periodically (see api.ts's subscribeToAlerts) - each call
 * may return zero or more NEW alerts, matching how a real polling/push
 * endpoint would only deliver what's new since last time. */
export function generateNextMockAlerts(): Alert[] {
  if (cursor >= SAMPLE_SEQUENCE.length) return [];
  const item = SAMPLE_SEQUENCE[cursor];
  cursor += 1;
  if (!item) return [];

  const stock = mockRankedStocks.find((r) => r.symbol === item.symbol);
  return [
    {
      id: nextId(),
      symbol: item.symbol,
      alertType: item.alertType,
      direction: item.direction,
      message: item.message,
      candleTimestamp: Math.floor(Date.now() / 1000),
      firedAt: new Date().toISOString(),
      channels: ["DASHBOARD", "BROWSER_NOTIFICATION", "SOUND"],
      context: stock ? { score: stock.opportunityScore, price: stock.price } : {},
    },
  ];
}

export function resetMockAlertStream(): void {
  cursor = 0;
}
