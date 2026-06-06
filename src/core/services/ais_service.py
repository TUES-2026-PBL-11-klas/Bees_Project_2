"""
Live AIS vessel positions.

Connects to AISStream.io's public WebSocket feed and keeps an in-memory
cache of the most recent position report per MMSI. The endpoint layer
(``src/api/v1/routers/ais.py``) then serves bbox-filtered snapshots to
the map UI.

Design notes
------------
* **One persistent WebSocket** owned by the FastAPI lifespan task. Map
  clients poll the REST endpoint instead of opening their own sockets,
  so we never multiply the upstream load by the number of viewers.
* **Stateless cache** keyed by MMSI. Older than ``MAX_AGE_SECONDS`` is
  evicted on read, so a closed shipping lane disappears from the map
  even if the WebSocket stays open.
* **Graceful degrade**: if ``AIS_API_KEY`` is unset the consumer never
  starts and the endpoint returns a clear 503 with instructions, rather
  than failing in some confusing place inside the WebSocket library.

The AISStream message format is documented at
https://aisstream.io/documentation; we extract just the fields the map
actually needs (lat, lon, course, speed, name, type).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Optional

logger = logging.getLogger(__name__)


AISSTREAM_WS_URL = "wss://stream.aisstream.io/v0/stream"
MAX_AGE_SECONDS = 600              # evict reports older than 10 min
DEFAULT_BBOX = [[-90.0, -180.0], [90.0, 180.0]]  # world-wide subscription


@dataclass
class AISPosition:
    mmsi: int
    lat: float
    lon: float
    sog: Optional[float] = None       # speed over ground, knots
    cog: Optional[float] = None       # course over ground, degrees
    heading: Optional[float] = None
    name: Optional[str] = None
    ship_type: Optional[int] = None
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mmsi":       self.mmsi,
            "lat":        round(self.lat, 5),
            "lon":        round(self.lon, 5),
            "sog":        self.sog,
            "cog":        self.cog,
            "heading":    self.heading,
            "name":       self.name,
            "ship_type":  self.ship_type,
            "updated_at": self.updated_at,
        }


class AISCache:
    """Thread-safe most-recent-position-per-MMSI cache."""

    def __init__(self, max_age_seconds: int = MAX_AGE_SECONDS) -> None:
        self._lock = RLock()
        self._positions: dict[int, AISPosition] = {}
        self._max_age = max_age_seconds

    def upsert(self, pos: AISPosition) -> None:
        with self._lock:
            self._positions[pos.mmsi] = pos

    def snapshot(
        self,
        *,
        bbox: Optional[tuple[float, float, float, float]] = None,
        limit: int = 2000,
    ) -> list[AISPosition]:
        """Return positions within the bbox (lat_min, lon_min, lat_max, lon_max)."""
        cutoff = time.time() - self._max_age
        with self._lock:
            # Evict stale entries lazily on read.
            stale = [m for m, p in self._positions.items() if p.updated_at < cutoff]
            for m in stale:
                del self._positions[m]

            if not bbox:
                items = list(self._positions.values())
            else:
                lat_min, lon_min, lat_max, lon_max = bbox
                items = [
                    p for p in self._positions.values()
                    if lat_min <= p.lat <= lat_max and lon_min <= p.lon <= lon_max
                ]

        items.sort(key=lambda p: p.updated_at, reverse=True)
        return items[:limit]

    def size(self) -> int:
        with self._lock:
            return len(self._positions)


# Module-level singleton — the WebSocket consumer writes to this, the
# REST endpoint reads from it.
cache = AISCache()


# ---------------------------------------------------------------------------
# Message parsing
# ---------------------------------------------------------------------------

def _extract_position(message: dict[str, Any]) -> Optional[AISPosition]:
    """
    Pull the fields the UI needs out of an AISStream envelope.

    AISStream wraps the actual report in ``{"MessageType": "...", "Message": {...}}``.
    We only act on ``PositionReport`` (types 1/2/3 in the raw spec) and ignore
    static metadata for now.
    """
    msg_type = message.get("MessageType")
    body = message.get("Message", {})
    if not body:
        return None

    if msg_type == "PositionReport":
        report = body.get("PositionReport") or {}
        meta = message.get("MetaData") or {}
        mmsi = report.get("UserID") or meta.get("MMSI")
        lat = report.get("Latitude")
        lon = report.get("Longitude")
        if mmsi is None or lat is None or lon is None:
            return None
        return AISPosition(
            mmsi=int(mmsi),
            lat=float(lat),
            lon=float(lon),
            sog=_coerce_float(report.get("Sog")),
            cog=_coerce_float(report.get("Cog")),
            heading=_coerce_float(report.get("TrueHeading")),
            name=(meta.get("ShipName") or "").strip() or None,
        )

    if msg_type == "ShipStaticData":
        # Static data doesn't give us a position by itself but it does refresh
        # the human-readable name on top of an existing position record.
        static = body.get("ShipStaticData") or {}
        meta = message.get("MetaData") or {}
        mmsi = static.get("UserID") or meta.get("MMSI")
        if mmsi is None:
            return None
        existing = cache._positions.get(int(mmsi))  # noqa: SLF001
        if existing is None:
            return None
        new_name = (static.get("Name") or meta.get("ShipName") or "").strip() or existing.name
        new_type = static.get("Type") or existing.ship_type
        return AISPosition(
            mmsi=existing.mmsi,
            lat=existing.lat,
            lon=existing.lon,
            sog=existing.sog,
            cog=existing.cog,
            heading=existing.heading,
            name=new_name,
            ship_type=new_type,
            updated_at=existing.updated_at,
        )

    return None


def _coerce_float(value: Any) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# WebSocket consumer
# ---------------------------------------------------------------------------

class AISStreamConsumer:
    """
    Long-lived WebSocket consumer for AISStream.io.

    Run via ``await AISStreamConsumer(api_key).run()`` from a background
    task; reconnects with exponential backoff on disconnect.
    """

    def __init__(
        self,
        api_key: str,
        *,
        bbox: Optional[list[list[float]]] = None,
    ) -> None:
        self.api_key = api_key
        self.bbox = bbox or DEFAULT_BBOX
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        try:
            import websockets  # pragma: no cover (network dep)
        except ImportError:
            logger.warning(
                "AISStreamConsumer skipped: the 'websockets' package is not installed. "
                "Run `pip install websockets` to enable live AIS."
            )
            return

        backoff = 2.0
        while not self._stop.is_set():
            try:
                async with websockets.connect(
                    AISSTREAM_WS_URL, max_size=2**22, ping_interval=20
                ) as ws:
                    subscribe = {
                        "APIKey": self.api_key,
                        "BoundingBoxes": self.bbox,
                        "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
                    }
                    await ws.send(json.dumps(subscribe))
                    logger.info("AIS stream connected; subscribed to %d boxes", len(self.bbox))
                    backoff = 2.0  # reset on successful connect

                    async for raw in ws:
                        if self._stop.is_set():
                            break
                        try:
                            msg = json.loads(raw)
                            pos = _extract_position(msg)
                            if pos is not None:
                                cache.upsert(pos)
                        except (json.JSONDecodeError, ValueError, KeyError):
                            logger.debug("Skipping malformed AIS message", exc_info=True)

            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover (network)
                logger.warning("AIS stream disconnected (%s); retrying in %.0fs", exc, backoff)
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=backoff)
                    break
                except asyncio.TimeoutError:
                    pass
                backoff = min(backoff * 2, 60.0)


# ---------------------------------------------------------------------------
# Public helpers used by app lifespan
# ---------------------------------------------------------------------------

def is_enabled() -> bool:
    return bool(os.getenv("AIS_API_KEY"))


def make_consumer() -> Optional[AISStreamConsumer]:
    api_key = os.getenv("AIS_API_KEY")
    if not api_key:
        return None
    return AISStreamConsumer(api_key)
