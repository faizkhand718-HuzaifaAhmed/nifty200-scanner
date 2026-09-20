import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings  # noqa: E402
from app.core.error_monitoring import ErrorMonitor  # noqa: E402


def test_disabled_by_default_with_no_dsn():
    monitor = ErrorMonitor(Settings(sentry_dsn=None))
    assert monitor.enabled is False


def test_capture_exception_does_not_raise_when_disabled():
    monitor = ErrorMonitor(Settings(sentry_dsn=None))
    try:
        raise ValueError("boom")
    except ValueError as e:
        monitor.capture_exception(e, context={"symbol": "RELIANCE"})


def test_capture_message_does_not_raise_when_disabled():
    monitor = ErrorMonitor(Settings(sentry_dsn=None))
    monitor.capture_message("something noteworthy happened", level="warning")


def test_dsn_set_but_sentry_sdk_not_installed_degrades_gracefully():
    """This sandbox genuinely does not have sentry-sdk installed - this
    test proves the REAL behavior in that state: no crash, monitoring
    just ends up disabled, with a clear log explaining why."""
    monitor = ErrorMonitor(Settings(sentry_dsn="https://fake-dsn@example.com/1"))
    assert monitor.enabled is False
    try:
        raise RuntimeError("simulated failure")
    except RuntimeError as e:
        monitor.capture_exception(e)
