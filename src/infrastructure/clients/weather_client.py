import logging
from typing import Any

import httpx

from src.core.config import settings
from src.exceptions.weather_exceptions import WeatherApiKeyMissingException, WeatherServiceException

logger = logging.getLogger(__name__)


class WeatherClient:
    """Async HTTP client for the OpenWeatherMap current-weather API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        client: httpx.AsyncClient | None = None,
    ):
        self._api_key = api_key if api_key is not None else settings.WEATHER_API_KEY
        self._base_url = (base_url or settings.WEATHER_API_BASE_URL).rstrip("/")
        self._timeout = timeout_seconds or settings.WEATHER_HTTP_TIMEOUT_SECONDS
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._client

    def _require_api_key(self) -> str:
        if not self._api_key:
            raise WeatherApiKeyMissingException()
        return self._api_key

    async def fetch_current_weather(self, lat: float, lon: float) -> dict[str, Any]:
        api_key = self._require_api_key()
        client = await self._get_client()

        try:
            response = await client.get(
                "/weather",
                params={
                    "lat": lat,
                    "lon": lon,
                    "appid": api_key,
                    "units": "metric",
                },
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            logger.warning(
                "Weather API HTTP error for lat=%s lon=%s: %s",
                lat,
                lon,
                detail,
            )
            raise WeatherServiceException(
                "Weather provider returned an error.",
                details=detail,
            ) from exc
        except httpx.HTTPError as exc:
            logger.exception("Weather API request failed for lat=%s lon=%s", lat, lon)
            raise WeatherServiceException(
                "Unable to reach the weather provider.",
                details=str(exc),
            ) from exc

        return response.json()

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None
