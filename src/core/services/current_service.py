"""
Service layer for ocean current data.

Wraps the GRIB parser and provides higher-level methods
for route analysis.
"""

from __future__ import annotations

import logging
import math

from src.core.grib_parser import (
    CurrentVector,
    fetch_current_at_point,
    fetch_currents_batch,
    get_current_effect_on_heading,
)

logger = logging.getLogger(__name__)


class OceanCurrentService:
    """High-level facade for ocean-current queries."""

    # ------------------------------------------------------------------
    # Single-point query
    # ------------------------------------------------------------------

    async def get_current_at(self, lat: float, lon: float) -> CurrentVector:
        """Return the estimated ocean current at *(lat, lon)*."""
        return await fetch_current_at_point(lat, lon)

    # ------------------------------------------------------------------
    # Route-level query
    # ------------------------------------------------------------------

    async def get_currents_for_route(
        self,
        waypoints: list[dict],
    ) -> list[dict]:
        """Get currents at each waypoint along a route.

        Parameters
        ----------
        waypoints:
            List of dicts, each with ``'coordinates': [lon, lat]``
            (GeoJSON order).

        Returns
        -------
        list[dict]
            One dict per sampled point containing ``lat``, ``lon``,
            ``speed_knots``, ``direction_deg``, ``u_ms`` and ``v_ms``.
        """
        points: list[tuple[float, float]] = []
        for wp in waypoints:
            coords = wp.get("coordinates", [])
            if len(coords) >= 2:
                points.append((coords[1], coords[0]))  # lat, lon

        if not points:
            return []

        # Sample up to 10 points evenly along the route
        if len(points) > 10:
            step = len(points) / 10
            points = [points[int(i * step)] for i in range(10)]

        currents = await fetch_currents_batch(points)

        return [
            {
                "lat": pt[0],
                "lon": pt[1],
                "speed_knots": round(c.speed_knots, 3),
                "direction_deg": round(c.direction_deg, 1),
                "u_ms": round(c.u_ms, 4),
                "v_ms": round(c.v_ms, 4),
            }
            for pt, c in zip(points, currents)
        ]

    # ------------------------------------------------------------------
    # Leg-level adjustment
    # ------------------------------------------------------------------

    def compute_leg_adjustment(
        self,
        current: CurrentVector,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        vessel_speed_knots: float = 14.0,
    ) -> float:
        """Compute speed adjustment factor for a route leg.

        Returns a multiplicative factor (e.g. *1.03* when the current
        is favourable, *0.97* when opposing).
        """
        dlat = end_lat - start_lat
        dlon = end_lon - start_lon
        heading = (math.degrees(math.atan2(dlon, dlat)) + 360) % 360
        return get_current_effect_on_heading(current, heading, vessel_speed_knots)
