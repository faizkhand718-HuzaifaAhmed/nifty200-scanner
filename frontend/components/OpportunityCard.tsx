import type { RankedStock } from "@/lib/types";
import { formatPrice, formatPercent, changeColorClass } from "@/lib/format";
import { StatusBadge } from "./Badges";
import Link from "next/link";

export function OpportunityCard({ stock, side }: { stock: RankedStock; side: "long" | "short" }) {
  const isLong = side === "long";
  const borderColor = isLong ? "border-l-long" : "border-l-short";
  const barColor = isLong ? "bg-long" : "bg-short";
  const scoreColor = isLong ? "text-long" : "text-short";
  const arrow = isLong ? "\u25B2" : "\u25BC";

  return (
    <Link
      href={`/stocks/${stock.symbol}`}
      className={`block bg-surface border border-border ${borderColor} border-l-[3px] rounded-lg p-4 hover:border-l-4 transition-[border-width]`}
    >
      <div className="text-[11px] text-text-faint mb-2">
        Top {side} opportunity
      </div>
      <div className="flex items-baseline justify-between mb-2.5">
        <div className="text-[22px] font-semibold">
          {stock.symbol} <span className={scoreColor}>{arrow}</span>
        </div>
        <div className="text-right">
          <div className="num text-lg">{formatPrice(stock.price)}</div>
          <div className={`num text-[13px] ${changeColorClass(stock.changePct)}`}>
            {formatPercent(stock.changePct)}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2.5 mb-2.5">
        <div className="flex-1 h-1.5 bg-surface2 rounded-full overflow-hidden">
          <div className={`h-full rounded-full ${barColor}`} style={{ width: `${stock.opportunityScore}%` }} />
        </div>
        <div className={`text-[15px] font-semibold min-w-[46px] text-right ${scoreColor}`}>
          {stock.opportunityScore}/100
        </div>
      </div>
      <p className="text-[12.5px] text-text-dim leading-relaxed">{stock.setupExplanation}</p>
      <div className="flex gap-4 mt-3 pt-3 border-t border-border flex-wrap">
        <MetaItem label="Entry" value={formatPrice(stock.entryPrice)} />
        <MetaItem label="SL" value={formatPrice(stock.stopLoss)} valueClass={isLong ? "text-short" : "text-long"} />
        <MetaItem label="Target" value={formatPrice(stock.target)} valueClass={isLong ? "text-long" : "text-short"} />
        <MetaItem label="R:R" value={stock.riskReward !== null ? stock.riskReward.toFixed(2) : "—"} />
        <div>
          <div className="text-[10.5px] text-text-faint mb-0.5">Status</div>
          <StatusBadge status={stock.entryStatus} />
        </div>
      </div>
    </Link>
  );
}

function MetaItem({ label, value, valueClass }: { label: string; value: string; valueClass?: string }) {
  return (
    <div>
      <div className="text-[10.5px] text-text-faint mb-0.5">{label}</div>
      <div className={`num text-[13px] ${valueClass ?? ""}`}>{value}</div>
    </div>
  );
}
