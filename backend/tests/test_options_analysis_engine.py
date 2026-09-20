import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Optional

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.options_analysis.config import OptionSelectionConfig  # noqa: E402
from app.options_analysis.engine import OptionsAnalysisEngine  # noqa: E402
from app.options_analysis.liquidity import LiquidityRating  # noqa: E402
from app.options_analysis.underlying_signal import UnderlyingSignal  # noqa: E402


@dataclass
class FakeContract:
    strike: float
    option_type: str
    ltp: float
    open_interest: Optional[int] = None
    volume: Optional[int] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    change_in_open_interest: Optional[int] = None
    implied_volatility: Optional[float] = None


@dataclass
class FakeChain:
    spot_price: float
    timestamp: datetime
    contracts: List[FakeContract] = field(default_factory=list)


def liquid_contract(strike, option_type, ltp=50.0, change_oi=1200, iv=18.5):
    return FakeContract(
        strike=strike, option_type=option_type, ltp=ltp, open_interest=50000, volume=5000,
        bid=ltp - 0.5, ask=ltp + 0.5, change_in_open_interest=change_oi, implied_volatility=iv,
    )


CONFIG = OptionSelectionConfig(min_volume=1000, min_open_interest=5000, max_spread_pct=0.05)
TODAY = datetime(2026, 1, 28, tzinfo=timezone.utc)


def make_chain_by_expiry(option_type_strikes):
    """option_type_strikes: list of (strike, option_type) to populate a
    single-expiry chain with liquid contracts."""
    chain = FakeChain(spot_price=100.0, timestamp=TODAY, contracts=[liquid_contract(s, t) for s, t in option_type_strikes])
    return {date(2026, 2, 5): chain}


def test_none_direction_never_selects_a_contract():
    """THE central requirement: even with a perfectly liquid, attractive
    option chain available, a NONE-direction underlying signal must
    result in no contract selection whatsoever."""
    engine = OptionsAnalysisEngine(CONFIG)
    signal = UnderlyingSignal(symbol="RELIANCE", direction="NONE", opportunity_score=35.0)
    chain_by_expiry = make_chain_by_expiry([(s, t) for s in (90, 95, 100, 105, 110) for t in ("CE", "PE")])

    result = engine.analyze(signal, chain_by_expiry)

    assert result.option_type is None
    assert result.strike is None
    assert result.premium is None
    assert result.has_contract is False
    assert "no valid" in result.selection_note.lower()
    # underlying context is still reported, for transparency
    assert result.underlying_symbol == "RELIANCE"
    assert result.underlying_opportunity_score == pytest.approx(35.0)


def test_long_signal_selects_a_call():
    engine = OptionsAnalysisEngine(CONFIG)
    signal = UnderlyingSignal(symbol="RELIANCE", direction="LONG", opportunity_score=82.0, entry=100.0, stop=95.0, target=115.0)
    chain_by_expiry = make_chain_by_expiry([(s, t) for s in (90, 95, 100, 105, 110) for t in ("CE", "PE")])

    result = engine.analyze(signal, chain_by_expiry)

    assert result.option_type == "CE"
    assert result.strike == pytest.approx(100.0)  # ATM default
    assert result.has_contract is True
    assert result.liquidity == LiquidityRating.LIQUID
    assert result.risk_reward is not None


def test_short_signal_selects_a_put():
    engine = OptionsAnalysisEngine(CONFIG)
    signal = UnderlyingSignal(symbol="ZOMATO", direction="SHORT", opportunity_score=74.0, entry=100.0, stop=105.0, target=85.0)
    chain_by_expiry = make_chain_by_expiry([(s, t) for s in (90, 95, 100, 105, 110) for t in ("CE", "PE")])

    result = engine.analyze(signal, chain_by_expiry)

    assert result.option_type == "PE"
    assert result.strike == pytest.approx(100.0)


def test_all_13_fields_populated_on_full_success():
    engine = OptionsAnalysisEngine(CONFIG)
    signal = UnderlyingSignal(symbol="RELIANCE", direction="LONG", opportunity_score=82.0, entry=100.0, stop=95.0, target=115.0)
    chain_by_expiry = make_chain_by_expiry([(s, t) for s in (90, 95, 100, 105, 110) for t in ("CE", "PE")])

    result = engine.analyze(signal, chain_by_expiry)

    # 1-2
    assert result.underlying_direction == "LONG"
    assert result.underlying_opportunity_score == pytest.approx(82.0)
    # 3-13
    assert result.option_type == "CE"
    assert result.expiry == date(2026, 2, 5)
    assert result.strike is not None
    assert result.premium is not None
    assert result.volume is not None
    assert result.open_interest is not None
    assert result.change_in_open_interest is not None
    assert result.implied_volatility is not None
    assert result.bid is not None
    assert result.ask is not None
    assert result.spread_pct is not None
    assert result.liquidity is not None
    assert result.risk_reward is not None


def test_no_expiry_available_returns_no_contract_but_keeps_underlying_context():
    engine = OptionsAnalysisEngine(CONFIG)
    signal = UnderlyingSignal(symbol="RELIANCE", direction="LONG", opportunity_score=82.0)
    past_chain = FakeChain(spot_price=100.0, timestamp=TODAY, contracts=[liquid_contract(100.0, "CE")])
    chain_by_expiry = {date(2026, 1, 1): past_chain}  # only a PAST expiry available

    result = engine.analyze(signal, chain_by_expiry)

    assert result.option_type == "CE"  # direction was still resolved
    assert result.strike is None       # but no contract, since no valid expiry
    assert "no expiry" in result.selection_note.lower()


def test_no_liquid_contract_returns_no_contract_but_keeps_expiry_and_type():
    engine = OptionsAnalysisEngine(CONFIG)
    signal = UnderlyingSignal(symbol="RELIANCE", direction="LONG", opportunity_score=82.0)

    illiquid = FakeContract(strike=100.0, option_type="CE", ltp=5.0, open_interest=10, volume=1, bid=1.0, ask=9.0)
    chain = FakeChain(spot_price=100.0, timestamp=TODAY, contracts=[illiquid])
    chain_by_expiry = {date(2026, 2, 5): chain}

    result = engine.analyze(signal, chain_by_expiry)

    assert result.option_type == "CE"
    assert result.expiry == date(2026, 2, 5)
    assert result.strike is None
    assert result.has_contract is False


def test_engine_validates_config_on_construction():
    with pytest.raises(ValueError):
        OptionsAnalysisEngine(OptionSelectionConfig(min_volume=-1))
