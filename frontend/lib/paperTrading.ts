/**
 * Paper trading types. Field names mirror the backend's PaperPosition
 * exactly (see backend/app/paper_trading/models.py) so wiring the real
 * API later is a pass-through, not a translation layer.
 */

export type Direction = "LONG" | "SHORT";
export type ExitReason = "TARGET_HIT" | "STOP_LOSS_HIT" | "MANUAL_CLOSE";

export interface PaperPosition {
  id: string;
  symbol: string;
  direction: Direction;
  entryPrice: number;
  quantity: number;
  stopLoss: number | null;
  target: number | null;
  entryTime: string; // ISO timestamp

  opportunityScoreAtEntry: number | null;
  marketCondition: string | null;
  reasonForEntry: string | null;

  exitTime: string | null;
  exitPrice: number | null;
  exitReason: ExitReason | null;
  pnl: number | null;
  pnlPct: number | null;
  rMultiple: number | null;
}

export interface PaperTradingSummary {
  openPositionsCount: number;
  closedPositionsCount: number;
  todaysPnl: number;
  winRate: number | null;
  averageR: number | null;
  maxDrawdown: number;
}

export function isOpen(position: PaperPosition): boolean {
  return position.exitTime === null;
}

export function isWin(position: PaperPosition): boolean | null {
  if (isOpen(position) || position.pnl === null) return null;
  return position.pnl > 0;
}
