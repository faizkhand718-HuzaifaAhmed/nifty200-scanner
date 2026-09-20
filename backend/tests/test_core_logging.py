import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.logging_config import (  # noqa: E402
    JSONFormatter,
    get_correlation_id,
    new_correlation_id,
    set_correlation_id,
)


def make_record(msg="hello", extra=None, level=logging.INFO):
    record = logging.LogRecord(
        name="test.logger", level=level, pathname=__file__, lineno=1, msg=msg, args=(), exc_info=None,
    )
    if extra:
        for k, v in extra.items():
            setattr(record, k, v)
    return record


def test_json_formatter_produces_valid_json_with_expected_fields():
    formatter = JSONFormatter()
    record = make_record("something happened")
    output = json.loads(formatter.format(record))
    assert output["message"] == "something happened"
    assert output["level"] == "INFO"
    assert output["logger"] == "test.logger"
    assert "timestamp" in output


def test_json_formatter_includes_extra_fields():
    formatter = JSONFormatter()
    record = make_record("order placed", extra={"symbol": "RELIANCE", "quantity": 10})
    output = json.loads(formatter.format(record))
    assert output["extra"]["symbol"] == "RELIANCE"
    assert output["extra"]["quantity"] == 10


def test_json_formatter_redacts_secret_shaped_keys():
    formatter = JSONFormatter()
    record = make_record("auth attempt", extra={"api_key": "sk-12345", "access_token": "abcxyz", "username": "trader1"})
    output = json.loads(formatter.format(record))
    assert output["extra"]["api_key"] == "[REDACTED]"
    assert output["extra"]["access_token"] == "[REDACTED]"
    assert output["extra"]["username"] == "trader1"


def test_json_formatter_redacts_nested_secrets():
    formatter = JSONFormatter()
    record = make_record("context", extra={"context": {"database_url": "postgresql://user:pass@host/db"}})
    output = json.loads(formatter.format(record))
    assert output["extra"]["context"]["database_url"] == "[REDACTED]"


def test_json_formatter_includes_correlation_id_when_set():
    set_correlation_id("abc123")
    try:
        formatter = JSONFormatter()
        output = json.loads(formatter.format(make_record("with correlation")))
        assert output["correlation_id"] == "abc123"
    finally:
        set_correlation_id(None)


def test_new_correlation_id_is_unique_and_short():
    ids = {new_correlation_id() for _ in range(100)}
    assert len(ids) == 100
    assert all(len(cid) == 16 for cid in ids)


def test_get_correlation_id_defaults_to_none():
    set_correlation_id(None)
    assert get_correlation_id() is None
