"""
OpportunityScoringEngine: combines Phase 4 indicator values and Phase 5
setup-detection components into a single 0-100 Opportunity Score per side
(LONG/SHORT), broken down by category so every point is traceable to a
specific, already-computed signal.

WHAT THIS SCORE IS AND ISN'T (read before using it for anything):
This score measures SETUP QUALITY / SIGNAL STRENGTH - how many configured
technical conditions are currently aligned, and how strongly, given the
weights and normalization constants you've configured. It is NOT a
probability of profit, NOT a guarantee of any outcome, and has NOT yet
been validated against historical performance - that happens in the
backtesting phase, which comes later. A high score means "many favorable
technical signals are currently present", nothing more.

Category-to-signal mapping (no new trading rules invented here beyond
weighting/scaling - every input already exists from Phase 4/5):
  Trend                -> ADX trend-strength (direction-gated) + price
                          structure regime
  Volume                -> relative volume magnitude + above-average check
  VWAP                  -> % distance on the favorable side of VWAP
  Momentum               -> RSI position within the configured zone
  EMA Structure          -> EMA9-vs-20 and EMA20-vs-50 alignment
  Breakout/Breakdown     -> breakout/breakdown + retest
  Market Confirmation    -> NIFTY direction (gate) x NIFTY's own ADX (scale)
  Relative Strength      -> continuous relative-strength-vs-NIFTY value
  Risk/Volatility        -> ATR-as-%-of-price vs a configured "ideal" band
                            (direction-agnostic, same for LONG and SHORT)

Input contract: `indicators_df` is (or is shaped like) Phase 4's
IndicatorEngine.compute() output for one stock; `setup_df` is Phase 5's
SetupDetectionEngine.compute() output for the SAME rows, in the SAME
order (this engine does not re-merge/re-align them - that alignment is
Phase 5's job, already done). `nifty_indicators_df`, if given, must
likewise already be row-aligned and supplies NIFTY's own ADX for Market
Confirmation's strength scaling.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from app.scoring import components as comp
from app.scoring.config import ScoringNormalization, ScoringWeights
from app.setup_detection.config import SetupThresholds

REQUIRED_INDICATOR_COLUMNS = {"timestamp", "close", "vwap", "atr", "rsi", "adx", "plus_di", "minus_di", "relative_volume"}
REQUIRED_SETUP_COLUMNS = {
    "timestamp",
    "long_ema9_above_ema20", "long_ema20_above_ema50", "long_price_structure",
    "long_volume_confirmation", "long_breakout", "long_retest",
    "short_ema9_below_ema20", "short_ema20_below_ema50", "short_price_structure",
    "short_breakdown", "short_retest",
}
CATEGORIES = (
    "trend", "volume", "vwap", "momentum", "ema_structure",
    "breakout", "market_confirmation", "relative_strength", "risk",
)


class OpportunityScoringEngine:
    def __init__(
        self,
        weights: Optional[ScoringWeights] = None,
        normalization: Optional[ScoringNormalization] = None,
        setup_thresholds: Optional[SetupThresholds] = None,
    ):
        self.weights = weights or ScoringWeights()
        self.weights.validate()
        self.norm = normalization or ScoringNormalization()
        # Reuses the SAME thresholds Phase 5 was configured with (adx_min,
        # RSI zone bounds) so the boolean pass/fail line and the continuous
        # score never disagree about where "confirmed" starts.
        self.setup_thresholds = setup_thresholds or SetupThresholds()

    def compute(
        self,
        indicators_df: pd.DataFrame,
        setup_df: pd.DataFrame,
        nifty_indicators_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        missing_ind = REQUIRED_INDICATOR_COLUMNS - set(indicators_df.columns)
        if missing_ind:
            raise ValueError(f"indicators_df missing required columns: {sorted(missing_ind)}")
        missing_setup = REQUIRED_SETUP_COLUMNS - set(setup_df.columns)
        if missing_setup:
            raise ValueError(f"setup_df missing required columns: {sorted(missing_setup)}")
        if len(indicators_df) != len(setup_df) or (
            indicators_df["timestamp"].reset_index(drop=True) != setup_df["timestamp"].reset_index(drop=True)
        ).any():
            raise ValueError("indicators_df and setup_df must be row-aligned on timestamp, same order")

        w, n, st = self.weights, self.norm, self.setup_thresholds
        idx = indicators_df.index

        # Direction-agnostic pieces, shared by LONG and SHORT.
        volume_fraction = comp.volume_score(
            setup_df["long_volume_confirmation"], indicators_df["relative_volume"], n.relative_volume_full
        )
        risk_fraction = comp.risk_score(indicators_df["atr"], indicators_df["close"], n.ideal_atr_pct, n.atr_tolerance_pct)
        nifty_adx = nifty_indicators_df["adx"] if nifty_indicators_df is not None else pd.Series(float("nan"), index=idx)
        relative_strength = indicators_df["relative_strength"] if "relative_strength" in indicators_df.columns else None

        fractions = {
            "long": {
                "trend": comp.trend_score(
                    indicators_df["adx"], indicators_df["plus_di"], indicators_df["minus_di"],
                    setup_df["long_price_structure"], st.adx_min, n.adx_full, bullish=True,
                ),
                "volume": volume_fraction,
                "vwap": comp.vwap_score(indicators_df["close"], indicators_df["vwap"], n.vwap_distance_full_pct, bullish=True),
                "momentum": comp.momentum_score(indicators_df["rsi"], st.rsi_bullish_min, st.rsi_bullish_max),
                "ema_structure": comp.ema_structure_score(setup_df["long_ema9_above_ema20"], setup_df["long_ema20_above_ema50"]),
                "breakout": comp.breakout_score(setup_df["long_breakout"], setup_df["long_retest"]),
                "market_confirmation": comp.market_confirmation_score(
                    setup_df.get("long_market_confirmation"), nifty_adx, n.nifty_adx_full
                ),
                "relative_strength": comp.relative_strength_score(relative_strength, n.relative_strength_full, True, idx),
                "risk": risk_fraction,
            },
            "short": {
                "trend": comp.trend_score(
                    indicators_df["adx"], indicators_df["plus_di"], indicators_df["minus_di"],
                    setup_df["short_price_structure"], st.adx_min, n.adx_full, bullish=False,
                ),
                "volume": volume_fraction,
                "vwap": comp.vwap_score(indicators_df["close"], indicators_df["vwap"], n.vwap_distance_full_pct, bullish=False),
                "momentum": comp.momentum_score(indicators_df["rsi"], st.rsi_bearish_min, st.rsi_bearish_max),
                "ema_structure": comp.ema_structure_score(setup_df["short_ema9_below_ema20"], setup_df["short_ema20_below_ema50"]),
                "breakout": comp.breakout_score(setup_df["short_breakdown"], setup_df["short_retest"]),
                "market_confirmation": comp.market_confirmation_score(
                    setup_df.get("short_market_confirmation"), nifty_adx, n.nifty_adx_full
                ),
                "relative_strength": comp.relative_strength_score(relative_strength, n.relative_strength_full, False, idx),
                "risk": risk_fraction,
            },
        }

        out = pd.DataFrame(index=idx)
        out["timestamp"] = indicators_df["timestamp"].values

        weight_map = w.as_dict()
        for side in ("long", "short"):
            total = pd.Series(0.0, index=idx)
            for category in CATEGORIES:
                weight = weight_map[category]
                score = fractions[side][category].fillna(0.0) * weight
                out[f"{side}_{category}_score"] = score
                out[f"{side}_{category}_max"] = weight
                total = total + score
            out[f"{side}_score"] = total
            out[f"{side}_score_max"] = w.total()

        return out

    @staticmethod
    def breakdown(result_row: pd.Series, side: str) -> dict:
        """Returns the per-category breakdown in the "X/Y" string format
        from the phase spec, e.g. {"trend": "18.0/20", ..., "total": "91.0/100"}."""
        out = {}
        for category in CATEGORIES:
            score = result_row[f"{side}_{category}_score"]
            maxv = result_row[f"{side}_{category}_max"]
            out[category] = f"{score:.1f}/{maxv:.0f}"
        out["total"] = f"{result_row[f'{side}_score']:.1f}/{result_row[f'{side}_score_max']:.0f}"
        return out
