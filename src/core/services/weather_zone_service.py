"""
Dynamic weather-driven no-go zone generator.

Instead of asking operators to remember to draw and remove storm zones
by hand, this service scans current weather samples for any maritime
region that exceeds a configured wave-height or wind-speed threshold
and persists a ``Zone(zone_type="temporary", status="active")`` covering
that region's bounding box. The zone gets a ``valid_until`` deadline so
downstream callers automatically stop avoiding the region once the
storm has passed.

Design choices
--------------
* The threshold checks are pure functions over a sample dict so the
  whole pipeline is unit-testable without ever touching the real
  Open-Meteo client.
* Zones are upserted by name (``auto_storm_<region_id>``): if a storm
  zone already exists for the region and is still in its valid window,
  we extend ``valid_until`` instead of stacking duplicates.
* Regions whose latest sample is calm get their existing storm zone
  cleared (status → ``inactive``) so the AI module + routing engine
  immediately stop treating them as no-go areas.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Iterable, Optional

from src.core.utc import utc_now
from src.models.zone import Zone

logger = logging.getLogger(__name__)


# Default thresholds — exceeding either flips the region to a storm zone.
DEFAULT_WAVE_HEIGHT_THRESHOLD_M = 4.0          # >4 m significant wave height
DEFAULT_WIND_SPEED_THRESHOLD_MS = 20.0         # >20 m/s ≈ Beaufort 9 (Strong Gale)

DEFAULT_VALID_HOURS = 12
AUTO_STORM_NAME_PREFIX = "auto_storm_"


def _polygon_from_bbox(bbox: dict) -> dict:
    """Convert a {min_lat, max_lat, min_lon, max_lon} bbox to a closed
    GeoJSON Polygon (lon, lat order, first==last)."""
    return {
        "type": "Polygon",
        "coordinates": [[
            [bbox["min_lon"], bbox["min_lat"]],
            [bbox["max_lon"], bbox["min_lat"]],
            [bbox["max_lon"], bbox["max_lat"]],
            [bbox["min_lon"], bbox["max_lat"]],
            [bbox["min_lon"], bbox["min_lat"]],
        ]],
    }


def exceeds_storm_threshold(
    sample: dict,
    *,
    wave_height_threshold_m: float = DEFAULT_WAVE_HEIGHT_THRESHOLD_M,
    wind_speed_threshold_ms: float = DEFAULT_WIND_SPEED_THRESHOLD_MS,
) -> bool:
    """True if either the wave-height or wind-speed reading exceeds the
    storm threshold for this sample."""
    wave = sample.get("wave_height")
    wind = sample.get("wind_speed_10m")
    if isinstance(wave, (int, float)) and wave > wave_height_threshold_m:
        return True
    if isinstance(wind, (int, float)) and wind > wind_speed_threshold_ms:
        return True
    return False


class WeatherZoneService:
    """Create / extend / retire dynamic storm zones from weather samples."""

    def __init__(
        self,
        *,
        wave_height_threshold_m: float = DEFAULT_WAVE_HEIGHT_THRESHOLD_M,
        wind_speed_threshold_ms: float = DEFAULT_WIND_SPEED_THRESHOLD_MS,
        valid_hours: int = DEFAULT_VALID_HOURS,
    ) -> None:
        self.wave_threshold = wave_height_threshold_m
        self.wind_threshold = wind_speed_threshold_ms
        self.valid_hours = valid_hours

    # ------------------------------------------------------------------
    # Core entry point — pure function over the supplied region samples
    # ------------------------------------------------------------------

    def refresh(self, region_samples: Iterable[dict]) -> dict:
        """
        For each region sample, create / refresh a storm zone if the
        sample exceeds thresholds, or retire any existing storm zone if
        the sample is calm again.

        Each sample must carry at least ``region_id``, ``region_name``,
        ``bbox`` and the measurement keys (``wave_height``,
        ``wind_speed_10m``). Returns a summary dict.
        """
        created: list[str] = []
        extended: list[str] = []
        retired: list[str] = []
        skipped: list[str] = []

        now = utc_now()
        new_valid_until = now + timedelta(hours=self.valid_hours)

        for sample in region_samples:
            region_id = sample.get("region_id")
            if not region_id:
                skipped.append("missing region_id")
                continue
            bbox = sample.get("bbox")
            if not isinstance(bbox, dict) or not {"min_lat", "max_lat", "min_lon", "max_lon"} <= bbox.keys():
                skipped.append(region_id)
                continue

            zone_name = f"{AUTO_STORM_NAME_PREFIX}{region_id}"
            existing = Zone.objects(name=zone_name).first()
            is_storm = exceeds_storm_threshold(
                sample,
                wave_height_threshold_m=self.wave_threshold,
                wind_speed_threshold_ms=self.wind_threshold,
            )

            if is_storm:
                if existing is None:
                    Zone(
                        name=zone_name,
                        zone_type="temporary",
                        status="active",
                        geometry=_polygon_from_bbox(bbox),
                        description=self._build_description(sample),
                        valid_from=now,
                        valid_until=new_valid_until,
                    ).save()
                    created.append(region_id)
                else:
                    # Extend the deadline and refresh the description, keep
                    # the polygon the same (region bbox doesn't move).
                    existing.update(
                        set__status="active",
                        set__valid_until=new_valid_until,
                        set__description=self._build_description(sample),
                    )
                    extended.append(region_id)
            else:
                if existing is not None and existing.status == "active":
                    existing.update(set__status="inactive")
                    retired.append(region_id)

        summary = {
            "created":   created,
            "extended":  extended,
            "retired":   retired,
            "skipped":   skipped,
            "valid_until": new_valid_until.isoformat(),
        }
        logger.info(
            "weather zone refresh: created=%d extended=%d retired=%d skipped=%d",
            len(created), len(extended), len(retired), len(skipped),
        )
        return summary

    def _build_description(self, sample: dict) -> str:
        wave = sample.get("wave_height")
        wind = sample.get("wind_speed_10m")
        bits = [f"Storm zone for {sample.get('region_name') or sample.get('region_id')}."]
        if isinstance(wave, (int, float)):
            bits.append(f"Wave height {wave:.1f} m.")
        if isinstance(wind, (int, float)):
            bits.append(f"Wind speed {wind:.1f} m/s.")
        bits.append("Auto-generated; expires when conditions ease.")
        return " ".join(bits)


# ---------------------------------------------------------------------------
# Adapter to the live /weather/regions client
# ---------------------------------------------------------------------------


async def refresh_zones_from_live_weather(
    *,
    valid_hours: int = DEFAULT_VALID_HOURS,
    wave_height_threshold_m: float = DEFAULT_WAVE_HEIGHT_THRESHOLD_M,
    wind_speed_threshold_ms: float = DEFAULT_WIND_SPEED_THRESHOLD_MS,
) -> dict:
    """Pull the latest /weather/regions samples and run the refresh."""
    from src.api.v1.routers.weather import get_all_regions_weather  # late import to avoid cycles

    samples = await get_all_regions_weather()
    if not isinstance(samples, list):
        # The endpoint may return a non-list during transient upstream failures.
        return {"error": "weather feed unavailable", "samples": 0}

    service = WeatherZoneService(
        wave_height_threshold_m=wave_height_threshold_m,
        wind_speed_threshold_ms=wind_speed_threshold_ms,
        valid_hours=valid_hours,
    )
    return service.refresh(samples)


# Optional task-queue handler so the background worker can fire this on a
# schedule. The /infrastructure/queue/jobs.py registry imports this lazily.
def weather_zone_refresh_job(**kwargs) -> dict:
    """Synchronous wrapper for the task queue."""
    import asyncio
    return asyncio.run(refresh_zones_from_live_weather(**kwargs))
