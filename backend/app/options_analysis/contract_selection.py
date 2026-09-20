"""
Contract selection. Only ever called with a real CE/PE direction already
decided (see underlying_signal.py) - this module picks WHICH contract of
that type to use, never whether to trade at all.

Uses TYPE_CHECKING-only imports of the real market-data schemas so this
module (and its tests) can run without pydantic installed - every real
value is accessed via plain attribute access (contract.strike,
contract.option_type, ...), which works identically whether the object is
a real app.market_data.schemas.OptionContract or any duck-typed
equivalent with the same fields.
"""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, List, Optional, Sequence, Tuple

from app.options_analysis.config import OptionSelectionConfig, StrikePreference
from app.options_analysis.liquidity import compute_spread_pct, passes_liquidity_filter

if TYPE_CHECKING:
    from app.market_data.schemas import OptionChain, OptionContract


def select_expiry(available_expiries: Sequence[date], as_of: date, config: OptionSelectionConfig) -> Optional[date]:
    """Returns None (never a fabricated date) if there's no expiry on or
    after `as_of`."""
    future_expiries = sorted(e for e in available_expiries if e >= as_of)
    if not future_expiries:
        return None
    if config.expiry_preference.value == "nearest":
        return future_expiries[0]
    return future_expiries[1] if len(future_expiries) > 1 else future_expiries[0]


def _target_strike_index(sorted_strikes: List[float], spot: float, option_type: str, config: OptionSelectionConfig) -> int:
    atm_strike = min(sorted_strikes, key=lambda s: abs(s - spot))
    atm_index = sorted_strikes.index(atm_strike)

    if config.strike_preference == StrikePreference.ATM:
        target = atm_index
    elif config.strike_preference == StrikePreference.ITM:
        # ITM for a call is BELOW spot (lower strikes); ITM for a put is ABOVE spot.
        target = atm_index - config.strike_offset if option_type == "CE" else atm_index + config.strike_offset
    else:  # OTM
        target = atm_index + config.strike_offset if option_type == "CE" else atm_index - config.strike_offset

    return max(0, min(len(sorted_strikes) - 1, target))


def select_contract(
    chain: "OptionChain", option_type: str, config: OptionSelectionConfig
) -> Tuple[Optional["OptionContract"], str]:
    """
    Returns (selected_contract_or_None, explanation). Searches outward
    from the preferred strike, within `strike_search_radius`, for the
    first LIQUID contract - never falls back to an illiquid contract just
    because it's the "preferred" strike or has a cheap premium. Returns
    (None, reason) if nothing in the search radius is liquid enough.
    """
    candidates = [c for c in chain.contracts if c.option_type == option_type]
    if not candidates:
        return None, f"no {option_type} contracts in this chain"

    sorted_strikes = sorted({c.strike for c in candidates})
    target_index = _target_strike_index(sorted_strikes, chain.spot_price, option_type, config)
    by_strike = {c.strike: c for c in candidates}

    tried_indices = set()
    for radius in range(config.strike_search_radius + 1):
        for idx in (target_index - radius, target_index + radius):
            if idx in tried_indices or not (0 <= idx < len(sorted_strikes)):
                continue
            tried_indices.add(idx)

            contract = by_strike.get(sorted_strikes[idx])
            if contract is None:
                continue
            spread_pct = compute_spread_pct(contract.bid, contract.ask)
            if passes_liquidity_filter(contract.volume, contract.open_interest, spread_pct, config):
                note = "preferred strike, met liquidity" if idx == target_index else f"fell back {radius} strike(s) outward for liquidity"
                return contract, note

    return None, f"no {option_type} contract within {config.strike_search_radius} strikes of the preferred one met liquidity thresholds"
