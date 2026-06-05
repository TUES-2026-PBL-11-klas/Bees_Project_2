from datetime import datetime, timedelta, timezone

import mongoengine
import mongomock
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from unittest.mock import patch

from src.models.route import Route


@pytest.fixture
def client():
    with patch("src.main.init_db"), patch("src.main.close_db"):
        mongoengine.disconnect_all()
        mongoengine.connect(
            "testdb",
            host="mongodb://localhost",
            mongo_client_class=mongomock.MongoClient,
            uuidRepresentation="standard",
        )

        company_id = ObjectId()
        vessel_id = ObjectId()
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        Route(
            request_id=ObjectId(),
            company_id=company_id,
            vessel_id=vessel_id,
            optimization_mode="fastest",
            total_distance_nm=120.0,
            estimated_duration_h=8.0,
            estimated_fuel_tons=40.0,
            calculated_at=now,
        ).save()
        Route(
            request_id=ObjectId(),
            company_id=company_id,
            vessel_id=vessel_id,
            optimization_mode="eco",
            total_distance_nm=130.0,
            estimated_duration_h=9.0,
            estimated_fuel_tons=35.0,
            calculated_at=now - timedelta(hours=1),
        ).save()

        from src.main import app

        with TestClient(app) as test_client:
            yield test_client, str(company_id), str(vessel_id)

        Route.drop_collection()
        mongoengine.disconnect_all()


def test_get_route_history_endpoint(client):
    test_client, company_id, vessel_id = client
    response = test_client.get(
        "/api/v1/routes/history",
        params={"company_id": company_id, "vessel_id": vessel_id},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["filters"]["company_id"] == company_id


def test_get_route_analytics_endpoint(client):
    test_client, company_id, _ = client
    response = test_client.get(
        "/api/v1/routes/analytics",
        params={"company_id": company_id},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_routes"] == 2
    assert data["totals"]["distance_nm"] == pytest.approx(250.0)
    assert data["by_optimization_mode"]["fastest"]["count"] == 1
    assert data["by_optimization_mode"]["eco"]["count"] == 1


def test_history_not_shadowed_by_route_id(client):
    test_client, _, _ = client
    response = test_client.get("/api/v1/routes/history")
    assert response.status_code == 200
    assert "items" in response.json()
