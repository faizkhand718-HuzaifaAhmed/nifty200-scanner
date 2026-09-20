/**
 * Alert types. Field names and enum values deliberately mirror the
 * backend exactly (see backend/app/alerts/config.py's AlertType/
 * AlertChannel and models.py's Alert) so wiring the real API later is a
 * pass-through, not a translation layer.
 */

export type AlertType =
  | "SCORE_CROSSES_80"
  | "SCORE_CROSSES_90"
  | "LONG_SETUP"
  | "SHORT_SETUP"
  | "BREAKOUT"
  | "BREAKDOWN"
  | "VWAP_RECLAIM"
  | "VWAP_REJECTION"
  | "ENTRY_TRIGGER"
  | "STOP_LOSS"
  | "TARGET";

export type AlertChannel = "DASHBOARD" | "BROWSER_NOTIFICATION" | "SOUND";

export interface Alert {
  id: string;
  symbol: string;
  alertType: AlertType;
  direction: "LONG" | "SHORT" | null;
  message: string;
  candleTimestamp: number;
  firedAt: string; // ISO timestamp
  channels: AlertChannel[];
  context?: Record<string, unknown>;
}

export const ALERT_TYPE_LABELS: Record<AlertType, string> = {
  SCORE_CROSSES_80: "Score crosses 80",
  SCORE_CROSSES_90: "Score crosses 90",
  LONG_SETUP: "LONG setup",
  SHORT_SETUP: "SHORT setup",
  BREAKOUT: "Breakout",
  BREAKDOWN: "Breakdown",
  VWAP_RECLAIM: "VWAP reclaim",
  VWAP_REJECTION: "VWAP rejection",
  ENTRY_TRIGGER: "Entry trigger",
  STOP_LOSS: "Stop loss",
  TARGET: "Target",
};

/** Which color/urgency an alert type reads as - reuses the same
 * long/short/watch semantics as the rest of the dashboard, never
 * introduces a new color meaning.
 *
 * Note this is OUTCOME-based, not direction-based, for TARGET/STOP_LOSS:
 * a SHORT trade hitting its target is a WIN and must read positive
 * (green), not red just because the trade was a short. Direction-locked
 * setup alerts (LONG_SETUP/BREAKOUT/VWAP_RECLAIM are LONG-only by
 * construction in the backend, their SHORT counterparts SHORT-only) use
 * the alert's own `direction` field for the score-crossing types, which
 * can legitimately be either side. */
export function alertTone(alert: Alert): "long" | "short" | "watch" | "neutral" {
  if (alert.alertType === "TARGET") return "long"; // good outcome, regardless of trade direction
  if (alert.alertType === "STOP_LOSS") return "short"; // bad outcome, regardless of trade direction
  if (alert.alertType === "ENTRY_TRIGGER") return "watch";

  if (alert.alertType === "LONG_SETUP" || alert.alertType === "BREAKOUT" || alert.alertType === "VWAP_RECLAIM") {
    return "long";
  }
  if (alert.alertType === "SHORT_SETUP" || alert.alertType === "BREAKDOWN" || alert.alertType === "VWAP_REJECTION") {
    return "short";
  }
  if (alert.alertType === "SCORE_CROSSES_80" || alert.alertType === "SCORE_CROSSES_90") {
    if (alert.direction === "LONG") return "long";
    if (alert.direction === "SHORT") return "short";
    return "watch";
  }
  return "neutral";
}
