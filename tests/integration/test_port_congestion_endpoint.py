"""Integration tests for GET /api/v1/ports/{port_id}/congestion."""

from __future__ import annotations

from datetime import datetime, timedelta

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
        "testdb_congestion_endpoint",
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
def clean_data():
    from src.models.port_scheduling import DockReservation, Port
    Port.drop_collection()
    DockReservation.drop_collection()


PORT_ID = "ROTTERDAM"


def _create_port(berth_count: int = 2):
    from src.models.port_scheduling import Port
    Port(
        port_id=PORT_ID,
        name="Rotterdam",
        latitude=51.9,
        longitude=4.5,
        berth_count=berth_count,
    ).save()


def _add_reservation(berth: int, start: datetime, end: datetime, status: str = "scheduled"):
    from src.models.port_scheduling import DockReservation
    DockReservation(
        port_id=PORT_ID,
        berth_number=berth,
        vessel_id=ObjectId(),
        start_at=start,
        end_at=end,
        status=status,
    ).save()


class TestCongestionEndpoint:
    def test_unknown_port_returns_404(self, client):
        resp = client.get("/api/v1/ports/MARS_BASE_1/congestion")
        assert resp.status_code == 404

    def test_empty_port_returns_zero_scores(self, client):
        _create_port(berth_count=3)
        resp = client.get(
            f"/api/v1/ports/{PORT_ID}/congestion",
            params={"horizon_hours": 6},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["port_id"] == PORT_ID
        assert body["berth_count"] == 3
        assert len(body["buckets"]) == 6
        assert body["peak_congestion_score"] == 0.0
        # All berths available in every bucket
        for b in body["buckets"]:
            assert b["available_berths_estimate"] == 3

    def test_booked_port_shows_congestion(self, client):
        _create_port(berth_count=2)
        # Fully book a 1-hour window starting "now"
        from src.core.utc import utc_now
        start = utc_now().replace(minute=0, second=0, microsecond=0)
        _add_reservation(1, start, start + timedelta(hours=1))
        _add_reservation(2, start, start + timedelta(hours=1))

        resp = client.get(
            f"/api/v1/ports/{PORT_ID}/congestion",
            params={
                "start_at": start.isoformat(),
                "horizon_hours": 2,
                "confirmed_weight": 1.0,  # only consider confirmed bookings
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # First bucket should be saturated, second free.
        assert body["buckets"][0]["projected_occupancy"] == 1.0
        assert body["buckets"][0]["available_berths_estimate"] == 0.0
        assert body["buckets"][1]["projected_occupancy"] == 0.0

    def test_invalid_horizon_returns_400(self, client):
        _create_port()
        resp = client.get(
            f"/api/v1/ports/{PORT_ID}/congestion",
            params={"horizon_hours": 1, "bucket_minutes": 120},
        )
        assert resp.status_code == 400

    def test_horizon_at_query_limit(self, client):
        _create_port()
        # 14 days is the upper bound on the endpoint
        resp = client.get(
            f"/api/v1/ports/{PORT_ID}/congestion",
            params={"horizon_hours": 24 * 14, "bucket_minutes": 60 * 12},
        )
        assert resp.status_code == 200
