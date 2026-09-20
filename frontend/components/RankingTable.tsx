"use client";

import { useRouter } from "next/navigation";
import type { RankedStock } from "@/lib/types";
import {
  formatPrice,
  formatPercent,
  formatVolume,
  formatRelativeVolume,
  formatNumber,
  changeColorClass,
} from "@/lib/format";
import { DirectionBadge, StatusBadge } from "./Badges";

export function RankingTable({ stocks }: { stocks: RankedStock[] }) {
  const router = useRouter();
  const goToDetail = (symbol: string) => router.push(`/stocks/${symbol}`);

  return (
    <>
      {/* Desktop / tablet: full table. Hidden below md - a 17-column
          table has no honest way to compress onto a phone screen without
          losing the numbers that make it useful, so mobile gets a
          purpose-built compact list instead (below). */}
      <table className="hidden md:table w-full border-collapse bg-surface border border-border rounded-lg overflow-hidden text-[13px]">
        <thead>
          <tr>
            {[
              ["Rank", "left"], ["Symbol", "left"], ["Price", "right"], ["Chg %", "right"],
              ["Volume", "right"], ["Rel Vol", "right"], ["VWAP", "right"], ["RSI", "right"],
              ["ADX", "right"], ["Trend", "right"], ["Dir", "right"], ["Score", "right"],
              ["Entry", "right"], ["SL", "right"], ["Target", "right"], ["R:R", "right"], ["Status", "right"],
            ].map(([label, align]) => (
              <th
                key={label}
                className={`px-3 py-2.5 text-[11px] font-medium text-text-faint border-b border-border whitespace-nowrap ${
                  align === "left" ? "text-left" : "text-right"
                }`}
              >
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {stocks.map((s) => (
            <tr
              key={s.symbol}
              onClick={() => goToDetail(s.symbol)}
              className="cursor-pointer hover:bg-surface2 border-b border-border last:border-b-0"
            >
              <td className="px-3 py-2.5 text-left">{s.rank}</td>
              <td className="px-3 py-2.5 text-left font-medium">
                {s.symbol} <span className="text-text-faint text-[10.5px] ml-1">{s.exchange}</span>
              </td>
              <td className="px-3 py-2.5 text-right num">{formatPrice(s.price)}</td>
              <td className={`px-3 py-2.5 text-right num ${changeColorClass(s.changePct)}`}>
                {formatPercent(s.changePct)}
              </td>
              <td className="px-3 py-2.5 text-right num">{formatVolume(s.volume)}</td>
              <td className="px-3 py-2.5 text-right num">{formatRelativeVolume(s.relativeVolume)}</td>
              <td className="px-3 py-2.5 text-right num">{formatPrice(s.vwap)}</td>
              <td className="px-3 py-2.5 text-right num">{formatNumber(s.rsi)}</td>
              <td className="px-3 py-2.5 text-right num">{formatNumber(s.adx)}</td>
              <td className="px-3 py-2.5 text-right num">{s.trend}</td>
              <td className="px-3 py-2.5 text-right">
                <DirectionBadge direction={s.direction} />
              </td>
              <td className="px-3 py-2.5 text-right num font-semibold">{s.opportunityScore}</td>
              <td className="px-3 py-2.5 text-right num">{formatPrice(s.entryPrice)}</td>
              <td className="px-3 py-2.5 text-right num">{formatPrice(s.stopLoss)}</td>
              <td className="px-3 py-2.5 text-right num">{formatPrice(s.target)}</td>
              <td className="px-3 py-2.5 text-right num">{s.riskReward !== null ? s.riskReward.toFixed(2) : "—"}</td>
              <td className="px-3 py-2.5 text-right">
                <StatusBadge status={s.entryStatus} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Mobile: compact 2-line cards. Secondary fields (volume, RSI, ADX,
          entry/SL/target...) live on the stock detail page - one tap
          away - rather than crammed into every row of a scanning list. */}
      <div className="md:hidden bg-surface border border-border rounded-lg overflow-hidden">
        {stocks.map((s) => (
          <button
            key={s.symbol}
            onClick={() => goToDetail(s.symbol)}
            className="w-full flex items-center justify-between px-3 py-3 border-b border-border last:border-b-0 text-left"
          >
            <div className="flex flex-col gap-0.5">
              <span className="text-[15px] font-medium">{s.symbol}</span>
              <DirectionBadge direction={s.direction} />
            </div>
            <div className="flex flex-col items-end gap-0.5">
              <span className="num text-[15px]">{formatPrice(s.price)}</span>
              <div className="flex items-center gap-2 text-[12px]">
                <span className={`num ${changeColorClass(s.changePct)}`}>{formatPercent(s.changePct)}</span>
                <span className="num font-semibold">{s.opportunityScore}</span>
                <StatusBadge status={s.entryStatus} />
              </div>
            </div>
          </button>
        ))}
      </div>
    </>
  );
}
