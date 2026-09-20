"""
Health and readiness checks.

LIVENESS ("/health") answers "is this process alive at all" - it should
never depend on the database or any external service, since a database
outage is exactly the situation where you do NOT want the orchestrator
(Kubernetes, ECS, etc.) to conclude the process itself is broken and
kill/restart it, worsening an already-bad situation.

READINESS ("/health/ready") answers "can this process actually serve
traffic right now" - it DOES check dependencies (database, and anything
else critical), and should be used to gate whether a load balancer sends
traffic to this instance, not to decide whether to kill the process.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional


class ComponentState(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


@dataclass
class ComponentStatus:
    name: str
    state: ComponentState
    latency_ms: Optional[float] = None
    detail: Optional[str] = None


@dataclass
class HealthReport:
    healthy: bool
    components: List[ComponentStatus] = field(default_factory=list)


def liveness_check(app_version: str) -> Dict[str, str]:
    """No dependency checks by design - see module docstring."""
    return {"status": "alive", "version": app_version}


def check_database(ping_fn: Callable[[], None], timeout_seconds: float, now: Optional[Callable[[], float]] = None) -> ComponentStatus:
    """`ping_fn` should run a trivial query (e.g. `SELECT 1`) and raise on
    failure - this function doesn't know or care about SQLAlchemy
    specifically, so it's testable with any callable, including one that
    deliberately raises to simulate an outage."""
    clock = now or time.monotonic
    start = clock()
    try:
        ping_fn()
    except Exception as exc:
        return ComponentStatus(name="database", state=ComponentState.DOWN, detail=str(exc))

    elapsed_ms = (clock() - start) * 1000
    if elapsed_ms > timeout_seconds * 1000:
        return ComponentStatus(name="database", state=ComponentState.DEGRADED, latency_ms=elapsed_ms, detail="slow response")
    return ComponentStatus(name="database", state=ComponentState.OK, latency_ms=elapsed_ms)


def readiness_check(components: List[ComponentStatus]) -> HealthReport:
    healthy = all(c.state != ComponentState.DOWN for c in components)
    return HealthReport(healthy=healthy, components=components)
