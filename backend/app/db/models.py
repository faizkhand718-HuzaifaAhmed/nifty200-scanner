"""
SQLAlchemy models for the instrument universe.

Two tables, deliberately separated:

- Instrument: the canonical identity of a tradable security (symbol +
  exchange), independent of any index. A stock does not stop being
  "Reliance Industries" just because it temporarily leaves the NIFTY 200.

- IndexMembership: a time-boxed fact that a given instrument was part of a
  given index between effective_from and effective_to (NULL = still a
  member). This is what lets us answer "what was the NIFTY 200 universe on
  2024-01-15" for backtests, and cleanly handle additions/removals without
  ever deleting instrument history.
"""
from datetime import date

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = (
        UniqueConstraint("symbol", "exchange", name="uq_instrument_symbol_exchange"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), nullable=False, index=True)
    exchange = Column(String(16), nullable=False, default="NSE")
    company_name = Column(String(255), nullable=False)
    sector = Column(String(128), nullable=True)
    isin = Column(String(20), nullable=True)

    # Broker/vendor-specific identifier (e.g. a Kite instrument_token).
    # Nullable today - populated once a broker/data-vendor is chosen
    # (see Phase 1 architecture, section 11: broker-integration).
    instrument_token = Column(String(64), nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    memberships = relationship(
        "IndexMembership", back_populates="instrument", order_by="IndexMembership.effective_from"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid only
        return f"<Instrument {self.symbol}.{self.exchange}>"


class IndexMembership(Base):
    __tablename__ = "index_memberships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instrument_id = Column(Integer, ForeignKey("instruments.id"), nullable=False, index=True)
    index_name = Column(String(32), nullable=False, default="NIFTY200", index=True)
    effective_from = Column(Date, nullable=False, default=date.today)
    effective_to = Column(Date, nullable=True)  # NULL = currently a member
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    instrument = relationship("Instrument", back_populates="memberships")

    def __repr__(self) -> str:  # pragma: no cover - debug aid only
        status = "active" if self.effective_to is None else f"closed {self.effective_to}"
        return f"<IndexMembership instrument_id={self.instrument_id} {self.index_name} {status}>"
