"""
Ocean current data fetcher using Open-Meteo Marine API.

Provides U/V current components at any ocean coordinate.
Since the Open-Meteo Marine API does not expose direct ocean-current
fields, surface currents are approximated via **Stokes drift** derived
from wave parameters (height, period, direction).

    U_stokes ≈ 0.01 × H × (2π / T)

Data is cached in-memory with a configurable TTL.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass, field
from typing import Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

_MARINE_API = "https://marine-api.open-meteo.com/v1/marine"
_TIMEOUT = 8.0  # seconds per request
_CACHE_TTL = 3600  # 1 hour


@dataclass
class CurrentVector:
    """Ocean current at a specific point."""

    u_ms: float  # East-west component  (m/s, positive = east)
    v_ms: float  # North-south component (m/s, positive = north)
    speed_ms: float = field(init=False)
    speed_knots: float = field(init=False)
    direction_deg: float = field(init=False)  # direction current flows TO

    def __post_init__(self) -> None:
        self.speed_ms = math.sqrt(self.u_ms**2 + self.v_ms**2)
        self.speed_knots = self.speed_ms * 1.94384
        self.direction_deg = (
            math.degrees(math.atan2(self.u_ms, self.v_ms)) + 360
        ) % 360


_current_cache: dict[tuple[float, float], tuple[float, CurrentVector]] = {}


def _cache_key(lat: float, lon: float) -> tuple[float, float]:
    """Round to 0.5° grid for cache efficiency."""
    return (round(lat * 2) / 2, round(lon * 2) / 2)



def _stokes_drift(
    wave_height: Optional[float],
    wave_period: Optional[float],
    wave_direction_deg: Optional[float],
) -> CurrentVector:
    """Approximate surface current from wave parameters.

    Uses the deep-water Stokes-drift formula:
        U_s ≈ 0.01 × H × (2π / T)

    ``wave_direction_deg`` is the direction waves come FROM (meteorological
    convention).  The resulting drift flows in the *same* direction the
    waves travel, i.e. 180° opposite to the "from" direction.

    Returns a ``CurrentVector`` with u/v components.  Falls back to zero
    if any input is ``None`` or the period is non-positive.
    """
    if (
        wave_height is None
        or wave_period is None
        or wave_direction_deg is None
        or wave_period <= 0
    ):
        return CurrentVector(0.0, 0.0)

    speed = 0.01 * wave_height * (2 * math.pi / wave_period)

    # Waves come FROM wave_direction_deg; drift goes in the opposite
    # direction, so add 180°.
    drift_dir_deg = (wave_direction_deg + 180) % 360
    drift_dir_rad = math.radians(drift_dir_deg)

    u = speed * math.sin(drift_dir_rad)  # east component
    v = speed * math.cos(drift_dir_rad)  # north component

    return CurrentVector(u, v)



async def fetch_current_at_point(lat: float, lon: float) -> CurrentVector:
    """Fetch (or return cached) ocean current estimate for a point.

    Calls the Open-Meteo Marine API for ``wave_height``,
    ``wave_direction`` and ``wave_period``, then derives a Stokes-drift
    current estimate.

    On any failure the function returns ``CurrentVector(0, 0)`` so callers
    can safely continue without crashing.
    """
    key = _cache_key(lat, lon)
    now = time.monotonic()

    cached = _current_cache.get(key)
    if cached is not None:
        ts, vec = cached
        if now - ts < _CACHE_TTL:
            return vec

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                _MARINE_API,
                params={
                    "latitude": key[0],
                    "longitude": key[1],
                    "hourly": "wave_height,wave_direction,wave_period",
                    "forecast_days": 1,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        hourly = data.get("hourly", {})
        wave_height = _first(hourly.get("wave_height"))
        wave_period = _first(hourly.get("wave_period"))
        wave_direction = _first(hourly.get("wave_direction"))

        vec = _stokes_drift(wave_height, wave_period, wave_direction)

        logger.debug(
            "Current at (%.2f, %.2f): %.3f kn @ %.0f° "
            "(H=%.1f m, T=%.1f s, D=%.0f°)",
            lat,
            lon,
            vec.speed_knots,
            vec.direction_deg,
            wave_height or 0,
            wave_period or 0,
            wave_direction or 0,
        )

    except Exception:
        logger.warning(
            "Failed to fetch current for (%.2f, %.2f); returning zero vector",
            lat,
            lon,
            exc_info=True,
        )
        vec = CurrentVector(0.0, 0.0)

    _current_cache[key] = (now, vec)
    return vec


async def fetch_currents_batch(
    points: list[tuple[float, float]],
) -> list[CurrentVector]:
    """Fetch currents for *points* in parallel.

    Returns a list of ``CurrentVector`` in the same order as *points*.
    Individual failures are silently replaced with zero vectors.
    """
    return list(
        await asyncio.gather(
            *(fetch_current_at_point(lat, lon) for lat, lon in points)
        )
    )



def get_current_effect_on_heading(
    current: CurrentVector,
    heading_deg: float,
    vessel_speed_knots: float,
) -> float:
    """Return a speed-adjustment factor for a vessel on *heading_deg*.

    * ``> 1.0`` → current is favourable (pushes the vessel along)
    * ``< 1.0`` → current opposes the vessel
    * ``1.0``   → no net effect (or zero current)

    The component of the current along the vessel heading is projected and
    divided by the vessel speed to obtain the factor.
    """
    if vessel_speed_knots <= 0 or current.speed_knots == 0:
        return 1.0

    # Angle between current direction and vessel heading
    angle_diff = math.radians(current.direction_deg - heading_deg)
    current_component_knots = current.speed_knots * math.cos(angle_diff)

    return 1.0 + current_component_knots / vessel_speed_knots



def _first(values: Optional[list]) -> Optional[float]:
    """Return the first non-None element, or ``None``."""
    if not values:
        return None
    for v in values:
        if v is not None:
            return float(v)
    return None
