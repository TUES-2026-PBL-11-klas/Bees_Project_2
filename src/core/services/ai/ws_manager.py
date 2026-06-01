"""
WebSocket connection manager for real-time AI notifications.

Manages client connections, supports targeted message delivery by
vessel_id or company_id, and broadcasts to all connected clients.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manages WebSocket connections for real-time AI event notifications.

    Each connection can optionally be associated with a vessel_id and/or
    company_id so that targeted messages reach only relevant clients.
    """

    def __init__(self) -> None:
        self._connections: dict[WebSocket, dict] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
        vessel_id: Optional[str] = None,
        company_id: Optional[str] = None,
    ) -> None:
        """Accept a WebSocket connection and register it with optional filters."""
        await websocket.accept()
        async with self._lock:
            self._connections[websocket] = {
                "vessel_id": vessel_id,
                "company_id": company_id,
            }
        logger.info(
            "WebSocket connected — vessel_id=%s, company_id=%s  (total: %d)",
            vessel_id,
            company_id,
            len(self._connections),
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the registry."""
        async with self._lock:
            self._connections.pop(websocket, None)
        logger.info(
            "WebSocket disconnected  (remaining: %d)", len(self._connections)
        )

    async def broadcast(self, message: dict) -> None:
        """Send *message* to every connected client."""
        payload = self._serialize(message)
        stale: list[WebSocket] = []

        async with self._lock:
            targets = list(self._connections.keys())

        for ws in targets:
            try:
                await ws.send_text(payload)
            except (WebSocketDisconnect, RuntimeError, Exception):
                stale.append(ws)

        for ws in stale:
            await self.disconnect(ws)

    async def send_to_vessel(self, vessel_id: str, message: dict) -> None:
        """
        Send *message* to clients subscribed to *vessel_id*.

        Connections with no vessel_id filter (``None``) also receive the
        message so that dashboard-wide listeners stay informed.
        """
        payload = self._serialize(message)
        stale: list[WebSocket] = []

        async with self._lock:
            targets = [
                ws
                for ws, meta in self._connections.items()
                if meta["vessel_id"] is None or meta["vessel_id"] == vessel_id
            ]

        for ws in targets:
            try:
                await ws.send_text(payload)
            except (WebSocketDisconnect, RuntimeError, Exception):
                stale.append(ws)

        for ws in stale:
            await self.disconnect(ws)

    async def send_to_company(self, company_id: str, message: dict) -> None:
        """
        Send *message* to clients subscribed to *company_id*.

        Connections with no company_id filter (``None``) also receive the
        message so that dashboard-wide listeners stay informed.
        """
        payload = self._serialize(message)
        stale: list[WebSocket] = []

        async with self._lock:
            targets = [
                ws
                for ws, meta in self._connections.items()
                if meta["company_id"] is None
                or meta["company_id"] == company_id
            ]

        for ws in targets:
            try:
                await ws.send_text(payload)
            except (WebSocketDisconnect, RuntimeError, Exception):
                stale.append(ws)

        for ws in stale:
            await self.disconnect(ws)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize(message: dict) -> str:
        """Serialise *message* to JSON, encoding datetimes as ISO-8601."""

        def _default(obj: object) -> str:
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(
                f"Object of type {type(obj).__name__} is not JSON serializable"
            )

        return json.dumps(message, default=_default)

    @property
    def active_count(self) -> int:
        """Return the number of currently connected WebSocket clients."""
        return len(self._connections)
