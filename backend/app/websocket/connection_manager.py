"""
WebSocket connection tracking and heartbeat monitoring.

Deliberately framework-agnostic: this class tracks connection IDs and
heartbeat timestamps as plain data, with no dependency on FastAPI's
WebSocket type or asyncio. That's what makes it testable without FastAPI
installed (see tests/test_websocket_connection_manager.py, which runs for
real in this sandbox). app/main.py's actual WebSocket route is a thin
wrapper around this class - the route itself can only be syntax-checked
here (no FastAPI installed), but the monitoring logic it depends on is
fully executed and proven correct.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ConnectionInfo:
    connection_id: str
    connected_at: float
    last_heartbeat_at: float
    subscriptions: List[str] = field(default_factory=list)


class WebSocketConnectionManager:
    """Tracks connections and heartbeats. Does not send or receive any
    actual bytes - that's app/main.py's job, using FastAPI's WebSocket
    object. This class only answers: who's connected, how many, and who's
    gone quiet (missed heartbeats, likely a dead/stale connection)."""

    def __init__(self, heartbeat_timeout_seconds: float = 30.0):
        if heartbeat_timeout_seconds <= 0:
            raise ValueError("heartbeat_timeout_seconds must be positive")
        self.heartbeat_timeout_seconds = heartbeat_timeout_seconds
        self._connections: Dict[str, ConnectionInfo] = {}

    def connect(self, connection_id: str, now: float) -> ConnectionInfo:
        if connection_id in self._connections:
            raise ValueError(f"connection_id {connection_id!r} is already connected")
        info = ConnectionInfo(connection_id=connection_id, connected_at=now, last_heartbeat_at=now)
        self._connections[connection_id] = info
        return info

    def disconnect(self, connection_id: str) -> None:
        self._connections.pop(connection_id, None)

    def record_heartbeat(self, connection_id: str, now: float) -> None:
        info = self._connections.get(connection_id)
        if info is not None:
            info.last_heartbeat_at = now

    def subscribe(self, connection_id: str, channel: str) -> None:
        info = self._connections.get(connection_id)
        if info is not None and channel not in info.subscriptions:
            info.subscriptions.append(channel)

    def active_connection_count(self) -> int:
        return len(self._connections)

    def connections_subscribed_to(self, channel: str) -> List[str]:
        return [cid for cid, info in self._connections.items() if channel in info.subscriptions]

    def stale_connections(self, now: float) -> List[str]:
        """Connection IDs that haven't sent a heartbeat within the
        configured timeout - candidates for the caller to actually close.
        This class never closes a connection itself (no I/O), it only
        identifies which ones should be."""
        cutoff = now - self.heartbeat_timeout_seconds
        return [cid for cid, info in self._connections.items() if info.last_heartbeat_at < cutoff]

    def get(self, connection_id: str) -> Optional[ConnectionInfo]:
        return self._connections.get(connection_id)
