import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from src.core.services.weather_service import WeatherService
from src.exceptions.weather_exceptions import WeatherApiKeyMissingException, WeatherServiceException
from src.schemas.weather import CurrentWeatherResponse, WeatherMapResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/weather", tags=["weather"])

_weather_service: WeatherService | None = None


def get_weather_service() -> WeatherService:
    global _weather_service
    if _weather_service is None:
        _weather_service = WeatherService()
    return _weather_service


async def close_weather_service() -> None:
    global _weather_service
    if _weather_service is not None:
        await _weather_service.aclose()
        _weather_service = None


@router.get("/current", response_model=CurrentWeatherResponse)
async def get_current_weather(
    lat: float = Query(..., ge=-90, le=90, description="WGS-84 latitude"),
    lon: float = Query(..., ge=-180, le=180, description="WGS-84 longitude"),
    service: WeatherService = Depends(get_weather_service),
) -> CurrentWeatherResponse:
    try:
        return await service.get_current_weather(lat, lon)
    except WeatherApiKeyMissingException as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except WeatherServiceException as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/map", response_model=WeatherMapResponse)
async def get_weather_map(
    north: float = Query(..., ge=-90, le=90),
    south: float = Query(..., ge=-90, le=90),
    east: float = Query(..., ge=-180, le=180),
    west: float = Query(..., ge=-180, le=180),
    cols: int = Query(default=4, ge=1, le=16),
    rows: int = Query(default=4, ge=1, le=16),
    service: WeatherService = Depends(get_weather_service),
) -> WeatherMapResponse:
    try:
        return await service.get_weather_map(
            north=north,
            south=south,
            east=east,
            west=west,
            cols=cols,
            rows=rows,
        )
    except WeatherApiKeyMissingException as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except WeatherServiceException as exc:
        status_code = 400 if "must" in str(exc).lower() or "exceeds" in str(exc).lower() else 502
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
