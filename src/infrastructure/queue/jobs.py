"""
Job handlers registered against the default TaskQueue (issue #85).

Each function returns a plain dict (or None) that is stored on the Job
record. They must remain side-effect-free in terms of HTTP responses
and import-time work — the queue executes them on background threads.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def run_grib_ingestion(path: str) -> dict:
    """
    Load a GRIB2 (or JSON fallback) current grid and return its bbox + size.

    Used to refresh the current-aware routing strategy without blocking
    the API request that triggered the refresh.
    """
    from src.core.services.current_grid import load_auto

    grid = load_auto(path)
    if grid is None:
        return {"loaded": False, "path": path}
    bbox = grid.bbox()
    return {
        "loaded": True,
        "path": path,
        "bbox": list(bbox),
        "nrows": grid.nrows,
        "ncols": grid.ncols,
    }


def run_analytics_rollup(company_id: Optional[str] = None) -> dict:
    """
    Aggregate route history into per-company analytics counters.

    Stub for now — returns a count of recent routes. The full implementation
    will read RouteHistory and update an analytics document.
    """
    from src.infrastructure.repositories.route_history_repository import (
        RouteHistoryRepository,
    )

    repo = RouteHistoryRepository()
    recent = repo.get_recent(limit=200)
    if company_id:
        recent = [r for r in recent if str(getattr(r, "company_id", "")) == company_id]
    return {
        "company_id": company_id,
        "rolled_up": len(recent),
    }


def run_ai_reroute(vessel_id: str, reason: str = "scheduled") -> dict:
    """
    Trigger the AI reroute service for a vessel.

    Designed to be invoked from cron-like timers or admin actions so a
    long-running reroute evaluation does not block the HTTP caller.
    """
    from src.core.services.ai.ai_service import AIService

    service = AIService()
    try:
        result = service.handle_reroute_request(
            vessel_id=vessel_id, reason=reason, current_position=None, force=False,
        )
        return {"ok": True, "vessel_id": vessel_id, "result_kind": type(result).__name__}
    except Exception as exc:
        logger.warning("AI reroute job failed for %s: %s", vessel_id, exc)
        raise


def run_weather_refresh(lat: float, lon: float) -> dict:
    """
    Pre-warm the current cache at a coordinate.

    The marine API is the hot path for the regional weather panel; this
    job lets a scheduler refresh popular points outside of request time.
    """
    import asyncio

    from src.core.grib_parser import fetch_current_at_point

    vec = asyncio.run(fetch_current_at_point(lat, lon))
    return {
        "lat": lat,
        "lon": lon,
        "speed_knots": round(vec.speed_knots, 3),
        "direction_deg": round(vec.direction_deg, 1),
    }
