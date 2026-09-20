"""
Pydantic schema for a single universe record coming from the external
configuration file (CSV/JSON). This is the boundary where malformed data is
rejected before it ever reaches the database.
"""
from __future__ import annotations

from typing import Optional, Tuple

from pydantic import BaseModel, field_validator


class InstrumentRecord(BaseModel):
    symbol: str
    exchange: str = "NSE"
    company_name: str
    sector: Optional[str] = None
    isin: Optional[str] = None
    instrument_token: Optional[str] = None

    @field_validator("symbol")
    @classmethod
    def _symbol_normalized(cls, v: str) -> str:
        v = (v or "").strip().upper()
        if not v:
            raise ValueError("symbol must not be empty")
        return v

    @field_validator("exchange")
    @classmethod
    def _exchange_normalized(cls, v: str) -> str:
        v = (v or "").strip().upper()
        if not v:
            raise ValueError("exchange must not be empty")
        return v

    @field_validator("company_name")
    @classmethod
    def _company_name_stripped(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("company_name must not be empty")
        return v

    @field_validator("sector", "isin", "instrument_token", mode="before")
    @classmethod
    def _blank_to_none(cls, v):
        # CSV parsers yield "" for empty optional cells - treat as absent.
        if v is None:
            return None
        v = str(v).strip()
        return v or None

    @property
    def key(self) -> Tuple[str, str]:
        """Natural key: a symbol is unique per exchange, not globally."""
        return (self.symbol, self.exchange)
