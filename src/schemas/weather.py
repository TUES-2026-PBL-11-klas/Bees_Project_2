from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WeatherConditions(BaseModel):
    id: int
    main: str
    description: str
    icon: str


class CurrentWeatherResponse(BaseModel):
    lat: float
    lon: float
    temperature_c: float
    feels_like_c: float
    humidity_percent: int
    wind_speed_ms: float
    wind_direction_deg: Optional[int] = None
    wind_gust_ms: Optional[float] = None
    pressure_hpa: int
    visibility_m: Optional[int] = None
    conditions: WeatherConditions
    fetched_at: datetime
    cached: bool = False


class WeatherMapBBox(BaseModel):
    north: float
    south: float
    east: float
    west: float


class WeatherMapResponse(BaseModel):
    bbox: WeatherMapBBox
    cols: int
    rows: int
    points: list[CurrentWeatherResponse]
    cached_points: int = Field(
        default=0,
        description="Number of grid points served from cache.",
    )
