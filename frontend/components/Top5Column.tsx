import Link from "next/link";
import type { RankedStock } from "@/lib/types";
import { formatPercent, changeColorClass } from "@/lib/format";

export function Top5Column({ title, stocks, side }: { title: string; stocks: RankedStock[]; side: "long" | "short" }) {
  const scoreColor = side === "long" ? "text-long" : "text-short";

  return (
    <div className="bg-surface border border-border rounded-lg overflow-hidden">
      <div className="px-3.5 py-2.5 text-xs font-medium text-text-dim border-b border-border">{title}</div>
      {stocks.length === 0 ? (
        <div className="px-3.5 py-4 text-xs text-text-faint">No {side} candidates right now.</div>
      ) : (
        stocks.map((s) => (
          <Link
            key={s.symbol}
            href={`/stocks/${s.symbol}`}
            className="flex items-center justify-between px-3.5 py-2 border-b border-border last:border-b-0 hover:bg-surface2"
          >
            <div className="flex items-center gap-2.5">
              <span className="text-text-faint text-xs w-3.5">{s.rank}</span>
              <span className="font-medium">{s.symbol}</span>
            </div>
            <div className="flex items-center gap-2.5">
              <span className={`num text-[12.5px] ${changeColorClass(s.changePct)}`}>{formatPercent(s.changePct)}</span>
              <span className={`num text-[13px] font-semibold min-w-[28px] text-right ${scoreColor}`}>
                {s.opportunityScore}
              </span>
            </div>
          </Link>
        ))
      )}
    </div>
  );
}
