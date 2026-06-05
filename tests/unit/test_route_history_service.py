from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId

from src.core.services.route_history_service import RouteHistoryService
from src.infrastructure.repositories.route_repository import RouteRepository
from src.models.route import Route


@pytest.fixture
def seeded_routes():
    company_a = ObjectId()
    company_b = ObjectId()
    vessel_a = ObjectId()
    vessel_b = ObjectId()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    Route(
        request_id=ObjectId(),
        company_id=company_a,
        vessel_id=vessel_a,
        optimization_mode="fastest",
        total_distance_nm=100.0,
        estimated_duration_h=10.0,
        estimated_fuel_tons=50.0,
        is_valid=True,
        calculated_at=now - timedelta(days=2),
    ).save()
    Route(
        request_id=ObjectId(),
        company_id=company_a,
        vessel_id=vessel_b,
        optimization_mode="eco",
        total_distance_nm=200.0,
        estimated_duration_h=20.0,
        estimated_fuel_tons=80.0,
        is_valid=True,
        calculated_at=now - timedelta(days=1),
    ).save()
    Route(
        request_id=ObjectId(),
        company_id=company_b,
        vessel_id=vessel_a,
        optimization_mode="eco",
        total_distance_nm=150.0,
        estimated_duration_h=15.0,
        estimated_fuel_tons=60.0,
        is_valid=False,
        calculated_at=now,
    ).save()

    yield {
        "company_a": str(company_a),
        "company_b": str(company_b),
        "vessel_a": str(vessel_a),
        "vessel_b": str(vessel_b),
        "now": now,
    }

    Route.drop_collection()


def test_history_filters_by_company(seeded_routes):
    service = RouteHistoryService(RouteRepository())
    result = service.get_history(company_id=seeded_routes["company_a"])

    assert result.total == 2
    assert len(result.items) == 2
    assert all(item.company_id == seeded_routes["company_a"] for item in result.items)


def test_analytics_aggregates_by_mode(seeded_routes):
    service = RouteHistoryService(RouteRepository())
    result = service.get_analytics(company_id=seeded_routes["company_a"])

    assert result.total_routes == 2
    assert result.valid_routes == 2
    assert result.totals.distance_nm == pytest.approx(300.0)
    assert "fastest" in result.by_optimization_mode
    assert "eco" in result.by_optimization_mode
    assert result.by_optimization_mode["fastest"].count == 1


def test_history_rejects_invalid_company_id():
    service = RouteHistoryService(RouteRepository())
    with pytest.raises(ValueError, match="company_id"):
        service.get_history(company_id="not-an-object-id")
