"use client";

import { useEffect, useRef } from "react";
import { createChart, CrosshairMode } from "lightweight-charts";
import type { IChartApi, ISeriesApi, UTCTimestamp } from "lightweight-charts";
import type { ChartData, OverlayKey } from "@/lib/candles";
import { OVERLAY_COLORS } from "@/lib/candles";

/**
 * Pure rendering component: every value drawn here (candles, overlay
 * lines, markers, trade-plan levels) is passed in via `data` exactly as
 * received from getChartData() - see lib/candles.ts's header comment.
 * This component performs no indicator calculation whatsoever.
 */
export function CandlestickChart({
  data,
  visibleOverlays,
}: {
  data: ChartData;
  visibleOverlays: Set<OverlayKey>;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      width: container.clientWidth,
      height: 440,
      layout: {
        background: { color: "transparent" },
        textColor: "#8B93A1",
        fontFamily: "SF Mono, Consolas, Menlo, monospace",
      },
      grid: {
        vertLines: { color: "#232935" },
        horzLines: { color: "#232935" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#232935" },
      timeScale: { borderColor: "#232935", timeVisible: true, secondsVisible: false },
    });
    chartRef.current = chart;

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#3DD68C",
      downColor: "#F0596B",
      borderVisible: false,
      wickUpColor: "#3DD68C",
      wickDownColor: "#F0596B",
    });
    candleSeries.setData(
      data.candles.map((c) => ({
        time: c.time as UTCTimestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    );

    const overlaySeries: ISeriesApi<"Line">[] = [];
    (Object.keys(data.overlays) as OverlayKey[]).forEach((key) => {
      if (!visibleOverlays.has(key)) return;
      const points = data.overlays[key];
      if (points.length === 0) return;
      const isLevelLine = key === "prevDayHigh" || key === "prevDayLow" || key === "support" || key === "resistance";
      const series = chart.addLineSeries({
        color: OVERLAY_COLORS[key],
        lineWidth: isLevelLine ? 1 : 2,
        lineStyle: isLevelLine ? 2 : 0, // dashed for fixed reference levels, solid for moving averages/VWAP
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      series.setData(points.map((p) => ({ time: p.time as UTCTimestamp, value: p.value })));
      overlaySeries.push(series);
    });

    // Trade plan: fixed horizontal reference lines, not a time series -
    // these are the CURRENT entry/stop/target from Phase 7's
    // RankingEngine output, held constant across the visible chart.
    const tradePlanSeries: ISeriesApi<"Line">[] = [];
    const addLevel = (value: number | null, color: string, title: string) => {
      if (value === null || data.candles.length === 0) return;
      const first = data.candles[0];
      const last = data.candles[data.candles.length - 1];
      if (!first || !last) return;
      const series = chart.addLineSeries({
        color,
        lineWidth: 2,
        lineStyle: 3, // dotted
        priceLineVisible: false,
        lastValueVisible: true,
        title,
      });
      series.setData([
        { time: first.time as UTCTimestamp, value },
        { time: last.time as UTCTimestamp, value },
      ]);
      tradePlanSeries.push(series);
    };
    addLevel(data.tradePlan.entry, "#4C8DFF", "Entry");
    addLevel(data.tradePlan.stopLoss, "#F0596B", "Stop loss");
    addLevel(data.tradePlan.target, "#3DD68C", "Target");

    // Buy/sell setup markers.
    candleSeries.setMarkers(
      data.markers.map((m) => ({
        time: m.time as UTCTimestamp,
        position: m.direction === "LONG" ? "belowBar" : "aboveBar",
        color: m.direction === "LONG" ? "#3DD68C" : "#F0596B",
        shape: m.direction === "LONG" ? "arrowUp" : "arrowDown",
        text: m.type === "breakout" ? "Breakout" : m.type === "breakdown" ? "Breakdown" : m.type === "retest_long" ? "Retest" : "Retest",
      }))
    );

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (container) chart.applyOptions({ width: container.clientWidth });
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, visibleOverlays]);

  return <div ref={containerRef} className="w-full" />;
}
