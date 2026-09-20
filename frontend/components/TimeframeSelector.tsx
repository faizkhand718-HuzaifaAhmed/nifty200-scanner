"use client";

import { TIMEFRAMES, TIMEFRAME_LABELS } from "@/lib/candles";
import type { Timeframe } from "@/lib/candles";

export function TimeframeSelector({ value, onChange }: { value: Timeframe; onChange: (t: Timeframe) => void }) {
  return (
    <div className="flex gap-1">
      {TIMEFRAMES.map((tf) => (
        <button
          key={tf}
          onClick={() => onChange(tf)}
          className={`px-2.5 py-1 rounded text-xs border ${
            value === tf ? "border-text-faint text-text" : "border-border text-text-dim bg-surface"
          }`}
        >
          {TIMEFRAME_LABELS[tf]}
        </button>
      ))}
    </div>
  );
}
