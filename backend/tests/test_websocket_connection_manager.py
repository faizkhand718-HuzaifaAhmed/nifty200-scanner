import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.websocket.connection_manager import WebSocketConnectionManager  # noqa: E402


def test_connect_and_count():
    manager = WebSocketConnectionManager()
    manager.connect("conn-1", now=0.0)
    manager.connect("conn-2", now=0.0)
    assert manager.active_connection_count() == 2


def test_duplicate_connection_id_raises():
    manager = WebSocketConnectionManager()
    manager.connect("conn-1", now=0.0)
    with pytest.raises(ValueError):
        manager.connect("conn-1", now=1.0)


def test_disconnect_removes_connection():
    manager = WebSocketConnectionManager()
    manager.connect("conn-1", now=0.0)
    manager.disconnect("conn-1")
    assert manager.active_connection_count() == 0


def test_disconnect_unknown_connection_is_a_no_op():
    manager = WebSocketConnectionManager()
    manager.disconnect("does-not-exist")


def test_heartbeat_updates_last_seen():
    manager = WebSocketConnectionManager()
    manager.connect("conn-1", now=0.0)
    manager.record_heartbeat("conn-1", now=15.0)
    assert manager.get("conn-1").last_heartbeat_at == 15.0


def test_stale_connections_detected_after_timeout():
    manager = WebSocketConnectionManager(heartbeat_timeout_seconds=30.0)
    manager.connect("conn-1", now=0.0)
    manager.connect("conn-2", now=0.0)
    manager.record_heartbeat("conn-2", now=40.0)

    stale = manager.stale_connections(now=45.0)
    assert stale == ["conn-1"]


def test_fresh_connections_are_not_stale():
    manager = WebSocketConnectionManager(heartbeat_timeout_seconds=30.0)
    manager.connect("conn-1", now=0.0)
    assert manager.stale_connections(now=10.0) == []


def test_subscribe_and_filter_by_channel():
    manager = WebSocketConnectionManager()
    manager.connect("conn-1", now=0.0)
    manager.connect("conn-2", now=0.0)
    manager.subscribe("conn-1", "rankings")
    manager.subscribe("conn-2", "alerts")

    assert manager.connections_subscribed_to("rankings") == ["conn-1"]
    assert manager.connections_subscribed_to("alerts") == ["conn-2"]
    assert manager.connections_subscribed_to("nonexistent-channel") == []


def test_subscribe_is_idempotent():
    manager = WebSocketConnectionManager()
    manager.connect("conn-1", now=0.0)
    manager.subscribe("conn-1", "rankings")
    manager.subscribe("conn-1", "rankings")
    assert manager.get("conn-1").subscriptions == ["rankings"]


def test_rejects_non_positive_heartbeat_timeout():
    with pytest.raises(ValueError):
        WebSocketConnectionManager(heartbeat_timeout_seconds=0.0)
