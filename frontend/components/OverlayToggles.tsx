"use client";

import type { OverlayKey } from "@/lib/candles";
import { OVERLAY_LABELS, OVERLAY_COLORS } from "@/lib/candles";

const ALL_OVERLAY_KEYS = Object.keys(OVERLAY_LABELS) as OverlayKey[];

export function OverlayToggles({
  visible,
  onChange,
}: {
  visible: Set<OverlayKey>;
  onChange: (next: Set<OverlayKey>) => void;
}) {
  function toggle(key: OverlayKey) {
    const next = new Set(visible);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    onChange(next);
  }

  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {ALL_OVERLAY_KEYS.map((key) => {
        const active = visible.has(key);
        return (
          <button
            key={key}
            onClick={() => toggle(key)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs border transition-colors ${
              active ? "border-text-faint text-text bg-surface2" : "border-border text-text-faint bg-surface"
            }`}
          >
            <span
              className="w-2 h-2 rounded-full shrink-0"
              style={{ background: active ? OVERLAY_COLORS[key] : "#5B6270" }}
            />
            {OVERLAY_LABELS[key]}
          </button>
        );
      })}
    </div>
  );
}

export const DEFAULT_VISIBLE_OVERLAYS = new Set<OverlayKey>(["vwap", "ema9", "ema20"]);
