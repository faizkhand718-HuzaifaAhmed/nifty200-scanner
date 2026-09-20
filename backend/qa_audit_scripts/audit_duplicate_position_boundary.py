"""
QA AUDIT: Duplicate position prevention. Phase 16's RiskManager has an
explicit "prevent duplicate positions" safeguard. Phase 13's
PaperTradingEngine does NOT itself check for duplicates before opening a
position - that's intentional (RiskManager is the gatekeeper; engines
downstream of it shouldn't re-implement its checks). But this audit
verifies two things concretely:
  1. The CORRECT integration (RiskManager gates, then PaperTradingEngine
     executes) actually prevents duplicates end-to-end.
  2. What happens if PaperTradingEngine is used WITHOUT RiskManager in
     front of it - documenting this as a real, findable gap, not
     silently assuming it's fine.
"""
import sys
from datetime import date, datetime, timezone
sys.path.insert(0, "/home/claude/project/backend")

from app.risk_management.config import RiskConfig
from app.risk_management.engine import RiskManager
from app.risk_management.models import ProposedTrade
from app.paper_trading.engine import PaperTradingEngine

NOW = datetime(2026, 1, 28, 10, 0, tzinfo=timezone.utc)

print("=== Scenario 1: CORRECT integration (RiskManager gates PaperTradingEngine) ===")
risk_manager = RiskManager(RiskConfig(account_capital=100000.0), today=date(2026, 1, 28))
paper_engine = PaperTradingEngine()

proposed = ProposedTrade(symbol="RELIANCE", direction="LONG", entry_price=100.0, stop_loss=95.0, target=115.0, market_data_timestamp=NOW)

decision1 = risk_manager.evaluate_trade(proposed, now=NOW)
print(f"  1st evaluation: approved={decision1.approved}, size={decision1.position_size}")
assert decision1.approved
paper_engine.open_position("RELIANCE", "LONG", 100.0, decision1.position_size, 95.0, 115.0, entry_time=NOW)
risk_manager.record_trade_opened("RELIANCE")

decision2 = risk_manager.evaluate_trade(proposed, now=NOW)
print(f"  2nd evaluation (duplicate attempt): approved={decision2.approved}, reasons={decision2.rejection_reasons}")
assert not decision2.approved, "CRITICAL: RiskManager failed to block a duplicate!"
# Correctly-integrated caller respects the rejection and does NOT call open_position again.
open_positions = paper_engine.get_open_positions()
print(f"  PaperTradingEngine open positions in RELIANCE: {sum(1 for p in open_positions if p.symbol=='RELIANCE')}")
assert sum(1 for p in open_positions if p.symbol == "RELIANCE") == 1
print("  RESULT: correctly integrated, duplicate blocked end-to-end. OK.\n")

print("=== Scenario 2: PaperTradingEngine used standalone, WITHOUT RiskManager ===")
standalone_engine = PaperTradingEngine()
standalone_engine.open_position("TCS", "LONG", 3000.0, 10, 2950.0, 3100.0, entry_time=NOW)
standalone_engine.open_position("TCS", "LONG", 3005.0, 10, 2950.0, 3100.0, entry_time=NOW)  # same symbol, called again
tcs_positions = [p for p in standalone_engine.get_open_positions() if p.symbol == "TCS"]
print(f"  PaperTradingEngine open positions in TCS after 2 calls: {len(tcs_positions)}")
if len(tcs_positions) == 2:
    print("  FINDING (not a bug, a documented gap): PaperTradingEngine alone allows")
    print("  duplicate positions in the same symbol - duplicate prevention is")
    print("  RiskManager's responsibility, and callers MUST evaluate_trade() first.")
