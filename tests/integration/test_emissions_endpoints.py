"""Integration tests for /api/v1/emissions."""

from __future__ import annotations

import pytest
import mongomock
import mongoengine
from bson import ObjectId
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch


@pytest.fixture(scope="session", autouse=True)
def mock_db():
    mongoengine.disconnect_all()
    mongoengine.connect(
        "testdb_emissions",
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
def clean_collections():
    from src.models.route_history import RouteHistory
    from src.models.vessel import Vessel
    RouteHistory.drop_collection()
    Vessel.drop_collection()


class TestVoyageEndpoint:
    def test_voyage_returns_co2_and_rating(self, client):
        resp = client.post("/api/v1/emissions/voyage", json={
            "fuel_tons": 50.0,
            "vessel_type": "bulk_carrier",
            "distance_nm": 1200.0,
            "dwt_tons": 80_000.0,
            "fuel_type": "HFO",
            "calls_at_eu_port": True,
            "compliance_year": 2025,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["co2_tons"] > 0
        assert body["rating"] in {"A", "B", "C", "D", "E"}
        assert body["eu_ets_allowance_cost_eur"] > 0

    def test_voyage_without_dwt_still_returns_co2(self, client):
        resp = client.post("/api/v1/emissions/voyage", json={
            "fuel_tons": 10.0,
            "vessel_type": "tanker",
            "distance_nm": 200.0,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["co2_tons"] > 0
        assert body["rating"] is None

    def test_invalid_payload_returns_422(self, client):
        # Negative fuel
        resp = client.post("/api/v1/emissions/voyage", json={
            "fuel_tons": -1.0,
            "vessel_type": "tanker",
            "distance_nm": 100.0,
        })
        assert resp.status_code == 422


class TestFleetEndpoint:
    def test_fleet_empty_history_returns_zeros(self, client):
        company_id = str(ObjectId())
        resp = client.get(f"/api/v1/emissions/fleet/{company_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["fleet_total_co2_tons"] == 0.0
        assert body["by_vessel"] == []

    def test_fleet_invalid_company_id_returns_400(self, client):
        resp = client.get("/api/v1/emissions/fleet/not-an-objectid")
        assert resp.status_code == 400

    def test_fleet_aggregates_voyages_per_vessel(self, client):
        from src.models.route_history import RouteHistory
        from src.models.vessel import Vessel, VesselSpecs

        company_id = ObjectId()
        vessel = Vessel(
            company_id=company_id,
            name="Test Bulker",
            imo_number="IMO1234567",
            vessel_type="bulk_carrier",
            specs=VesselSpecs(max_cargo_t=80_000),
        )
        vessel.save()

        # Two voyages by the same vessel.
        for i in range(2):
            RouteHistory(
                company_id=company_id,
                vessel_id=vessel.id,
                estimated_fuel_tons=40.0,
                total_distance_nm=1000.0,
            ).save()

        resp = client.get(
            f"/api/v1/emissions/fleet/{company_id}",
            params={"calls_at_eu_port": True, "year": 2025},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["voyages_considered"] == 2
        # 80 t HFO total → ~249 t CO2
        assert body["fleet_total_co2_tons"] == pytest.approx(80 * 3.114, abs=0.5)
        assert body["fleet_total_distance_nm"] == 2000.0
        assert len(body["by_vessel"]) == 1
        row = body["by_vessel"][0]
        assert row["voyages"] == 2
        assert row["rating"] in {"A", "B", "C", "D", "E"}
        assert row["vessel_name"] == "Test Bulker"
