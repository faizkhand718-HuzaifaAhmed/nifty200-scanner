"""
Candle data-quality utilities: duplicate detection, gap detection, timestamp
alignment, and out-of-session filtering.

These functions REPORT problems by default; they do not silently fabricate
missing data. Forward-filling a gap is a trading-relevant decision (it
invents a flat, zero-volume candle where none was actually traded) - this
module will not make that choice for you silently. Pass fill_gaps=True to
opt in explicitly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Tuple

from app.market_data.calendar import NSECalendar
from app.market_data.enums import Timeframe
from app.market_data.schemas import Candle


@dataclass
class CandleQualityReport:
    duplicate_timestamps: List[datetime] = field(default_factory=list)
    missing_timestamps: List[datetime] = field(default_factory=list)
    out_of_session_dropped: List[datetime] = field(default_factory=list)
    misaligned_dropped: List[datetime] = field(default_factory=list)
    gap_filled: List[datetime] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not (
            self.duplicate_timestamps
            or self.missing_timestamps
            or self.out_of_session_dropped
            or self.misaligned_dropped
        )


def dedupe_candles(candles: List[Candle]) -> Tuple[List[Candle], List[datetime]]:
    """Keep the LAST-seen candle for any duplicate timestamp - later entries
    in the input list are assumed to be corrections/restatements of earlier
    ones (e.g. a provider re-sending a revised candle). Returns
    (deduped_candles_sorted_by_time, timestamps_that_had_duplicates)."""
    by_ts: Dict[datetime, Candle] = {}
    duplicates: List[datetime] = []
    for candle in candles:
        if candle.timestamp in by_ts:
            duplicates.append(candle.timestamp)
        by_ts[candle.timestamp] = candle  # last write wins
    deduped = sorted(by_ts.values(), key=lambda c: c.timestamp)
    return deduped, duplicates


def validate_and_clean(
    candles: List[Candle],
    timeframe: Timeframe,
    calendar: NSECalendar,
    fill_gaps: bool = False,
) -> Tuple[List[Candle], CandleQualityReport]:
    """
    Cleans a batch of candles for a single (symbol, exchange, timeframe):

      1. Deduplicate by timestamp (keep last).
      2. Drop candles outside trading-session hours for their date, or on
         a non-trading day (weekend/holiday) - these are treated as
         incorrect timestamps, not real market data.
      3. Drop candles whose timestamp does not fall on the expected grid
         for this timeframe (misaligned - e.g. a 5m timestamp of 09:17).
      4. Detect missing timestamps against the expected session grid.
         If fill_gaps=True, insert a synthetic flat candle (O=H=L=C=
         previous close, volume=0, is_complete=True) for each gap and
         record it separately in `gap_filled` - this is never done
         silently by default.

    Returns the cleaned candle list (sorted, ascending) and a report of
    everything that was found/changed.
    """
    report = CandleQualityReport()

    deduped, duplicates = dedupe_candles(candles)
    report.duplicate_timestamps = duplicates

    kept: List[Candle] = []
    for candle in deduped:
        d = candle.date_ist
        if not calendar.is_trading_day(d):
            report.out_of_session_dropped.append(candle.timestamp)
            continue
        if timeframe.is_intraday:
            if not (calendar.session_open(d) <= candle.timestamp <= calendar.session_close(d)):
                report.out_of_session_dropped.append(candle.timestamp)
                continue

        expected_grid = set(calendar.session_timestamps(d, timeframe))
        if candle.timestamp not in expected_grid:
            report.misaligned_dropped.append(candle.timestamp)
            continue

        kept.append(candle)

    # Gap detection, grouped by trading day present in the cleaned data.
    dates_present = sorted({c.date_ist for c in kept})
    by_date: Dict[date, List[Candle]] = {}
    for c in kept:
        by_date.setdefault(c.date_ist, []).append(c)

    final: List[Candle] = []
    for d in dates_present:
        day_candles = sorted(by_date[d], key=lambda c: c.timestamp)
        expected = calendar.session_timestamps(d, timeframe)
        present_ts = {c.timestamp for c in day_candles}
        missing = [ts for ts in expected if ts not in present_ts]
        report.missing_timestamps.extend(missing)

        if not fill_gaps or not missing:
            final.extend(day_candles)
            continue

        # Opt-in forward-fill: build the full grid, carrying the last known
        # close forward into any missing slot.
        by_ts = {c.timestamp: c for c in day_candles}
        last_close: float | None = None
        filled_day: List[Candle] = []
        for ts in expected:
            if ts in by_ts:
                c = by_ts[ts]
                last_close = c.close
                filled_day.append(c)
            elif last_close is not None:
                synthetic = Candle(
                    symbol=day_candles[0].symbol,
                    exchange=day_candles[0].exchange,
                    timeframe=timeframe,
                    timestamp=ts,
                    open=last_close,
                    high=last_close,
                    low=last_close,
                    close=last_close,
                    volume=0,
                    is_complete=True,
                )
                filled_day.append(synthetic)
                report.gap_filled.append(ts)
            # If there's no prior close yet (gap at the very start of the
            # day), we cannot fabricate a plausible price - leave it out
            # rather than guessing.
        final.extend(filled_day)

    final.sort(key=lambda c: c.timestamp)
    return final, report
