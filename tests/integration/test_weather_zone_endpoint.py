"""Integration tests for /api/v1/zones/refresh-from-samples."""

from __future__ import annotations

import pytest
import mongomock
import mongoengine
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from src.core.services.weather_zone_service import AUTO_STORM_NAME_PREFIX


@pytest.fixture(scope="session", autouse=True)
def mock_db():
    mongoengine.disconnect_all()
    mongoengine.connect(
        "testdb_weather_zone_endpoint",
        host="mongodb://localhost",
        mongo_client_class=mongomock.MongoClient,
        uuidRepresentation="standard",
    )
    yield
    mongoengine.disconnect_all()


@pytest.fixture(scope="session")
def client(mock_db):
    from src.core.events.dispatcher import dispatcher
    dispatcher._audit_repo = MagicMock()
    with patch("src.main.init_db"), patch("src.main.close_db"):
        from src.main import app
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


@pytest.fixture(autouse=True)
def clean_zones():
    from src.models.zone import Zone
    Zone.drop_collection()


STORM_SAMPLE = {
    "region_id": "east_med",
    "region_name": "East Mediterranean",
    "bbox": {
        "min_lat": 30.0, "max_lat": 37.5,
        "min_lon": 16.0, "max_lon": 36.0,
    },
    "wave_height": 6.0,
    "wind_speed_10m": 12.0,
}


class TestRefreshFromSamples:
    def test_creates_storm_zone_for_storm_sample(self, client):
        from src.models.zone import Zone

        resp = client.post(
            "/api/v1/zones/refresh-from-samples",
            json=[STORM_SAMPLE],
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["created"] == ["east_med"]
        assert Zone.objects(name=f"{AUTO_STORM_NAME_PREFIX}east_med").count() == 1

    def test_calm_sample_creates_nothing(self, client):
        from src.models.zone import Zone

        calm = dict(STORM_SAMPLE, wave_height=0.5, wind_speed_10m=2.0)
        resp = client.post("/api/v1/zones/refresh-from-samples", json=[calm])
        assert resp.status_code == 200
        assert resp.json()["created"] == []
        assert Zone.objects().count() == 0

    def test_custom_thresholds_via_query_string(self, client):
        from src.models.zone import Zone

        # Very lenient thresholds → even mild conditions should trigger.
        mild = dict(STORM_SAMPLE, wave_height=2.0, wind_speed_10m=5.0)
        resp = client.post(
            "/api/v1/zones/refresh-from-samples",
            params={
                "wave_height_threshold_m": 1.0,
                "wind_speed_threshold_ms": 4.0,
                "valid_hours": 6,
            },
            json=[mild],
        )
        assert resp.status_code == 200
        assert resp.json()["created"] == ["east_med"]
        assert Zone.objects().count() == 1
