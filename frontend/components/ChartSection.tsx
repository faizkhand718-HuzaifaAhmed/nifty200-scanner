"use client";

import { useEffect, useState } from "react";
import { getChartData } from "@/lib/api";
import type { ChartData, OverlayKey, Timeframe } from "@/lib/candles";
import { CandlestickChart } from "./CandlestickChart";
import { TimeframeSelector } from "./TimeframeSelector";
import { OverlayToggles, DEFAULT_VISIBLE_OVERLAYS } from "./OverlayToggles";

/**
 * Loads and displays the chart for `symbol`. Mounting this component IS
 * "automatically load its chart when a stock is selected" - the stock
 * detail page (app/stocks/[symbol]/page.tsx) renders this unconditionally
 * for whichever symbol the route is for, with no extra click needed;
 * navigating here from the ranking table (Phase 8) already puts the
 * symbol in the URL.
 */
export function ChartSection({ symbol }: { symbol: string }) {
  const [timeframe, setTimeframe] = useState<Timeframe>("5m");
  const [visibleOverlays, setVisibleOverlays] = useState<Set<OverlayKey>>(DEFAULT_VISIBLE_OVERLAYS);
  const [chartData, setChartData] = useState<ChartData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getChartData(symbol, timeframe).then((data) => {
      if (!cancelled) {
        setChartData(data);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [symbol, timeframe]);

  return (
    <div>
      <div className="flex items-center justify-between mb-2.5 flex-wrap gap-2">
        <TimeframeSelector value={timeframe} onChange={setTimeframe} />
        <OverlayToggles visible={visibleOverlays} onChange={setVisibleOverlays} />
      </div>
      <div className="bg-surface border border-border rounded-lg p-2 relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center text-text-faint text-xs bg-surface/60 z-10">
            Loading chart…
          </div>
        )}
        {chartData ? (
          <CandlestickChart data={chartData} visibleOverlays={visibleOverlays} />
        ) : (
          <div className="h-[440px]" />
        )}
      </div>
    </div>
  );
}
