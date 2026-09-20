import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.health import ComponentState, ComponentStatus, check_database, liveness_check, readiness_check  # noqa: E402


def test_liveness_check_never_touches_a_dependency():
    result = liveness_check(app_version="1.0.0")
    assert result == {"status": "alive", "version": "1.0.0"}


def test_check_database_ok_when_ping_succeeds():
    clock = iter([0.0, 0.01])  # 10ms elapsed
    status = check_database(ping_fn=lambda: None, timeout_seconds=5.0, now=lambda: next(clock))
    assert status.state == ComponentState.OK
    assert status.latency_ms == pytest.approx(10.0, abs=1.0)


def test_check_database_down_when_ping_raises():
    def failing_ping():
        raise ConnectionError("could not connect to postgres")

    status = check_database(ping_fn=failing_ping, timeout_seconds=5.0)
    assert status.state == ComponentState.DOWN
    assert "could not connect" in status.detail


def test_check_database_degraded_when_slow():
    clock = iter([0.0, 10.0])  # 10 seconds elapsed, way over a 1s timeout
    status = check_database(ping_fn=lambda: None, timeout_seconds=1.0, now=lambda: next(clock))
    assert status.state == ComponentState.DEGRADED


def test_readiness_check_healthy_when_all_components_ok():
    components = [ComponentStatus(name="database", state=ComponentState.OK, latency_ms=5.0)]
    report = readiness_check(components)
    assert report.healthy is True


def test_readiness_check_unhealthy_when_any_component_down():
    components = [ComponentStatus(name="database", state=ComponentState.DOWN, detail="connection refused")]
    report = readiness_check(components)
    assert report.healthy is False


def test_readiness_check_still_healthy_when_only_degraded():
    """A slow-but-working dependency should not take the instance out of
    the load balancer rotation the way a fully-down one should."""
    components = [ComponentStatus(name="database", state=ComponentState.DEGRADED, latency_ms=800.0)]
    report = readiness_check(components)
    assert report.healthy is True
