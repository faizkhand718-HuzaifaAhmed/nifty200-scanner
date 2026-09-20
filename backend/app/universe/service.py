"""
Universe sync service: reconciles the canonical configuration file against
the database, handling additions and removals from an index without ever
deleting instrument history.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.db.models import IndexMembership, Instrument
from app.universe.schemas import InstrumentRecord

_UPDATABLE_FIELDS = ("company_name", "sector", "isin", "instrument_token")


@dataclass
class SyncResult:
    added: List[str] = field(default_factory=list)
    removed: List[str] = field(default_factory=list)
    updated: List[str] = field(default_factory=list)
    unchanged: List[str] = field(default_factory=list)


class UniverseService:
    def __init__(self, session: Session):
        self.session = session

    def get_active_universe(
        self, index_name: str = "NIFTY200", as_of: Optional[date] = None
    ) -> List[Instrument]:
        """Instruments that were members of `index_name` as of `as_of`
        (defaults to today). Used both by the live pipeline and by
        backtests that need the historically-correct universe for a given
        date (avoids survivorship bias)."""
        as_of = as_of or date.today()
        # effective_to is the date a membership CEASED to be active (i.e. the
        # last day it was NOT yet a member): a membership closed exactly on
        # `as_of` must already be excluded on that same date, hence strict
        # '>' rather than '>='.
        q = (
            self.session.query(Instrument)
            .join(IndexMembership)
            .filter(IndexMembership.index_name == index_name)
            .filter(IndexMembership.effective_from <= as_of)
            .filter(
                (IndexMembership.effective_to.is_(None))
                | (IndexMembership.effective_to > as_of)
            )
        )
        return q.order_by(Instrument.symbol).all()

    def sync_from_records(
        self,
        records: List[InstrumentRecord],
        index_name: str = "NIFTY200",
        as_of: Optional[date] = None,
    ) -> SyncResult:
        """
        Reconciles the DB against `records` (already validated and
        deduplicated by the loader):

          - symbol not in DB at all                 -> create Instrument
          - symbol in DB, not currently an active
            member of `index_name`                  -> open new membership
                                                         (counts as "added")
          - symbol in DB, active member, metadata
            changed                                  -> update fields
                                                         (counts as "updated")
          - symbol in DB, active member, unchanged   -> no-op
          - active member not present in `records`   -> close membership
                                                         (effective_to = as_of)

        Instruments are never deleted - only membership windows are
        opened/closed - so history is preserved for backtesting.
        """
        as_of = as_of or date.today()
        result = SyncResult()

        incoming_keys = {r.key for r in records}

        existing_instruments: Dict[Tuple[str, str], Instrument] = {
            (i.symbol, i.exchange): i for i in self.session.query(Instrument).all()
        }
        active_memberships = self._active_memberships_by_key(index_name, as_of)

        for record in records:
            key = record.key
            instrument = existing_instruments.get(key)
            is_new_instrument = instrument is None

            if is_new_instrument:
                instrument = Instrument(
                    symbol=record.symbol,
                    exchange=record.exchange,
                    company_name=record.company_name,
                    sector=record.sector,
                    isin=record.isin,
                    instrument_token=record.instrument_token,
                )
                self.session.add(instrument)
                self.session.flush()  # populate instrument.id
                existing_instruments[key] = instrument
                metadata_changed = False
            else:
                metadata_changed = self._apply_updates(instrument, record)

            membership_active = key in active_memberships
            if not membership_active:
                self.session.add(
                    IndexMembership(
                        instrument_id=instrument.id,
                        index_name=index_name,
                        effective_from=as_of,
                        effective_to=None,
                    )
                )

            label = f"{record.symbol}.{record.exchange}"
            if is_new_instrument or not membership_active:
                result.added.append(label)
            elif metadata_changed:
                result.updated.append(label)
            else:
                result.unchanged.append(label)

        # Removals: currently-active members not present in the incoming file
        for key, membership in active_memberships.items():
            if key not in incoming_keys:
                membership.effective_to = as_of
                symbol, exchange = key
                result.removed.append(f"{symbol}.{exchange}")

        self.session.commit()
        return result

    def _active_memberships_by_key(
        self, index_name: str, as_of: date
    ) -> Dict[Tuple[str, str], IndexMembership]:
        q = (
            self.session.query(IndexMembership)
            .join(Instrument)
            .filter(IndexMembership.index_name == index_name)
            .filter(IndexMembership.effective_from <= as_of)
            .filter(IndexMembership.effective_to.is_(None))
        )
        return {(m.instrument.symbol, m.instrument.exchange): m for m in q.all()}

    @staticmethod
    def _apply_updates(instrument: Instrument, record: InstrumentRecord) -> bool:
        changed = False
        for field_name in _UPDATABLE_FIELDS:
            new_value = getattr(record, field_name)
            if new_value is not None and getattr(instrument, field_name) != new_value:
                setattr(instrument, field_name, new_value)
                changed = True
        return changed
