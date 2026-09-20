"""
Human-readable explanation generator for an Opportunity Score.

Terminology rule, enforced throughout: "Opportunity Score", "Setup
Quality", and "Signal Strength" - NEVER "probability of profit", "chance
of winning", or similar. A high score means many configured technical
conditions currently align; it is not a prediction of what will happen,
and has not been validated by backtesting (a separate, later phase).
"""
from __future__ import annotations

CATEGORY_LABELS = {
    "trend": "Trend",
    "volume": "Volume",
    "vwap": "VWAP",
    "momentum": "Momentum",
    "ema_structure": "EMA Structure",
    "breakout": "Breakout/Breakdown",
    "market_confirmation": "Market Confirmation",
    "relative_strength": "Relative Strength",
    "risk": "Risk/Volatility",
}


def generate_explanation(result_row, side: str) -> str:
    """
    Builds a short, mechanically-derived explanation of WHY the score came
    out the way it did - which categories were strongly confirmed, which
    were only partial, which weren't confirmed at all. Every sentence is
    derived directly from the numeric breakdown, nothing is inferred or
    embellished beyond what the numbers show.
    """
    total = result_row[f"{side}_score"]
    total_max = result_row[f"{side}_score_max"]

    strong, moderate, weak = [], [], []
    for key, label in CATEGORY_LABELS.items():
        score = result_row[f"{side}_{key}_score"]
        maxv = result_row[f"{side}_{key}_max"]
        if maxv <= 0:
            continue
        fraction = score / maxv
        if fraction >= 0.8:
            strong.append(label)
        elif fraction <= 0.2:
            weak.append(label)
        else:
            moderate.append(label)

    side_label = "LONG" if side == "long" else "SHORT"
    pct = (total / total_max * 100) if total_max else 0.0
    lines = [
        f"{side_label} Opportunity Score: {total:.1f}/{total_max:.0f} ({pct:.0f}%) "
        f"- a measure of current Setup Quality and Signal Strength, not a "
        f"probability of profit."
    ]
    if strong:
        lines.append("Strongly confirmed: " + ", ".join(strong) + ".")
    if moderate:
        lines.append("Partially confirmed: " + ", ".join(moderate) + ".")
    if weak:
        lines.append("Not confirmed: " + ", ".join(weak) + ".")
    lines.append(
        "This score reflects currently-aligned technical conditions only; "
        "it is not a guarantee of any outcome and has not yet been "
        "validated against historical performance."
    )
    return " ".join(lines)
