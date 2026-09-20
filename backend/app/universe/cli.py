"""
Command-line entrypoint to sync the instrument universe from a config file
into the database.

Usage:
    python -m app.universe.cli --file config/universe/nifty200_sample.csv --index NIFTY200

DATABASE_URL must be set in the environment (see backend/.env.example).
This does not touch any broker or place any trades - it only maintains the
`instruments` / `index_memberships` tables.
"""
from __future__ import annotations

import argparse
import sys

from app.db.session import get_engine, get_sessionmaker, init_db
from app.universe.loader import UniverseFileError, load_records
from app.universe.service import UniverseService


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync the instrument universe from a config file into the database."
    )
    parser.add_argument("--file", required=True, help="Path to the universe CSV/JSON file")
    parser.add_argument("--index", default="NIFTY200", help="Index name (default: NIFTY200)")
    args = parser.parse_args()

    try:
        records = load_records(args.file)
    except UniverseFileError as exc:
        print(f"Universe file error: {exc}", file=sys.stderr)
        return 1

    engine = get_engine()
    init_db(engine)
    session_factory = get_sessionmaker()
    with session_factory() as session:
        service = UniverseService(session)
        result = service.sync_from_records(records, index_name=args.index)

    print(f"Added:     {len(result.added)} {result.added}")
    print(f"Removed:   {len(result.removed)} {result.removed}")
    print(f"Updated:   {len(result.updated)} {result.updated}")
    print(f"Unchanged: {len(result.unchanged)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
