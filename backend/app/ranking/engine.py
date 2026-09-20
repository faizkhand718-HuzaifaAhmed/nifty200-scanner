"""
RankingEngine: given a per-symbol snapshot of already-computed indicator,
setup, and scoring rows (steps 1-5 of the pipeline - see pipeline.py /
scanner.py for the orchestration that actually produces these), performs
steps 6-7: determines the strongest VALID direction per symbol, computes
Entry Status and Risk/Reward, and produces the final ranked table.

This split exists so ranking LOGIC (this file) can be tested fast and in
isolation, with hand-built snapshots, without needing the full Phase 2-6
stack running in every test.

WHAT "VALID DIRECTION" MEANS HERE (a configured threshold, not an
objective truth): the side (LONG/SHORT) with the higher Opportunity Score
is the "leading" side; it's only reported as a DIRECTION if its score
clears `min_valid_score`. Below that, direction is "NONE" - the
higher-scoring side's numbers are still shown for context, just not
flagged as a valid setup.

ENTRY STATUS (also a configured threshold, not an objective truth):
  READY - leading score >= ready_score_threshold AND a breakout/breakdown
          or a confirmed retest is present on the leading side
  WATCH - leading score >= watch_score_threshold (but not READY)
  NONE  - below watch_score_threshold, or direction is NONE

TIE-BREAK for equal scores: higher relative_volume wins, then
alphabetically by symbol - chosen for determinism since this was flagged
as an open question back in Phase 1 and never resolved. Revisit if you
have a different preference.

This engine does not place, size, or execute any trade - it only ranks
and describes.
"""
from __future__ import annotations

from typing import List, Optional

import pandas as pd

from app.ranking.config import RankingConfig
from app.ranking.risk_reward import long_risk_reward, short_risk_reward
from app.scoring.engine import OpportunityScoringEngine
from app.scoring.explanation import generate_explanation


class SymbolSnapshot:
    """Thin holder for one symbol's LATEST computed rows across the
    pipeline - all real logic lives in RankingEngine, not here."""

    __slots__ = ("symbol", "indicators_row", "setup_row", "scoring_row")

    def __init__(self, symbol: str, indicators_row: pd.Series, setup_row: pd.Series, scoring_row: pd.Series):
        self.symbol = symbol
        self.indicators_row = indicators_row
        self.setup_row = setup_row
        self.scoring_row = scoring_row


class RankingEngine:
    def __init__(self, config: Optional[RankingConfig] = None):
        self.config = config or RankingConfig()

    def rank(self, snapshots: List[SymbolSnapshot]) -> pd.DataFrame:
        """Builds the full ranked table for whatever snapshots are given -
        call this again with fresh snapshots any time new market data
        arrives; there is no cached/stale state held here."""
        rows = [self._build_row(s) for s in snapshots]
        columns = [
            "rank", "symbol", "price", "change_pct", "direction", "opportunity_score",
            "trend", "volume", "vwap", "rsi", "adx", "entry_status", "entry_price",
            "stop_loss", "target", "risk_reward", "setup_explanation", "relative_volume",
        ]
        if not rows:
            return pd.DataFrame(columns=columns)

        df = pd.DataFrame(rows)
        df = df.sort_values(
            by=["opportunity_score", "relative_volume", "symbol"],
            ascending=[False, False, True],
        ).reset_index(drop=True)
        df.insert(0, "rank", range(1, len(df) + 1))
        return df[columns]

    def _build_row(self, snap: SymbolSnapshot) -> dict:
        cfg = self.config
        ind, setup, score = snap.indicators_row, snap.setup_row, snap.scoring_row

        long_score = float(score["long_score"])
        short_score = float(score["short_score"])

        if long_score >= short_score:
            side, leading_score = "LONG", long_score
        else:
            side, leading_score = "SHORT", short_score

        direction = side if leading_score >= cfg.min_valid_score else "NONE"

        breakdown = OpportunityScoringEngine.breakdown(score, side.lower())
        explanation = generate_explanation(score, side.lower())

        close = float(ind["close"])
        prev_close = ind.get("prev_day_close")
        change_pct = (
            (close - prev_close) / prev_close * 100
            if prev_close is not None and prev_close == prev_close and prev_close != 0
            else None
        )

        if side == "LONG":
            breakout_or_retest = bool(setup.get("long_breakout")) or bool(setup.get("long_retest"))
            stop, target, rr = long_risk_reward(
                close, float(ind["atr"]), ind.get("support"), ind.get("r1"), ind.get("r2"), ind.get("r3"),
                cfg.stop_atr_multiple, cfg.target_atr_multiple,
            )
        else:
            breakout_or_retest = bool(setup.get("short_breakdown")) or bool(setup.get("short_retest"))
            stop, target, rr = short_risk_reward(
                close, float(ind["atr"]), ind.get("resistance"), ind.get("s1"), ind.get("s2"), ind.get("s3"),
                cfg.stop_atr_multiple, cfg.target_atr_multiple,
            )

        if direction == "NONE":
            entry_status = "NONE"
        elif leading_score >= cfg.ready_score_threshold and breakout_or_retest:
            entry_status = "READY"
        elif leading_score >= cfg.watch_score_threshold:
            entry_status = "WATCH"
        else:
            entry_status = "NONE"

        return {
            "symbol": snap.symbol,
            "price": close,
            "change_pct": change_pct,
            "direction": direction,
            "opportunity_score": leading_score,
            "trend": breakdown["trend"],
            "volume": breakdown["volume"],
            "vwap": breakdown["vwap"],
            "rsi": float(ind["rsi"]) if ind["rsi"] == ind["rsi"] else None,
            "adx": float(ind["adx"]) if ind["adx"] == ind["adx"] else None,
            "entry_status": entry_status,
            "entry_price": close,
            "stop_loss": stop,
            "target": target,
            "risk_reward": rr,
            "setup_explanation": explanation,
            "relative_volume": float(ind["relative_volume"]) if ind["relative_volume"] == ind["relative_volume"] else 0.0,
        }
