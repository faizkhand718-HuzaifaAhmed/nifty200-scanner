"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getOpenPositions, getClosedPositions, getPaperTradingSummary, closePaperPositionManually } from "@/lib/api";
import type { PaperPosition, PaperTradingSummary } from "@/lib/paperTrading";
import { formatPrice, formatPercent, changeColorClass } from "@/lib/format";
import { DirectionBadge } from "@/components/Badges";

export default function PaperTradingPage() {
  const [open, setOpen] = useState<PaperPosition[]>([]);
  const [closed, setClosed] = useState<PaperPosition[]>([]);
  const [summary, setSummary] = useState<PaperTradingSummary | null>(null);

  async function refresh() {
    const [o, c, s] = await Promise.all([getOpenPositions(), getClosedPositions(), getPaperTradingSummary()]);
    setOpen(o);
    setClosed(c);
    setSummary(s);
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleManualClose(position: PaperPosition) {
    const priceStr = window.prompt(`Exit price for ${position.symbol}?`, String(position.entryPrice));
    if (!priceStr) return;
    const price = Number(priceStr);
    if (Number.isNaN(price)) return;
    await closePaperPositionManually(position.id, price);
    refresh();
  }

  return (
    <div className="max-w-[1200px] mx-auto p-4">
      <header className="flex items-center justify-between pb-4 mb-4 border-b border-border">
        <div>
          <Link href="/dashboard" className="text-text-dim text-xs hover:text-text">
            &larr; Back to dashboard
          </Link>
          <h1 className="text-lg font-semibold mt-1">Paper trading</h1>
        </div>
      </header>

      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-6">
          <SummaryCell label="Open positions" value={String(summary.openPositionsCount)} />
          <SummaryCell label="Today's P&L" value={formatPrice(summary.todaysPnl)} valueClass={changeColorClass(summary.todaysPnl)} />
          <SummaryCell label="Win rate" value={summary.winRate !== null ? `${(summary.winRate * 100).toFixed(0)}%` : "—"} />
          <SummaryCell label="Average R" value={summary.averageR !== null ? summary.averageR.toFixed(2) : "—"} />
          <SummaryCell label="Max drawdown" value={formatPrice(summary.maxDrawdown)} valueClass="text-short" />
        </div>
      )}

      <h2 className="text-[13px] font-medium text-text-dim mb-2.5">Open positions</h2>
      <div className="bg-surface border border-border rounded-lg overflow-hidden mb-6">
        {open.length === 0 ? (
          <div className="px-4 py-6 text-xs text-text-faint text-center">No open positions.</div>
        ) : (
          open.map((p) => <OpenPositionRow key={p.id} position={p} onClose={() => handleManualClose(p)} />)
        )}
      </div>

      <h2 className="text-[13px] font-medium text-text-dim mb-2.5">Closed positions</h2>
      <div className="bg-surface border border-border rounded-lg overflow-hidden">
        {closed.length === 0 ? (
          <div className="px-4 py-6 text-xs text-text-faint text-center">No closed positions yet.</div>
        ) : (
          closed.map((p) => <ClosedPositionRow key={p.id} position={p} />)
        )}
      </div>

      <footer className="mt-6 mb-2 p-3.5 bg-surface border border-border rounded-md text-text-dim text-xs leading-relaxed">
        Paper trading only. No real orders are ever sent - every position here is a virtual
        record for tracking and learning purposes.
      </footer>
    </div>
  );
}

function SummaryCell({ label, value, valueClass }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="bg-surface border border-border rounded-md p-3">
      <div className="text-[11px] text-text-faint mb-1">{label}</div>
      <div className={`num text-[15px] ${valueClass ?? ""}`}>{value}</div>
    </div>
  );
}

function OpenPositionRow({ position, onClose }: { position: PaperPosition; onClose: () => void }) {
  return (
    <div className="px-4 py-3 border-b border-border last:border-b-0">
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <span className="font-medium">{position.symbol}</span>
          <DirectionBadge direction={position.direction} />
        </div>
        <button onClick={onClose} className="text-[11px] text-text-dim border border-border rounded px-2 py-0.5 hover:text-text">
          Close manually
        </button>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-6 gap-x-3 gap-y-1 text-[12px] text-text-dim">
        <Field label="Entry" value={formatPrice(position.entryPrice)} />
        <Field label="Qty" value={String(position.quantity)} />
        <Field label="SL" value={formatPrice(position.stopLoss)} />
        <Field label="Target" value={formatPrice(position.target)} />
        <Field label="Score at entry" value={position.opportunityScoreAtEntry?.toFixed(0) ?? "—"} />
        <Field label="Market" value={position.marketCondition ?? "—"} />
      </div>
      {position.reasonForEntry && <div className="text-[11.5px] text-text-faint mt-1.5">{position.reasonForEntry}</div>}
    </div>
  );
}

function ClosedPositionRow({ position }: { position: PaperPosition }) {
  const pnlClass = changeColorClass(position.pnl);
  return (
    <div className="px-4 py-3 border-b border-border last:border-b-0">
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <span className="font-medium">{position.symbol}</span>
          <DirectionBadge direction={position.direction} />
          <span className="text-[11px] text-text-faint">{position.exitReason?.replace("_", " ")}</span>
        </div>
        <div className="text-right">
          <div className={`num text-[14px] font-semibold ${pnlClass}`}>{formatPrice(position.pnl)}</div>
          <div className={`num text-[11px] ${pnlClass}`}>{formatPercent(position.pnlPct ?? undefined)}</div>
        </div>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-6 gap-x-3 gap-y-1 text-[12px] text-text-dim">
        <Field label="Entry" value={formatPrice(position.entryPrice)} />
        <Field label="Exit" value={formatPrice(position.exitPrice)} />
        <Field label="Qty" value={String(position.quantity)} />
        <Field label="R" value={position.rMultiple !== null ? position.rMultiple.toFixed(2) : "—"} />
        <Field label="Score at entry" value={position.opportunityScoreAtEntry?.toFixed(0) ?? "—"} />
        <Field label="Market" value={position.marketCondition ?? "—"} />
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-text-faint">{label}: </span>
      <span className="num text-text">{value}</span>
    </div>
  );
}
