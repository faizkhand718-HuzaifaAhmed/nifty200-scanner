import type { Direction, EntryStatus } from "@/lib/types";

export function DirectionBadge({ direction }: { direction: Direction }) {
  if (direction === "LONG") {
    return (
      <span className="text-long text-xs font-medium whitespace-nowrap">
        &#9650; Long
      </span>
    );
  }
  if (direction === "SHORT") {
    return (
      <span className="text-short text-xs font-medium whitespace-nowrap">
        &#9660; Short
      </span>
    );
  }
  return <span className="text-text-faint text-xs font-medium whitespace-nowrap">&mdash; None</span>;
}

const STATUS_STYLES: Record<EntryStatus, string> = {
  READY: "bg-long/10 text-long",
  WATCH: "bg-watch/10 text-watch",
  NONE: "bg-text-dim/10 text-text-faint",
};

const STATUS_LABEL: Record<EntryStatus, string> = {
  READY: "Ready",
  WATCH: "Watch",
  NONE: "None",
};

export function StatusBadge({ status }: { status: EntryStatus }) {
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[status]}`}>
      {STATUS_LABEL[status]}
    </span>
  );
}
