import type { MarketStatusSummary } from "@/lib/types";
import { formatPrice, formatPercent, changeColorClass } from "@/lib/format";

const STATE_STYLES: Record<MarketStatusSummary["state"], string> = {
  OPEN: "bg-long/10 text-long",
  PRE_OPEN: "bg-watch/10 text-watch",
  CLOSED: "bg-text-dim/10 text-text-faint",
  HOLIDAY: "bg-text-dim/10 text-text-faint",
};

const STATE_LABEL: Record<MarketStatusSummary["state"], string> = {
  OPEN: "Open",
  PRE_OPEN: "Pre-open",
  CLOSED: "Closed",
  HOLIDAY: "Holiday",
};

function Cell({ label, children, lastOnMobile }: { label: string; children: React.ReactNode; lastOnMobile?: boolean }) {
  return (
    <div className={`bg-surface px-3.5 py-2.5 ${lastOnMobile ? "col-span-2 sm:col-span-1" : ""}`}>
      <div className="text-[11px] text-text-faint mb-1">{label}</div>
      <div className="text-[15px] font-medium">{children}</div>
    </div>
  );
}

export function MarketStatusBar({ status }: { status: MarketStatusSummary }) {
  const directionColor =
    status.direction === "Bullish" ? "text-long" : status.direction === "Bearish" ? "text-short" : "text-text-dim";

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-px bg-border border border-border rounded-md overflow-hidden mb-5">
      <Cell label="Market status">
        <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${STATE_STYLES[status.state]}`}>
          {STATE_LABEL[status.state]}
        </span>
        {status.reason && <span className="ml-2 text-xs text-text-faint">{status.reason}</span>}
      </Cell>
      <Cell label="Direction">
        <span className={directionColor}>{status.direction}</span>
      </Cell>
      <Cell label="Regime">{status.regime}</Cell>
      <Cell label={status.indexName}>
        <span className="num">{formatPrice(status.price)}</span>
      </Cell>
      <Cell label="Change %">
        <span className={`num ${changeColorClass(status.changePct)}`}>{formatPercent(status.changePct)}</span>
      </Cell>
      <Cell label="VWAP">
        <span className="num">{formatPrice(status.vwap)}</span>
      </Cell>
      <Cell label="Market strength" lastOnMobile>
        <span className="num">ADX {status.adx.toFixed(1)}</span>
        <span className="ml-2 text-text-faint text-xs font-normal">{status.strengthLabel}</span>
      </Cell>
    </div>
  );
}
