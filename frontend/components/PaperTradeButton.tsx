"use client";

import { useState } from "react";
import type { ChangeEvent } from "react";
import type { RankedStock } from "@/lib/types";
import { openPaperPosition, getMarketStatus } from "@/lib/api";
import { formatPrice } from "@/lib/format";

/**
 * "When an ENTRY signal occurs, allow the user to create a virtual
 * position." This component is the "allow the user" part - it never
 * opens a position on its own; it only acts when clicked. Prefills
 * quantity/entry/stop/target/score from the stock's current data, all of
 * which already came from the backend engines (Phase 6/7/10) - nothing
 * here computes a new price or score.
 */
export function PaperTradeButton({ stock }: { stock: RankedStock }) {
  const [expanded, setExpanded] = useState(false);
  const [quantity, setQuantity] = useState(10);
  const [status, setStatus] = useState<"idle" | "submitting" | "done">("idle");

  const disabled = stock.direction === "NONE";

  async function submit() {
    setStatus("submitting");
    const marketStatus = await getMarketStatus();
    const marketCondition = `${marketStatus.direction} (ADX ${marketStatus.adx.toFixed(1)})`;

    await openPaperPosition({
      symbol: stock.symbol,
      direction: stock.direction === "SHORT" ? "SHORT" : "LONG",
      entryPrice: stock.entryPrice,
      quantity,
      stopLoss: stock.stopLoss,
      target: stock.target,
      opportunityScoreAtEntry: stock.opportunityScore,
      marketCondition,
      reasonForEntry: `${stock.direction} entry trigger, Opportunity Score ${stock.opportunityScore}/100. ${stock.setupExplanation}`,
    });
    setStatus("done");
  }

  if (disabled) {
    return (
      <button disabled className="px-3 py-1.5 rounded-md text-xs border border-border text-text-faint cursor-not-allowed">
        No valid entry signal
      </button>
    );
  }

  if (status === "done") {
    return <div className="text-xs text-long">Virtual position opened.</div>;
  }

  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="px-3 py-1.5 rounded-md text-xs border border-accent text-accent hover:bg-accent/10"
      >
        Paper trade this setup
      </button>
    );
  }

  return (
    <div className="bg-surface border border-border rounded-md p-3 text-xs space-y-2 w-64">
      <div className="text-text-dim">
        {stock.direction} {stock.symbol} @ <span className="num">{formatPrice(stock.entryPrice)}</span>
      </div>
      <div className="flex items-center gap-2">
        <label className="text-text-faint">Qty</label>
        <input
          type="number"
          min={1}
          value={quantity}
          onChange={(e: ChangeEvent<HTMLInputElement>) => setQuantity(Math.max(1, Number(e.target.value)))}
          className="num bg-surface2 border border-border rounded px-2 py-1 w-20"
        />
      </div>
      <div className="text-text-faint">
        SL <span className="num">{formatPrice(stock.stopLoss)}</span> · Target{" "}
        <span className="num">{formatPrice(stock.target)}</span>
      </div>
      <div className="flex gap-2">
        <button
          onClick={submit}
          disabled={status === "submitting"}
          className="px-3 py-1 rounded bg-accent/20 text-accent border border-accent text-xs"
        >
          {status === "submitting" ? "Opening…" : "Confirm"}
        </button>
        <button onClick={() => setExpanded(false)} className="px-3 py-1 rounded border border-border text-text-dim text-xs">
          Cancel
        </button>
      </div>
    </div>
  );
}
