"""Integration tests for /api/v1/ais/vessels."""

from __future__ import annotations

import pytest
import mongomock
import mongoengine
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from src.core.services import ais_service
from src.core.services.ais_service import AISPosition


@pytest.fixture(scope="session", autouse=True)
def mock_db():
    mongoengine.disconnect_all()
    mongoengine.connect(
        "testdb_ais_endpoint",
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
def reset_ais_cache():
    ais_service.cache._positions.clear()  # noqa: SLF001


class TestAISEndpoint:
    def test_disabled_when_no_api_key(self, client, monkeypatch):
        monkeypatch.delenv("AIS_API_KEY", raising=False)
        resp = client.get("/api/v1/ais/vessels")
        assert resp.status_code == 200
        body = resp.json()
        assert body["enabled"] is False
        assert body["vessels"] == []
        assert "AIS_API_KEY" in body["reason"]

    def test_returns_cached_positions(self, client, monkeypatch):
        monkeypatch.setenv("AIS_API_KEY", "x")
        ais_service.cache.upsert(AISPosition(mmsi=1, lat=10.0, lon=20.0, name="A"))
        ais_service.cache.upsert(AISPosition(mmsi=2, lat=-10.0, lon=-20.0, name="B"))
        resp = client.get("/api/v1/ais/vessels")
        assert resp.status_code == 200
        body = resp.json()
        assert body["enabled"] is True
        assert body["count"] == 2
        assert {v["name"] for v in body["vessels"]} == {"A", "B"}

    def test_bbox_filter_applied(self, client, monkeypatch):
        monkeypatch.setenv("AIS_API_KEY", "x")
        ais_service.cache.upsert(AISPosition(mmsi=1, lat=10.0, lon=20.0))  # inside
        ais_service.cache.upsert(AISPosition(mmsi=2, lat=60.0, lon=60.0))  # outside
        resp = client.get("/api/v1/ais/vessels?bbox=0,0,30,30")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert body["vessels"][0]["mmsi"] == 1

    def test_bad_bbox_falls_back_to_world(self, client, monkeypatch):
        monkeypatch.setenv("AIS_API_KEY", "x")
        ais_service.cache.upsert(AISPosition(mmsi=1, lat=10.0, lon=20.0))
        resp = client.get("/api/v1/ais/vessels?bbox=garbage")
        assert resp.status_code == 200
        assert resp.json()["count"] == 1
