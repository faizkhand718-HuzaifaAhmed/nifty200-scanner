"""
Configuration for option contract selection. Every threshold here is a
first-draft default, not a backtested "correct" value - tune once real
options backtesting exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExpiryPreference(str, Enum):
    NEAREST = "nearest"
    NEXT = "next"  # skip the nearest expiry (avoids the most extreme theta decay right before it)


class StrikePreference(str, Enum):
    ATM = "atm"
    ITM = "itm"
    OTM = "otm"


@dataclass
class OptionSelectionConfig:
    expiry_preference: ExpiryPreference = ExpiryPreference.NEAREST
    strike_preference: StrikePreference = StrikePreference.ATM
    # How many strikes ITM/OTM from ATM to prefer (0 = exactly ATM,
    # regardless of strike_preference).
    strike_offset: int = 0
    # If the preferred strike isn't liquid enough, how many additional
    # strikes outward to search before giving up (never falls back to an
    # illiquid contract just because it's cheap or "close enough").
    strike_search_radius: int = 3

    # Liquidity gate - hard filters, not scoring inputs. A contract that
    # fails any of these is never selected, no matter how attractive its
    # premium looks.
    min_volume: int = 1000
    min_open_interest: int = 5000
    max_spread_pct: float = 0.05  # 5% of mid price

    def validate(self) -> None:
        if self.strike_offset < 0:
            raise ValueError("strike_offset must be non-negative")
        if self.strike_search_radius < 0:
            raise ValueError("strike_search_radius must be non-negative")
        if self.min_volume < 0 or self.min_open_interest < 0:
            raise ValueError("min_volume and min_open_interest must be non-negative")
        if self.max_spread_pct <= 0:
            raise ValueError("max_spread_pct must be positive")
