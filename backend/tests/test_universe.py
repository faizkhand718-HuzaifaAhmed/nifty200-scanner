import sys
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Make the `app` package importable when tests are run directly with pytest
# from the backend/ directory (no packaging/install step required).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.base import Base  # noqa: E402
from app.db.models import Instrument  # noqa: E402
from app.universe.loader import UniverseFileError, load_records  # noqa: E402
from app.universe.schemas import InstrumentRecord  # noqa: E402
from app.universe.service import UniverseService  # noqa: E402


@pytest.fixture()
def session():
    """In-memory SQLite DB per test - no live Postgres required to run tests.
    The models use only portable column types, so behavior against Postgres
    is the same."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, future=True)
    s = session_factory()
    yield s
    s.close()


def make_records(*symbols):
    return [
        InstrumentRecord(symbol=sym, exchange="NSE", company_name=f"{sym} Ltd", sector="Sample")
        for sym in symbols
    ]


# ---------------------------------------------------------------------------
# Loader tests
# ---------------------------------------------------------------------------

def test_load_valid_csv(tmp_path):
    csv_content = (
        "symbol,exchange,company_name,sector,isin,instrument_token\n"
        "RELIANCE,NSE,Reliance Industries Ltd,Energy,,\n"
        "TCS,NSE,Tata Consultancy Services Ltd,Information Technology,,\n"
    )
    f = tmp_path / "universe.csv"
    f.write_text(csv_content)

    records = load_records(f)

    assert [r.symbol for r in records] == ["RELIANCE", "TCS"]
    assert records[0].sector == "Energy"
    assert records[0].isin is None  # blank CSV cell -> None, not ""


def test_load_rejects_duplicate_symbol_within_file(tmp_path):
    csv_content = (
        "symbol,exchange,company_name\n"
        "RELIANCE,NSE,Reliance Industries Ltd\n"
        "RELIANCE,NSE,Reliance Industries Ltd\n"
    )
    f = tmp_path / "universe.csv"
    f.write_text(csv_content)

    with pytest.raises(UniverseFileError, match="Duplicate symbol"):
        load_records(f)


def test_load_allows_same_symbol_on_different_exchange(tmp_path):
    # Symbol uniqueness is per (symbol, exchange), not global.
    csv_content = (
        "symbol,exchange,company_name\n"
        "TCS,NSE,Tata Consultancy Services Ltd\n"
        "TCS,BSE,Tata Consultancy Services Ltd\n"
    )
    f = tmp_path / "universe.csv"
    f.write_text(csv_content)

    records = load_records(f)
    assert len(records) == 2


def test_load_rejects_missing_required_field(tmp_path):
    csv_content = "symbol,exchange\nRELIANCE,NSE\n"  # missing company_name
    f = tmp_path / "universe.csv"
    f.write_text(csv_content)

    with pytest.raises(UniverseFileError, match="Row 1 invalid"):
        load_records(f)


def test_load_missing_file():
    with pytest.raises(UniverseFileError, match="not found"):
        load_records("does/not/exist.csv")


def test_load_empty_file(tmp_path):
    f = tmp_path / "universe.csv"
    f.write_text("symbol,exchange,company_name\n")

    with pytest.raises(UniverseFileError, match="no records"):
        load_records(f)


def test_load_unsupported_extension(tmp_path):
    f = tmp_path / "universe.txt"
    f.write_text("not a real universe file")

    with pytest.raises(UniverseFileError, match="Unsupported universe file type"):
        load_records(f)


def test_load_valid_json(tmp_path):
    f = tmp_path / "universe.json"
    f.write_text(
        '[{"symbol": "infy", "exchange": "nse", "company_name": "Infosys Ltd"}]'
    )
    records = load_records(f)
    # symbol/exchange are normalized to upper case
    assert records[0].symbol == "INFY"
    assert records[0].exchange == "NSE"


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------

def test_sync_adds_new_instruments(session):
    service = UniverseService(session)

    result = service.sync_from_records(make_records("RELIANCE", "TCS"))

    assert set(result.added) == {"RELIANCE.NSE", "TCS.NSE"}
    assert result.removed == []
    universe = service.get_active_universe()
    assert [i.symbol for i in universe] == ["RELIANCE", "TCS"]


def test_sync_is_idempotent(session):
    service = UniverseService(session)
    service.sync_from_records(make_records("RELIANCE", "TCS"))

    result = service.sync_from_records(make_records("RELIANCE", "TCS"))

    assert result.added == []
    assert result.removed == []
    assert set(result.unchanged) == {"RELIANCE.NSE", "TCS.NSE"}


def test_sync_handles_removal_without_deleting_instrument(session):
    service = UniverseService(session)
    service.sync_from_records(make_records("RELIANCE", "TCS"))

    result = service.sync_from_records(make_records("RELIANCE"))

    assert result.removed == ["TCS.NSE"]

    # Instrument row must still exist (history preserved for backtesting)...
    instrument = session.query(Instrument).filter_by(symbol="TCS").one()
    assert instrument is not None
    # ...but it must no longer appear in the active universe.
    active_symbols = [i.symbol for i in service.get_active_universe()]
    assert "TCS" not in active_symbols


def test_sync_reopens_membership_on_re_addition(session):
    service = UniverseService(session)
    service.sync_from_records(make_records("RELIANCE", "TCS"))
    service.sync_from_records(make_records("RELIANCE"))  # TCS removed

    result = service.sync_from_records(make_records("RELIANCE", "TCS"))  # TCS re-added

    assert result.added == ["TCS.NSE"]
    active_symbols = [i.symbol for i in service.get_active_universe()]
    assert "TCS" in active_symbols

    # Two membership rows should now exist for TCS: one closed, one open.
    tcs = session.query(Instrument).filter_by(symbol="TCS").one()
    assert len(tcs.memberships) == 2


def test_sync_updates_changed_metadata(session):
    service = UniverseService(session)
    service.sync_from_records(
        [InstrumentRecord(symbol="TCS", exchange="NSE", company_name="TCS Ltd", sector="IT")]
    )

    result = service.sync_from_records(
        [InstrumentRecord(symbol="TCS", exchange="NSE", company_name="TCS Ltd", sector="Technology")]
    )

    assert result.updated == ["TCS.NSE"]
    tcs = session.query(Instrument).filter_by(symbol="TCS").one()
    assert tcs.sector == "Technology"


def test_duplicate_symbol_exchange_rejected_at_db_level(session):
    # Defense-in-depth: even if something bypasses the loader's own
    # duplicate check, the DB unique constraint must still catch it.
    session.add(Instrument(symbol="TCS", exchange="NSE", company_name="TCS Ltd"))
    session.commit()

    session.add(Instrument(symbol="TCS", exchange="NSE", company_name="Duplicate TCS"))
    with pytest.raises(Exception):
        session.commit()
    session.rollback()


def test_as_of_date_query_reflects_historical_membership(session):
    service = UniverseService(session)
    service.sync_from_records(make_records("RELIANCE", "TCS"), as_of=date(2024, 1, 1))
    service.sync_from_records(make_records("RELIANCE"), as_of=date(2024, 6, 1))  # TCS removed mid-year

    as_of_march = service.get_active_universe(as_of=date(2024, 3, 1))
    as_of_july = service.get_active_universe(as_of=date(2024, 7, 1))

    assert {i.symbol for i in as_of_march} == {"RELIANCE", "TCS"}
    assert {i.symbol for i in as_of_july} == {"RELIANCE"}


def test_instrument_token_and_isin_are_optional_and_nullable(session):
    service = UniverseService(session)
    service.sync_from_records(make_records("RELIANCE"))

    instrument = session.query(Instrument).filter_by(symbol="RELIANCE").one()
    assert instrument.isin is None
    assert instrument.instrument_token is None
