import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from src.main import app

@pytest.fixture
def client():
    # Mock database connection to use mongomock
    with patch("src.infrastructure.database.database.mongoengine.connect") as mock_connect, \
         patch("src.infrastructure.database.database.mongoengine.disconnect"):
        import mongoengine
        import mongomock
        mongoengine.connect("testdb", host="mongodb://localhost", mongo_client_class=mongomock.MongoClient)
        with TestClient(app) as test_client:
            yield test_client
        mongoengine.disconnect()

def test_get_ports(client: TestClient):
    response = client.get("/api/v1/routes/ports")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "port_id" in data[0]
    assert "name" in data[0]
    assert "lat" in data[0]

def test_calculate_route_fastest(client: TestClient):
    payload = {
        "company_id": "000000000000000000000001",
        "start_node_id": "GENOA",
        "end_node_id": "MARSEILLE",
        "optimization_mode": "fastest"
    }
    response = client.post("/api/v1/routes/calculate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "total_distance_nm" in data
    assert "waypoints" in data
    assert len(data["waypoints"]) >= 2
    assert data["waypoints"][0]["name"] == "Genoa"

def test_calculate_route_invalid_port(client: TestClient):
    payload = {
        "company_id": "000000000000000000000001",
        "start_node_id": "FAKE_PORT",
        "end_node_id": "MARSEILLE",
        "optimization_mode": "fastest"
    }
    response = client.post("/api/v1/routes/calculate", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert "Port 'FAKE_PORT' not found" in data["detail"]
