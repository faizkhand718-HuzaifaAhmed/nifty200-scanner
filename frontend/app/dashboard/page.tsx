"use client";

import { useEffect, useMemo, useState } from "react";
import { MarketStatusBar } from "@/components/MarketStatusBar";
import { OpportunityCard } from "@/components/OpportunityCard";
import { Top5Column } from "@/components/Top5Column";
import { FilterBar, DEFAULT_FILTERS } from "@/components/FilterBar";
import { RankingTable } from "@/components/RankingTable";
import { AlertCenter } from "@/components/AlertCenter";
import { getMarketStatus, getRankings, subscribeToLiveRankings } from "@/lib/api";
import type { MarketStatusSummary, RankedStock, RankingFilterState, ViewSize } from "@/lib/types";

export default function DashboardPage() {
  const [marketStatus, setMarketStatus] = useState<MarketStatusSummary | null>(null);
  const [allStocks, setAllStocks] = useState<RankedStock[]>([]);
  const [filters, setFilters] = useState<RankingFilterState>(DEFAULT_FILTERS);
  const [viewSize, setViewSize] = useState<ViewSize>(10);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    getMarketStatus().then(setMarketStatus);
    getRankings().then((rows) => {
      setAllStocks(rows);
      setLastUpdated(new Date());
    });

    // "Ranking must automatically update when new data arrives" - this is
    // the live-update mechanism; see lib/api.ts's subscribeToLiveRankings
    // docstring for how this becomes a real WebSocket subscription later.
    const unsubscribe = subscribeToLiveRankings((rows) => {
      setAllStocks(rows);
      setLastUpdated(new Date());
    });
    return unsubscribe;
  }, []);

  const filteredStocks = useMemo(() => {
    let rows = allStocks;
    if (filters.direction !== "ALL") rows = rows.filter((r) => r.direction === filters.direction);
    if (filters.entryStatus !== "ALL") rows = rows.filter((r) => r.entryStatus === filters.entryStatus);
    if (filters.minScore !== null) rows = rows.filter((r) => r.opportunityScore > filters.minScore!);
    if (filters.minRiskReward !== null) {
      rows = rows.filter((r) => r.riskReward !== null && r.riskReward > filters.minRiskReward!);
    }
    if (filters.minRelativeVolume !== null) {
      rows = rows.filter((r) => r.relativeVolume > filters.minRelativeVolume!);
    }
    return rows.map((r, i) => ({ ...r, rank: i + 1 }));
  }, [allStocks, filters]);

  const visibleStocks = useMemo(() => filteredStocks.slice(0, viewSize), [filteredStocks, viewSize]);

  const topLong = useMemo(
    () => allStocks.filter((s) => s.direction === "LONG").sort((a, b) => b.opportunityScore - a.opportunityScore),
    [allStocks]
  );
  const topShort = useMemo(
    () => allStocks.filter((s) => s.direction === "SHORT").sort((a, b) => b.opportunityScore - a.opportunityScore),
    [allStocks]
  );

  return (
    <div className="max-w-[1400px] mx-auto p-4">
      <header className="flex items-center justify-between pb-4 mb-4 border-b border-border">
        <div className="text-[15px] font-semibold">
          NIFTY 200 Opportunity Scanner
          <span className="text-text-dim font-normal text-xs ml-2">paper trading / analysis only</span>
        </div>
        <div className="num text-text-dim text-xs flex items-center gap-3">
          {lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString("en-IN")}` : "Loading…"}
          <a href="/paper-trading" className="text-accent hover:underline">Paper trading</a>
          <AlertCenter />
        </div>
      </header>

      {marketStatus && <MarketStatusBar status={marketStatus} />}

      <h2 className="text-[13px] font-medium text-text-dim mb-2.5">Top opportunities</h2>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mb-5">
        {topLong[0] && <OpportunityCard stock={topLong[0]} side="long" />}
        {topShort[0] && <OpportunityCard stock={topShort[0]} side="short" />}
      </div>

      <h2 className="text-[13px] font-medium text-text-dim mb-2.5">Top 5</h2>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mb-5">
        <Top5Column title="Top 5 long" stocks={topLong.slice(0, 5)} side="long" />
        <Top5Column title="Top 5 short" stocks={topShort.slice(0, 5)} side="short" />
      </div>

      <h2 className="text-[13px] font-medium text-text-dim mb-2.5">Full ranking</h2>
      <FilterBar filters={filters} onFiltersChange={setFilters} viewSize={viewSize} onViewSizeChange={setViewSize} />
      <RankingTable stocks={visibleStocks} />

      <footer className="mt-5 mb-2 p-3.5 bg-surface border border-border rounded-md text-text-dim text-xs leading-relaxed">
        This dashboard is for market analysis and paper trading. Opportunity Scores reflect
        currently aligned technical conditions and configured thresholds - they are not a
        prediction of outcome and are not validated by backtesting. Nothing here is a
        recommendation to buy or sell.
      </footer>
    </div>
  );
}
