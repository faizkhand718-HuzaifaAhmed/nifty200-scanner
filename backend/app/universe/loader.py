"""
Loads and validates the universe configuration file.

This file is the single source of truth for "what is in the NIFTY 200 right
now". Editing it and re-running the sync (see cli.py / service.py) is the
only supported way to change the universe - no symbol list is ever
hard-coded elsewhere in the application.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List, Tuple, Union

from app.universe.schemas import InstrumentRecord


class UniverseFileError(ValueError):
    """Raised for structural problems in the universe config file."""


def load_records(path: Union[str, Path]) -> List[InstrumentRecord]:
    path = Path(path)
    if not path.exists():
        raise UniverseFileError(f"Universe file not found: {path}")

    if path.suffix.lower() == ".csv":
        rows = _read_csv(path)
    elif path.suffix.lower() == ".json":
        rows = _read_json(path)
    else:
        raise UniverseFileError(f"Unsupported universe file type: {path.suffix}")

    records: List[InstrumentRecord] = []
    seen: Dict[Tuple[str, str], int] = {}

    for line_no, row in enumerate(rows, start=1):
        try:
            record = InstrumentRecord(**row)
        except Exception as exc:  # pydantic ValidationError or bad row shape
            raise UniverseFileError(f"Row {line_no} invalid: {exc}") from exc

        if record.key in seen:
            raise UniverseFileError(
                f"Duplicate symbol {record.symbol}.{record.exchange} found at "
                f"rows {seen[record.key]} and {line_no}. Each symbol+exchange "
                f"combination must appear exactly once in the universe file."
            )
        seen[record.key] = line_no
        records.append(record)

    if not records:
        raise UniverseFileError("Universe file contains no records.")

    return records


def _read_csv(path: Path) -> List[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _read_json(path: Path) -> List[dict]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise UniverseFileError("JSON universe file must be a list of records.")
    return data
