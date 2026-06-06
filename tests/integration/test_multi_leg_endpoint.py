"""Integration tests for POST /api/v1/routes/multi-leg."""

from __future__ import annotations

import pytest
import mongomock
import mongoengine
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch


@pytest.fixture(scope="session", autouse=True)
def mock_db():
    mongoengine.disconnect_all()
    mongoengine.connect(
        "testdb_multi_leg",
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


@pytest.fixture(scope="module")
def real_port_ids():
    """Pull three known ports from the runtime graph so the test stays
    aligned with the real port catalog (and doesn't break when the seed
    data is refreshed)."""
    from src.api.v1.routers.routes import _GRAPH
    nodes = list(_GRAPH._nodes.keys())
    if len(nodes) < 3:
        pytest.skip("Navigation graph has fewer than 3 nodes; cannot run integration")
    return nodes[:3]


class TestMultiLegEndpoint:
    def test_two_port_voyage(self, client, real_port_ids):
        a, b, _ = real_port_ids
        resp = client.post("/api/v1/routes/multi-leg", json={
            "port_ids": [a, b],
            "optimization_mode": "fastest",
            "include_waypoints": False,
        })
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["port_order"] == [a, b]
        assert len(body["legs"]) == 1
        assert body["total_distance_nm"] > 0

    def test_three_port_voyage_returns_two_legs(self, client, real_port_ids):
        a, b, c = real_port_ids
        resp = client.post("/api/v1/routes/multi-leg", json={
            "port_ids": [a, b, c],
            "optimization_mode": "fastest",
            "include_waypoints": False,
        })
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body["legs"]) == 2

    def test_unknown_port_returns_404(self, client, real_port_ids):
        a, _, _ = real_port_ids
        resp = client.post("/api/v1/routes/multi-leg", json={
            "port_ids": [a, "DEFINITELY_NOT_A_PORT_XYZ"],
            "optimization_mode": "fastest",
        })
        assert resp.status_code == 404

    def test_one_port_voyage_is_rejected_by_schema(self, client, real_port_ids):
        a, _, _ = real_port_ids
        resp = client.post("/api/v1/routes/multi-leg", json={
            "port_ids": [a],
            "optimization_mode": "fastest",
        })
        assert resp.status_code == 422

    def test_bad_objective_is_rejected_by_schema(self, client, real_port_ids):
        a, b, _ = real_port_ids
        resp = client.post("/api/v1/routes/multi-leg", json={
            "port_ids": [a, b],
            "optimization_mode": "fastest",
            "optimize_order": True,
            "objective": "diet_coke",
        })
        assert resp.status_code == 422

    def test_optimize_order_smoke(self, client, real_port_ids):
        a, b, c = real_port_ids
        resp = client.post("/api/v1/routes/multi-leg", json={
            "port_ids": [a, b, c],
            "optimization_mode": "fastest",
            "optimize_order": True,
            "objective": "distance",
            "include_waypoints": False,
        })
        assert resp.status_code == 200
        body = resp.json()
        # First and last preserved
        assert body["port_order"][0] == a
        assert body["port_order"][-1] == c
