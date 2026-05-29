import asyncio
import logging
from datetime import datetime, timezone

from src.core.config import settings
from src.exceptions.weather_exceptions import WeatherServiceException
from src.infrastructure.cache.ttl_cache import TTLCache
from src.infrastructure.clients.weather_client import WeatherClient
from src.schemas.weather import (
    CurrentWeatherResponse,
    WeatherConditions,
    WeatherMapBBox,
    WeatherMapResponse,
)

logger = logging.getLogger(__name__)


def _cache_key(lat: float, lon: float) -> str:
    return f"{round(lat, 2)}:{round(lon, 2)}"


def _parse_current_weather(payload: dict, cached: bool = False) -> CurrentWeatherResponse:
    coord = payload.get("coord") or {}
    main = payload.get("main") or {}
    wind = payload.get("wind") or {}
    weather_items = payload.get("weather") or [{}]
    summary = weather_items[0]

    return CurrentWeatherResponse(
        lat=float(coord.get("lat", 0.0)),
        lon=float(coord.get("lon", 0.0)),
        temperature_c=float(main.get("temp", 0.0)),
        feels_like_c=float(main.get("feels_like", main.get("temp", 0.0))),
        humidity_percent=int(main.get("humidity", 0)),
        wind_speed_ms=float(wind.get("speed", 0.0)),
        wind_direction_deg=wind.get("deg"),
        wind_gust_ms=wind.get("gust"),
        pressure_hpa=int(main.get("pressure", 0)),
        visibility_m=payload.get("visibility"),
        conditions=WeatherConditions(
            id=int(summary.get("id", 0)),
            main=str(summary.get("main", "")),
            description=str(summary.get("description", "")),
            icon=str(summary.get("icon", "")),
        ),
        fetched_at=datetime.now(timezone.utc),
        cached=cached,
    )


def _build_grid(
    north: float,
    south: float,
    east: float,
    west: float,
    cols: int,
    rows: int,
) -> list[tuple[float, float]]:
    if cols < 1 or rows < 1:
        raise WeatherServiceException("Grid dimensions must be at least 1.")

    lat_step = (north - south) / max(rows - 1, 1)
    lon_step = (east - west) / max(cols - 1, 1)

    points: list[tuple[float, float]] = []
    for row in range(rows):
        lat = north - (lat_step * row)
        for col in range(cols):
            lon = west + (lon_step * col)
            points.append((lat, lon))
    return points


class WeatherService:
    def __init__(
        self,
        client: WeatherClient | None = None,
        cache: TTLCache[CurrentWeatherResponse] | None = None,
        max_grid_points: int | None = None,
    ):
        self._client = client or WeatherClient()
        self._cache = cache or TTLCache(settings.WEATHER_CACHE_TTL_SECONDS)
        self._max_grid_points = max_grid_points or settings.WEATHER_MAP_MAX_GRID_POINTS
        self._fetch_semaphore = asyncio.Semaphore(8)

    async def get_current_weather(self, lat: float, lon: float) -> CurrentWeatherResponse:
        key = _cache_key(lat, lon)
        cached = await self._cache.get(key)
        if cached is not None:
            return cached.model_copy(update={"cached": True})

        async with self._fetch_semaphore:
            cached = await self._cache.get(key)
            if cached is not None:
                return cached.model_copy(update={"cached": True})

            payload = await self._client.fetch_current_weather(lat, lon)
            result = _parse_current_weather(payload, cached=False)
            await self._cache.set(key, result)
            return result

    async def get_weather_map(
        self,
        north: float,
        south: float,
        east: float,
        west: float,
        cols: int = 4,
        rows: int = 4,
    ) -> WeatherMapResponse:
        if north <= south:
            raise WeatherServiceException("north must be greater than south.")
        if east == west:
            raise WeatherServiceException("east and west must differ.")

        grid_points = _build_grid(north, south, east, west, cols, rows)
        if len(grid_points) > self._max_grid_points:
            raise WeatherServiceException(
                f"Grid size {cols}x{rows} exceeds limit of {self._max_grid_points} points.",
            )

        tasks = [self.get_current_weather(lat, lon) for lat, lon in grid_points]
        points = await asyncio.gather(*tasks)
        cached_points = sum(1 for point in points if point.cached)

        return WeatherMapResponse(
            bbox=WeatherMapBBox(north=north, south=south, east=east, west=west),
            cols=cols,
            rows=rows,
            points=list(points),
            cached_points=cached_points,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
