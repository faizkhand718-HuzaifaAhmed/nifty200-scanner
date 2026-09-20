import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Optional

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.options_analysis.config import ExpiryPreference, OptionSelectionConfig, StrikePreference  # noqa: E402
from app.options_analysis.contract_selection import select_contract, select_expiry  # noqa: E402


# Lightweight duck-typed stand-ins for app.market_data.schemas.OptionContract/
# OptionChain - deliberately NOT importing the real pydantic-based classes,
# since contract_selection.py only ever accesses plain attributes. This lets
# these tests actually execute without pydantic installed.
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


@dataclass
class FakeChain:
    spot_price: float
    timestamp: datetime
    contracts: List[FakeContract] = field(default_factory=list)


def liquid_contract(strike, option_type, ltp=50.0):
    return FakeContract(strike=strike, option_type=option_type, ltp=ltp, open_interest=50000, volume=5000, bid=ltp - 0.5, ask=ltp + 0.5)


def illiquid_contract(strike, option_type, ltp=50.0):
    return FakeContract(strike=strike, option_type=option_type, ltp=ltp, open_interest=100, volume=10, bid=ltp - 5, ask=ltp + 5)


CONFIG = OptionSelectionConfig(min_volume=1000, min_open_interest=5000, max_spread_pct=0.05, strike_search_radius=3)


def test_select_expiry_nearest():
    config = OptionSelectionConfig(expiry_preference=ExpiryPreference.NEAREST)
    expiries = [date(2026, 2, 5), date(2026, 2, 12), date(2026, 2, 19)]
    assert select_expiry(expiries, as_of=date(2026, 1, 28), config=config) == date(2026, 2, 5)


def test_select_expiry_next_skips_nearest():
    config = OptionSelectionConfig(expiry_preference=ExpiryPreference.NEXT)
    expiries = [date(2026, 2, 5), date(2026, 2, 12), date(2026, 2, 19)]
    assert select_expiry(expiries, as_of=date(2026, 1, 28), config=config) == date(2026, 2, 12)


def test_select_expiry_excludes_past_dates():
    config = OptionSelectionConfig()
    expiries = [date(2026, 1, 15), date(2026, 2, 5)]
    assert select_expiry(expiries, as_of=date(2026, 1, 28), config=config) == date(2026, 2, 5)


def test_select_expiry_none_when_all_past():
    config = OptionSelectionConfig()
    expiries = [date(2026, 1, 1), date(2026, 1, 15)]
    assert select_expiry(expiries, as_of=date(2026, 1, 28), config=config) is None


def test_select_contract_picks_atm_when_liquid():
    chain = FakeChain(
        spot_price=100.0,
        timestamp=datetime(2026, 1, 28, tzinfo=timezone.utc),
        contracts=[
            liquid_contract(95.0, "CE"),
            liquid_contract(100.0, "CE"),
            liquid_contract(105.0, "CE"),
        ],
    )
    contract, note = select_contract(chain, "CE", CONFIG)
    assert contract is not None
    assert contract.strike == pytest.approx(100.0)
    assert "preferred strike" in note


def test_select_contract_never_picks_cheap_illiquid_over_liquid():
    """The central requirement: a cheap illiquid ATM contract must NOT be
    selected when a liquid contract exists nearby - liquidity is a gate,
    not something a low premium can outweigh."""
    chain = FakeChain(
        spot_price=100.0,
        timestamp=datetime(2026, 1, 28, tzinfo=timezone.utc),
        contracts=[
            illiquid_contract(100.0, "CE", ltp=5.0),   # ATM, cheap, illiquid
            liquid_contract(105.0, "CE", ltp=80.0),    # one strike out, liquid, expensive
        ],
    )
    contract, note = select_contract(chain, "CE", CONFIG)
    assert contract is not None
    assert contract.strike == pytest.approx(105.0)  # NOT the cheap illiquid ATM one
    assert "fell back" in note


def test_select_contract_none_when_nothing_in_radius_is_liquid():
    chain = FakeChain(
        spot_price=100.0,
        timestamp=datetime(2026, 1, 28, tzinfo=timezone.utc),
        contracts=[illiquid_contract(s, "CE") for s in (90, 95, 100, 105, 110)],
    )
    contract, note = select_contract(chain, "CE", CONFIG)
    assert contract is None
    assert "no" in note.lower()


def test_select_contract_none_when_no_contracts_of_type():
    chain = FakeChain(spot_price=100.0, timestamp=datetime(2026, 1, 28, tzinfo=timezone.utc), contracts=[liquid_contract(100.0, "PE")])
    contract, note = select_contract(chain, "CE", CONFIG)
    assert contract is None
    assert "no ce" in note.lower()


def test_select_contract_otm_call_prefers_higher_strike():
    config = OptionSelectionConfig(strike_preference=StrikePreference.OTM, strike_offset=1, min_volume=1000, min_open_interest=5000, max_spread_pct=0.05)
    chain = FakeChain(
        spot_price=100.0,
        timestamp=datetime(2026, 1, 28, tzinfo=timezone.utc),
        contracts=[liquid_contract(s, "CE") for s in (90, 95, 100, 105, 110)],
    )
    contract, _ = select_contract(chain, "CE", config)
    assert contract.strike == pytest.approx(105.0)  # OTM call = above spot


def test_select_contract_otm_put_prefers_lower_strike():
    config = OptionSelectionConfig(strike_preference=StrikePreference.OTM, strike_offset=1, min_volume=1000, min_open_interest=5000, max_spread_pct=0.05)
    chain = FakeChain(
        spot_price=100.0,
        timestamp=datetime(2026, 1, 28, tzinfo=timezone.utc),
        contracts=[liquid_contract(s, "PE") for s in (90, 95, 100, 105, 110)],
    )
    contract, _ = select_contract(chain, "PE", config)
    assert contract.strike == pytest.approx(95.0)  # OTM put = below spot


def test_select_contract_itm_call_prefers_lower_strike():
    config = OptionSelectionConfig(strike_preference=StrikePreference.ITM, strike_offset=1, min_volume=1000, min_open_interest=5000, max_spread_pct=0.05)
    chain = FakeChain(
        spot_price=100.0,
        timestamp=datetime(2026, 1, 28, tzinfo=timezone.utc),
        contracts=[liquid_contract(s, "CE") for s in (90, 95, 100, 105, 110)],
    )
    contract, _ = select_contract(chain, "CE", config)
    assert contract.strike == pytest.approx(95.0)  # ITM call = below spot
