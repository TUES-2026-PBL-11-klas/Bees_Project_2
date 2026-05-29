from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.schemas.weather import CurrentWeatherResponse, WeatherConditions, WeatherMapResponse
from src.schemas.weather import WeatherMapBBox


@pytest.fixture
def client():
    with patch("src.main.init_db"), patch("src.main.close_db"):
        import mongoengine
        import mongomock

        mongoengine.disconnect_all()
        mongoengine.connect(
            "testdb",
            host="mongodb://localhost",
            mongo_client_class=mongomock.MongoClient,
            uuidRepresentation="standard",
        )
        with patch("src.api.v1.routers.weather._weather_service", None):
            with TestClient(app) as test_client:
                yield test_client
        mongoengine.disconnect_all()


def _sample_point(cached: bool = False) -> CurrentWeatherResponse:
    return CurrentWeatherResponse(
        lat=41.0082,
        lon=28.9784,
        temperature_c=18.4,
        feels_like_c=17.9,
        humidity_percent=62,
        wind_speed_ms=4.2,
        wind_direction_deg=210,
        wind_gust_ms=6.1,
        pressure_hpa=1015,
        visibility_m=10000,
        conditions=WeatherConditions(
            id=800,
            main="Clear",
            description="clear sky",
            icon="01d",
        ),
        fetched_at=datetime.now(timezone.utc),
        cached=cached,
    )


def test_get_weather_current(client: TestClient):
    mock_service = AsyncMock()
    mock_service.get_current_weather.return_value = _sample_point()

    with patch(
        "src.api.v1.routers.weather.get_weather_service",
        return_value=mock_service,
    ):
        response = client.get(
            "/api/v1/weather/current",
            params={"lat": 41.0082, "lon": 28.9784},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["lat"] == pytest.approx(41.0082)
    assert data["conditions"]["main"] == "Clear"
    mock_service.get_current_weather.assert_awaited_once_with(41.0082, 28.9784)


def test_get_weather_map(client: TestClient):
    mock_service = AsyncMock()
    mock_service.get_weather_map.return_value = WeatherMapResponse(
        bbox=WeatherMapBBox(north=45.0, south=40.0, east=30.0, west=25.0),
        cols=2,
        rows=2,
        points=[_sample_point(), _sample_point(cached=True)],
        cached_points=1,
    )

    with patch(
        "src.api.v1.routers.weather.get_weather_service",
        return_value=mock_service,
    ):
        response = client.get(
            "/api/v1/weather/map",
            params={
                "north": 45.0,
                "south": 40.0,
                "east": 30.0,
                "west": 25.0,
                "cols": 2,
                "rows": 2,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["cols"] == 2
    assert data["rows"] == 2
    assert len(data["points"]) == 2
    assert data["cached_points"] == 1


def test_get_weather_current_missing_api_key(client: TestClient):
    from src.exceptions.weather_exceptions import WeatherApiKeyMissingException

    mock_service = AsyncMock()
    mock_service.get_current_weather.side_effect = WeatherApiKeyMissingException()

    with patch(
        "src.api.v1.routers.weather.get_weather_service",
        return_value=mock_service,
    ):
        response = client.get(
            "/api/v1/weather/current",
            params={"lat": 41.0, "lon": 29.0},
        )

    assert response.status_code == 503
