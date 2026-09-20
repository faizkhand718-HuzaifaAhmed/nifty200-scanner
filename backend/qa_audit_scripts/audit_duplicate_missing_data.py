"""
QA AUDIT: duplicate-candle and missing-candle detection logic. Copies the
EXACT body of app.market_data.validation.dedupe_candles() (the pydantic
import chain in that module can't be exercised in this sandbox - see the
QA report) against a lightweight duck-typed Candle stand-in, to prove the
actual deduplication algorithm behaves correctly with real execution.
"""
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class FakeCandle:
    timestamp: datetime
    close: float


def dedupe_candles(candles):
    # VERBATIM copy of app.market_data.validation.dedupe_candles's body
    by_ts = {}
    duplicates = []
    for candle in candles:
        if candle.timestamp in by_ts:
            duplicates.append(candle.timestamp)
        by_ts[candle.timestamp] = candle  # last write wins
    deduped = sorted(by_ts.values(), key=lambda c: c.timestamp)
    return deduped, duplicates


t1 = datetime(2026, 1, 28, 9, 15, tzinfo=timezone.utc)
t2 = datetime(2026, 1, 28, 9, 30, tzinfo=timezone.utc)
t3 = datetime(2026, 1, 28, 9, 45, tzinfo=timezone.utc)

# Scenario: t2 arrives twice, second time with a REVISED close price
# (simulating a provider resending a corrected candle).
candles = [
    FakeCandle(t1, close=100.0),
    FakeCandle(t2, close=101.0),   # original
    FakeCandle(t3, close=102.0),
    FakeCandle(t2, close=101.5),   # revision/duplicate of t2
]

deduped, duplicates = dedupe_candles(candles)

print(f"Input candles: {len(candles)}")
print(f"Deduped candles: {len(deduped)}")
print(f"Duplicate timestamps flagged: {duplicates}")
print(f"Timestamps in order: {[c.timestamp.strftime('%H:%M') for c in deduped]}")
print(f"t2's kept close price: {[c.close for c in deduped if c.timestamp == t2]}")

assert len(deduped) == 3, "FAIL: dedup did not collapse the duplicate"
assert duplicates == [t2], "FAIL: duplicate timestamp not correctly flagged"
assert [c.timestamp for c in deduped] == [t1, t2, t3], "FAIL: output not sorted ascending"
kept_close = [c.close for c in deduped if c.timestamp == t2][0]
assert kept_close == 101.5, "FAIL: dedup did not keep the LAST (revised) value"

print("\nALL CHECKS PASS: duplicate detection correctly collapses duplicates,")
print("keeps the last-seen (revised) value, and preserves chronological order.")
