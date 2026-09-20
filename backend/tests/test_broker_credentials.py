import dataclasses
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.brokers.models import BrokerCredentials  # noqa: E402


def test_dataclass_field_defaults_are_none_never_a_placeholder_string():
    """The concrete, inspectable proof that no secret is baked into the
    class definition itself: every credential field's default must be
    exactly None, not an empty string or any other placeholder that
    could be mistaken for (or silently behave like) a real value."""
    for f in dataclasses.fields(BrokerCredentials):
        if f.name in ("api_key", "api_secret", "access_token"):
            assert f.default is None, f"{f.name} has a non-None default: {f.default!r}"


def test_constructing_with_no_arguments_has_no_credentials():
    credentials = BrokerCredentials()
    assert credentials.api_key is None
    assert credentials.api_secret is None
    assert credentials.access_token is None
    assert credentials.is_complete() is False


def test_from_env_reads_prefixed_variables():
    os.environ["TESTBROKER_API_KEY"] = "test-key-value"
    os.environ["TESTBROKER_API_SECRET"] = "test-secret-value"
    os.environ["TESTBROKER_ACCESS_TOKEN"] = "test-token-value"
    try:
        credentials = BrokerCredentials.from_env("TESTBROKER")
        assert credentials.api_key == "test-key-value"
        assert credentials.api_secret == "test-secret-value"
        assert credentials.access_token == "test-token-value"
        assert credentials.is_complete() is True
    finally:
        for name in ("TESTBROKER_API_KEY", "TESTBROKER_API_SECRET", "TESTBROKER_ACCESS_TOKEN"):
            os.environ.pop(name, None)


def test_from_env_missing_variables_becomes_none_not_empty_string():
    for name in ("MISSINGBROKER_API_KEY", "MISSINGBROKER_API_SECRET", "MISSINGBROKER_ACCESS_TOKEN"):
        os.environ.pop(name, None)  # ensure genuinely unset
    credentials = BrokerCredentials.from_env("MISSINGBROKER")
    assert credentials.api_key is None
    assert credentials.api_secret is None
    assert credentials.is_complete() is False


def test_is_complete_requires_both_key_and_secret():
    assert BrokerCredentials(api_key="x").is_complete() is False
    assert BrokerCredentials(api_secret="y").is_complete() is False
    assert BrokerCredentials(api_key="x", api_secret="y").is_complete() is True
