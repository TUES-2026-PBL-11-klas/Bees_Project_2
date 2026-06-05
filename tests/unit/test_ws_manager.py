"""Unit tests for the AI WebSocketManager (#84)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from src.core.services.ai.ws_manager import WebSocketManager


class _FakeWebSocket:
    """Minimal stand-in for FastAPI's WebSocket — records send_text calls."""

    def __init__(self, *, raise_on_send: bool = False) -> None:
        self.accept = AsyncMock()
        self.raise_on_send = raise_on_send
        self.sent: list[str] = []

    async def send_text(self, payload: str) -> None:
        if self.raise_on_send:
            raise RuntimeError("client gone")
        self.sent.append(payload)


@pytest.mark.asyncio
async def test_connect_registers_socket_and_calls_accept():
    mgr = WebSocketManager()
    ws = _FakeWebSocket()

    await mgr.connect(ws, vessel_id="V1", company_id="C1")

    ws.accept.assert_awaited_once()
    assert mgr.active_count == 1


@pytest.mark.asyncio
async def test_disconnect_removes_socket():
    mgr = WebSocketManager()
    ws = _FakeWebSocket()
    await mgr.connect(ws)
    await mgr.disconnect(ws)
    assert mgr.active_count == 0


@pytest.mark.asyncio
async def test_broadcast_sends_to_all_connected():
    mgr = WebSocketManager()
    ws_a = _FakeWebSocket()
    ws_b = _FakeWebSocket()
    await mgr.connect(ws_a)
    await mgr.connect(ws_b)

    await mgr.broadcast({"kind": "hello"})

    assert ws_a.sent == ['{"kind": "hello"}']
    assert ws_b.sent == ['{"kind": "hello"}']


@pytest.mark.asyncio
async def test_broadcast_drops_stale_connections():
    mgr = WebSocketManager()
    healthy = _FakeWebSocket()
    stale = _FakeWebSocket(raise_on_send=True)
    await mgr.connect(healthy)
    await mgr.connect(stale)

    await mgr.broadcast({"x": 1})

    assert healthy.sent == ['{"x": 1}']
    # Stale socket is auto-disconnected.
    assert mgr.active_count == 1


@pytest.mark.asyncio
async def test_send_to_vessel_targets_matching_subscribers_and_listeners():
    mgr = WebSocketManager()
    vessel_sub = _FakeWebSocket()
    other_vessel_sub = _FakeWebSocket()
    no_filter_sub = _FakeWebSocket()

    await mgr.connect(vessel_sub, vessel_id="V1")
    await mgr.connect(other_vessel_sub, vessel_id="V2")
    await mgr.connect(no_filter_sub)  # no vessel filter → wildcard listener

    await mgr.send_to_vessel("V1", {"alert": "anomaly"})

    assert vessel_sub.sent == ['{"alert": "anomaly"}']
    assert other_vessel_sub.sent == []
    assert no_filter_sub.sent == ['{"alert": "anomaly"}']


@pytest.mark.asyncio
async def test_send_to_company_only_reaches_company_subscribers_and_listeners():
    mgr = WebSocketManager()
    company_sub = _FakeWebSocket()
    other_company_sub = _FakeWebSocket()
    no_filter_sub = _FakeWebSocket()

    await mgr.connect(company_sub, company_id="C1")
    await mgr.connect(other_company_sub, company_id="C2")
    await mgr.connect(no_filter_sub)

    await mgr.send_to_company("C1", {"billing": "invoice"})

    assert company_sub.sent == ['{"billing": "invoice"}']
    assert other_company_sub.sent == []
    assert no_filter_sub.sent == ['{"billing": "invoice"}']


def test_serialize_handles_datetimes():
    payload = WebSocketManager._serialize({"at": datetime(2026, 6, 5, 12, 0, 0)})
    assert payload == '{"at": "2026-06-05T12:00:00"}'


def test_serialize_raises_on_unknown_types():
    class Weird:
        pass

    with pytest.raises(TypeError):
        WebSocketManager._serialize({"x": Weird()})
