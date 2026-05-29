import pytest

from src.core.services.weather_service import WeatherService, _parse_current_weather
from src.infrastructure.cache.ttl_cache import TTLCache
from src.infrastructure.clients.weather_client import WeatherClient


SAMPLE_WEATHER_PAYLOAD = {
    "coord": {"lon": 28.9784, "lat": 41.0082},
    "weather": [
        {
            "id": 800,
            "main": "Clear",
            "description": "clear sky",
            "icon": "01d",
        }
    ],
    "main": {
        "temp": 18.4,
        "feels_like": 17.9,
        "pressure": 1015,
        "humidity": 62,
    },
    "visibility": 10000,
    "wind": {"speed": 4.2, "deg": 210, "gust": 6.1},
}


class FakeWeatherClient(WeatherClient):
    def __init__(self, payload: dict):
        super().__init__(api_key="test-key", client=None)
        self.payload = payload
        self.calls = 0

    async def fetch_current_weather(self, lat: float, lon: float) -> dict:
        self.calls += 1
        return self.payload


@pytest.mark.asyncio
async def test_parse_current_weather_maps_fields():
    result = _parse_current_weather(SAMPLE_WEATHER_PAYLOAD)
    assert result.lat == pytest.approx(41.0082)
    assert result.lon == pytest.approx(28.9784)
    assert result.temperature_c == pytest.approx(18.4)
    assert result.conditions.main == "Clear"
    assert result.wind_gust_ms == pytest.approx(6.1)


@pytest.mark.asyncio
async def test_get_current_weather_uses_cache():
    client = FakeWeatherClient(SAMPLE_WEATHER_PAYLOAD)
    service = WeatherService(client=client, cache=TTLCache(600))

    first = await service.get_current_weather(41.0, 29.0)
    second = await service.get_current_weather(41.0, 29.0)

    assert client.calls == 1
    assert first.cached is False
    assert second.cached is True
