"""
Live AIS endpoint.

GET /api/v1/ais/vessels
    Returns recent AIS position reports filtered by an optional bbox.

The data is served from the in-memory cache populated by
``src.core.services.ais_service.AISStreamConsumer`` running as a
lifespan task. If the AIS feed is not configured (no AIS_API_KEY),
the endpoint returns ``enabled: false`` rather than raising — the
client uses that flag to keep the toggle disabled with a helpful
tooltip.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from src.core.services import ais_service

router = APIRouter(prefix="/api/v1/ais", tags=["ais"])


@router.get("/vessels")
def list_live_vessels(
    bbox: Optional[str] = Query(
        default=None,
        description="lat_min,lon_min,lat_max,lon_max — limit to a viewport",
    ),
    limit: int = Query(default=1000, ge=1, le=5000),
):
    if not ais_service.is_enabled():
        return {
            "enabled": False,
            "reason": (
                "AIS feed not configured. Set AIS_API_KEY (free from "
                "https://aisstream.io) and restart the server."
            ),
            "count": 0,
            "vessels": [],
        }

    parsed_bbox = None
    if bbox:
        try:
            parts = [float(x) for x in bbox.split(",")]
            if len(parts) == 4:
                parsed_bbox = tuple(parts)  # (lat_min, lon_min, lat_max, lon_max)
        except ValueError:
            parsed_bbox = None

    positions = ais_service.cache.snapshot(bbox=parsed_bbox, limit=limit)
    return {
        "enabled": True,
        "count": len(positions),
        "cache_size": ais_service.cache.size(),
        "vessels": [p.to_dict() for p in positions],
    }
