import Link from "next/link";
import { notFound } from "next/navigation";
import { getStockDetail, getStockBreakdown } from "@/lib/api";
import { formatPrice, formatPercent, formatVolume, formatRelativeVolume, formatNumber, changeColorClass } from "@/lib/format";
import { DirectionBadge, StatusBadge } from "@/components/Badges";
import { ChartSection } from "@/components/ChartSection";
import { PaperTradeButton } from "@/components/PaperTradeButton";

export default async function StockDetailPage({ params }: { params: { symbol: string } }) {
  const stock = await getStockDetail(params.symbol);
  if (!stock) notFound();

  const breakdown = await getStockBreakdown(params.symbol);
  const isLong = stock.direction === "LONG";

  return (
    <div className="max-w-[900px] mx-auto p-4">
      <Link href="/dashboard" className="text-text-dim text-xs hover:text-text">
        &larr; Back to dashboard
      </Link>

      <header className="flex items-start justify-between mt-3 mb-5 pb-4 border-b border-border">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-semibold">{stock.symbol}</h1>
            <span className="text-text-faint text-xs">{stock.exchange}</span>
            <DirectionBadge direction={stock.direction} />
          </div>
          <div className="flex items-center gap-3 mt-1.5">
            <span className="num text-xl">{formatPrice(stock.price)}</span>
            <span className={`num text-sm ${changeColorClass(stock.changePct)}`}>{formatPercent(stock.changePct)}</span>
          </div>
        </div>
        <div className="text-right">
          <div className="text-[11px] text-text-faint mb-1">Entry status</div>
          <StatusBadge status={stock.entryStatus} />
          <div className="mt-2">
            <PaperTradeButton stock={stock} />
          </div>
        </div>
      </header>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <Stat label="Volume" value={formatVolume(stock.volume)} />
        <Stat label="Relative volume" value={formatRelativeVolume(stock.relativeVolume)} />
        <Stat label="VWAP" value={formatPrice(stock.vwap)} />
        <Stat label="RSI" value={formatNumber(stock.rsi)} />
        <Stat label="ADX" value={formatNumber(stock.adx)} />
        <Stat label="Entry" value={formatPrice(stock.entryPrice)} />
        <Stat label="Stop loss" value={formatPrice(stock.stopLoss)} valueClass={isLong ? "text-short" : "text-long"} />
        <Stat label="Target" value={formatPrice(stock.target)} valueClass={isLong ? "text-long" : "text-short"} />
      </div>

      <section className="mb-6">
        <div className="flex items-baseline justify-between mb-3">
          <h2 className="text-[13px] font-medium text-text-dim">Opportunity score breakdown</h2>
          <span className={`num text-lg font-semibold ${isLong ? "text-long" : "text-short"}`}>
            {stock.opportunityScore}/100
          </span>
        </div>
        <div className="bg-surface border border-border rounded-lg overflow-hidden">
          {breakdown.map((b) => (
            <div key={b.category} className="flex items-center gap-3 px-4 py-2.5 border-b border-border last:border-b-0">
              <span className="w-40 text-[13px] text-text-dim shrink-0">{b.category}</span>
              <div className="flex-1 h-1.5 bg-surface2 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${isLong ? "bg-long" : "bg-short"}`}
                  style={{ width: `${(b.score / b.max) * 100}%` }}
                />
              </div>
              <span className="num text-[13px] w-16 text-right shrink-0">
                {b.score.toFixed(1)}/{b.max}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section className="mb-6">
        <h2 className="text-[13px] font-medium text-text-dim mb-2.5">Setup explanation</h2>
        <p className="bg-surface border border-border rounded-lg p-4 text-[13px] text-text-dim leading-relaxed">
          {stock.setupExplanation}
        </p>
      </section>

      <section className="mb-6">
        <h2 className="text-[13px] font-medium text-text-dim mb-2.5">Price chart</h2>
        <ChartSection symbol={stock.symbol} />
      </section>

      <footer className="mb-2 p-3.5 bg-surface border border-border rounded-md text-text-dim text-xs leading-relaxed">
        This page is for market analysis and paper trading. The Opportunity Score measures
        currently aligned technical conditions - it is not a probability of profit and has not
        been validated by backtesting. Nothing here is a recommendation to buy or sell.
      </footer>
    </div>
  );
}

function Stat({ label, value, valueClass }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="bg-surface border border-border rounded-md p-3">
      <div className="text-[11px] text-text-faint mb-1">{label}</div>
      <div className={`num text-[15px] ${valueClass ?? ""}`}>{value}</div>
    </div>
  );
}
