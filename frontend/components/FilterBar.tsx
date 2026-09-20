"use client";

import type { Direction, EntryStatus, RankingFilterState, ViewSize } from "@/lib/types";

const VIEW_SIZES: { label: string; value: ViewSize }[] = [
  { label: "Top 1", value: 1 },
  { label: "Top 3", value: 3 },
  { label: "Top 5", value: 5 },
  { label: "Top 10", value: 10 },
  { label: "Full 200", value: 200 },
];

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1 rounded-full text-xs border transition-colors ${
        active ? "border-accent text-accent bg-accent/10" : "border-border text-text-dim bg-surface hover:border-text-faint"
      }`}
    >
      {children}
    </button>
  );
}

export function FilterBar({
  filters,
  onFiltersChange,
  viewSize,
  onViewSizeChange,
}: {
  filters: RankingFilterState;
  onFiltersChange: (f: RankingFilterState) => void;
  viewSize: ViewSize;
  onViewSizeChange: (v: ViewSize) => void;
}) {
  function setDirection(d: Direction | "ALL") {
    onFiltersChange({ ...filters, direction: d });
  }
  function setEntryStatus(s: EntryStatus | "ALL") {
    onFiltersChange({ ...filters, entryStatus: s });
  }
  function toggleMinScore() {
    onFiltersChange({ ...filters, minScore: filters.minScore === 60 ? null : 60 });
  }
  function toggleMinRR() {
    onFiltersChange({ ...filters, minRiskReward: filters.minRiskReward === 2 ? null : 2 });
  }

  return (
    <div className="flex items-center gap-2 mb-2.5 flex-wrap">
      <Chip active={filters.direction === "ALL"} onClick={() => setDirection("ALL")}>
        All
      </Chip>
      <Chip active={filters.direction === "LONG"} onClick={() => setDirection("LONG")}>
        Long
      </Chip>
      <Chip active={filters.direction === "SHORT"} onClick={() => setDirection("SHORT")}>
        Short
      </Chip>
      <Chip active={filters.entryStatus === "READY"} onClick={() => setEntryStatus(filters.entryStatus === "READY" ? "ALL" : "READY")}>
        Ready
      </Chip>
      <Chip active={filters.entryStatus === "WATCH"} onClick={() => setEntryStatus(filters.entryStatus === "WATCH" ? "ALL" : "WATCH")}>
        Watch
      </Chip>
      <Chip active={filters.minScore === 60} onClick={toggleMinScore}>
        Score &gt; 60
      </Chip>
      <Chip active={filters.minRiskReward === 2} onClick={toggleMinRR}>
        R:R &gt; 2
      </Chip>

      <div className="flex-1" />

      <div className="flex gap-1">
        {VIEW_SIZES.map((v) => (
          <button
            key={v.value}
            onClick={() => onViewSizeChange(v.value)}
            className={`px-2.5 py-1 rounded text-xs border ${
              viewSize === v.value ? "border-text-faint text-text" : "border-border text-text-dim bg-surface"
            }`}
          >
            {v.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export const DEFAULT_FILTERS: RankingFilterState = {
  direction: "ALL",
  entryStatus: "ALL",
  minScore: null,
  minRiskReward: null,
  minRelativeVolume: null,
};
