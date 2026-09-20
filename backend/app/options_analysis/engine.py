"""
OptionsAnalysisEngine: the two-step process the phase requires, made
structural rather than just described in prose:

  Step 1 (already done before this class is ever called): an
  UnderlyingSignal exists, produced by Phase 6 (score) and Phase 7/10
  (direction, entry/stop/target). This engine cannot compute one itself -
  see underlying_signal.py.

  Step 2 (this class's only job): IF the underlying signal is valid
  (direction != "NONE"), determine the appropriate option contract -
  expiry, strike, and liquidity-gated selection (contract_selection.py) -
  and assemble the full result. If the underlying signal is NOT valid,
  return a result with no contract fields populated at all, regardless of
  how attractive the option chain looks. See
  tests/test_options_analysis_engine.py's
  test_none_direction_never_selects_a_contract.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from app.options_analysis.config import OptionSelectionConfig
from app.options_analysis.contract_selection import select_contract, select_expiry
from app.options_analysis.liquidity import compute_spread_pct, rate_liquidity
from app.options_analysis.models import OptionAnalysisResult
from app.options_analysis.option_risk_reward import compute_option_risk_reward
from app.options_analysis.underlying_signal import UnderlyingSignal, direction_to_option_type

if TYPE_CHECKING:
    from app.market_data.schemas import OptionChain


class OptionsAnalysisEngine:
    def __init__(self, config: Optional[OptionSelectionConfig] = None):
        self.config = config or OptionSelectionConfig()
        self.config.validate()

    def analyze(self, signal: UnderlyingSignal, chain_by_expiry: "dict[object, OptionChain]") -> OptionAnalysisResult:
        """
        `chain_by_expiry` maps each available expiry date to the
        OptionChain for that expiry (a real provider typically returns
        one chain per expiry) - this engine picks the expiry first (via
        config.expiry_preference), then selects a contract within that
        expiry's chain.
        """
        option_type = direction_to_option_type(signal.direction)
        if option_type is None:
            return OptionAnalysisResult(
                underlying_symbol=signal.symbol,
                underlying_direction=signal.direction,
                underlying_opportunity_score=signal.opportunity_score,
                selection_note="underlying has no valid LONG/SHORT setup - no option contract considered",
            )

        available_expiries = list(chain_by_expiry.keys())
        chosen_expiry = select_expiry(available_expiries, as_of=_today_of(chain_by_expiry), config=self.config)
        if chosen_expiry is None:
            return OptionAnalysisResult(
                underlying_symbol=signal.symbol,
                underlying_direction=signal.direction,
                underlying_opportunity_score=signal.opportunity_score,
                option_type=option_type,
                selection_note="no expiry available on or after today",
            )

        chain = chain_by_expiry[chosen_expiry]
        contract, note = select_contract(chain, option_type, self.config)

        if contract is None:
            return OptionAnalysisResult(
                underlying_symbol=signal.symbol,
                underlying_direction=signal.direction,
                underlying_opportunity_score=signal.opportunity_score,
                option_type=option_type,
                expiry=chosen_expiry,
                selection_note=note,
            )

        spread_pct = compute_spread_pct(contract.bid, contract.ask)
        liquidity = rate_liquidity(contract.volume, contract.open_interest, spread_pct, self.config)
        risk_reward = compute_option_risk_reward(
            current_premium=contract.ltp, strike=contract.strike, option_type=option_type,
            underlying_stop=signal.stop, underlying_target=signal.target,
        )

        return OptionAnalysisResult(
            underlying_symbol=signal.symbol,
            underlying_direction=signal.direction,
            underlying_opportunity_score=signal.opportunity_score,
            option_type=option_type,
            expiry=chosen_expiry,
            strike=contract.strike,
            premium=contract.ltp,
            volume=contract.volume,
            open_interest=contract.open_interest,
            change_in_open_interest=contract.change_in_open_interest,
            implied_volatility=contract.implied_volatility,
            bid=contract.bid,
            ask=contract.ask,
            spread_pct=spread_pct,
            liquidity=liquidity,
            risk_reward=risk_reward,
            selection_note=note,
        )


def _today_of(chain_by_expiry: dict) -> "object":
    """Uses the earliest chain's own timestamp date as 'today' rather than
    reading the real clock, keeping this engine deterministic/testable -
    same principle as every other engine in this codebase that avoids
    calling datetime.now() internally."""
    any_chain = next(iter(chain_by_expiry.values()))
    return any_chain.timestamp.date()
