"""
QA AUDIT: Position sizing consistency across Phase 12 (backtesting) and
Phase 16 (risk_management). Both implement "Position Size = Max Risk
Amount / Stop Loss Distance" INDEPENDENTLY, on purpose, for architectural
decoupling (backtesting must not depend on risk_management and vice
versa). That deliberate duplication is itself a risk: if the two
implementations drift apart even slightly (different rounding, different
edge-case handling), a stock could be sized differently in a backtest
than it would be in live/paper risk-managed trading, which is exactly
the kind of silent inconsistency that erodes trust in the whole system.
This audit proves they agree on every case tried, including edge cases.
"""
import sys
sys.path.insert(0, "/home/claude/project/backend")

from app.backtesting.position_sizing import compute_quantity
from app.risk_management.position_sizing import compute_position_size

cases = [
    # (capital, risk_pct, entry, stop) -> both formulas should agree
    (100000.0, 0.01, 100.0, 95.0),
    (100000.0, 0.01, 100.0, 97.0),   # non-integer division -> truncation must match
    (500000.0, 0.02, 2905.10, 2870.0),
    (1000000.0, 0.005, 45.30, 44.10),
    (100000.0, 0.01, 100.0, 100.0),  # zero stop distance -> both None
    (100000.0, 0.01, 100.0, 99.999), # tiny stop distance -> both round to small qty
    (100000.0, 0.01, 50000.0, 49000.0),  # risk_amount smaller than one share's distance -> both None
]

print("Comparing app.backtesting.position_sizing.compute_quantity")
print("     vs app.risk_management.position_sizing.compute_position_size\n")

all_match = True
for capital, risk_pct, entry, stop in cases:
    backtest_qty = compute_quantity(capital, risk_pct, entry, stop)
    risk_amount = capital * risk_pct
    riskmgmt_qty = compute_position_size(risk_amount, entry, stop)
    match = backtest_qty == riskmgmt_qty
    all_match = all_match and match
    status = "OK" if match else "MISMATCH!!"
    print(f"  capital={capital:>10} risk_pct={risk_pct:<6} entry={entry:<10} stop={stop:<10}"
          f" -> backtest={backtest_qty!s:>6} risk_mgmt={riskmgmt_qty!s:>6}  [{status}]")

print(f"\n{'ALL MATCH - the two implementations are numerically consistent' if all_match else 'DIVERGENCE FOUND - CRITICAL BUG'}")
sys.exit(0 if all_match else 1)
