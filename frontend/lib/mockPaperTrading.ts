import type { Direction, PaperPosition } from "./paperTrading";

/**
 * MOCK ONLY. Simulates backend/app/paper_trading/engine.py's
 * PaperTradingEngine in-memory, purely for demo purposes until a real
 * API exists (see lib/api.ts). No real orders are sent here either -
 * same guarantee the backend enforces architecturally, this file simply
 * has no networking code in it at all.
 */

let idCounter = 0;
function nextId(): string {
  idCounter += 1;
  return `paper-${idCounter}`;
}

const positions: PaperPosition[] = [
  {
    id: nextId(), symbol: "RELIANCE", direction: "LONG", entryPrice: 2905.10, quantity: 34,
    stopLoss: 2870.00, target: 2975.30, entryTime: new Date(Date.now() - 3 * 3600_000).toISOString(),
    opportunityScoreAtEntry: 87, marketCondition: "Bullish (ADX 27.4)",
    reasonForEntry: "breakout entry trigger (LONG)",
    exitTime: null, exitPrice: null, exitReason: null, pnl: null, pnlPct: null, rMultiple: null,
  },
  {
    id: nextId(), symbol: "TATASTEEL", direction: "LONG", entryPrice: 159.40, quantity: 620,
    stopLoss: 156.80, target: 164.60, entryTime: new Date(Date.now() - 1.5 * 3600_000).toISOString(),
    opportunityScoreAtEntry: 81, marketCondition: "Bullish (ADX 28.9)",
    reasonForEntry: "retest entry trigger (LONG)",
    exitTime: null, exitPrice: null, exitReason: null, pnl: null, pnlPct: null, rMultiple: null,
  },
  {
    id: nextId(), symbol: "ZOMATO", direction: "SHORT", entryPrice: 267.80, quantity: 370,
    stopLoss: 272.50, target: 253.00, entryTime: new Date(Date.now() - 6 * 3600_000).toISOString(),
    opportunityScoreAtEntry: 74, marketCondition: "Bearish (ADX 26.8)",
    reasonForEntry: "vwap_rejection entry trigger (SHORT)",
    exitTime: new Date(Date.now() - 4 * 3600_000).toISOString(), exitPrice: 253.00, exitReason: "TARGET_HIT",
    pnl: (267.80 - 253.00) * 370, pnlPct: ((267.80 - 253.00) / 267.80) * 100, rMultiple: 3.15,
  },
  {
    id: nextId(), symbol: "ADANIENT", direction: "SHORT", entryPrice: 2448.00, quantity: 40,
    stopLoss: 2495.00, target: 2358.00, entryTime: new Date(Date.now() - 8 * 3600_000).toISOString(),
    opportunityScoreAtEntry: 58, marketCondition: "Neutral (ADX 22.5)",
    reasonForEntry: "breakdown entry trigger (SHORT)",
    exitTime: new Date(Date.now() - 7 * 3600_000).toISOString(), exitPrice: 2495.00, exitReason: "STOP_LOSS_HIT",
    pnl: (2448.00 - 2495.00) * 40, pnlPct: ((2448.00 - 2495.00) / 2448.00) * 100, rMultiple: -1.0,
  },
];

export function listOpenPositions(): PaperPosition[] {
  return positions.filter((p) => p.exitTime === null);
}

export function listClosedPositions(): PaperPosition[] {
  return positions.filter((p) => p.exitTime !== null);
}

export function openMockPosition(input: {
  symbol: string;
  direction: Direction;
  entryPrice: number;
  quantity: number;
  stopLoss: number | null;
  target: number | null;
  opportunityScoreAtEntry: number | null;
  marketCondition: string | null;
  reasonForEntry: string | null;
}): PaperPosition {
  const position: PaperPosition = {
    id: nextId(),
    symbol: input.symbol,
    direction: input.direction,
    entryPrice: input.entryPrice,
    quantity: input.quantity,
    stopLoss: input.stopLoss,
    target: input.target,
    entryTime: new Date().toISOString(),
    opportunityScoreAtEntry: input.opportunityScoreAtEntry,
    marketCondition: input.marketCondition,
    reasonForEntry: input.reasonForEntry,
    exitTime: null, exitPrice: null, exitReason: null, pnl: null, pnlPct: null, rMultiple: null,
  };
  positions.unshift(position);
  return position;
}

export function closeMockPositionManually(id: string, exitPrice: number): PaperPosition | null {
  const index = positions.findIndex((p) => p.id === id);
  if (index === -1) return null;
  const position = positions[index];
  if (!position || position.exitTime !== null) return null;

  const gross =
    position.direction === "LONG"
      ? (exitPrice - position.entryPrice) * position.quantity
      : (position.entryPrice - exitPrice) * position.quantity;
  const riskPerShare =
    position.stopLoss === null
      ? null
      : position.direction === "LONG"
      ? position.entryPrice - position.stopLoss
      : position.stopLoss - position.entryPrice;

  const closed: PaperPosition = {
    ...position,
    exitTime: new Date().toISOString(),
    exitPrice,
    exitReason: "MANUAL_CLOSE",
    pnl: gross,
    pnlPct: (gross / (position.entryPrice * position.quantity)) * 100,
    rMultiple: riskPerShare && riskPerShare > 0 ? gross / position.quantity / riskPerShare : null,
  };
  positions[index] = closed;
  return closed;
}
