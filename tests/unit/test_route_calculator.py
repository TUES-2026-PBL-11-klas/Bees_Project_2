"""
Unit tests for src/core/routing/route_calculator.py

Run with:  python -m pytest tests/unit/test_route_calculator.py -v
"""

import pytest
from typing import Optional
from unittest.mock import MagicMock

from src.core.graph import NavigationGraph, Waypoint
from src.core.routing.strategy import RoutingStrategy
from src.core.routing.route_calculator import (
    ParallelRouteCalculator,
    RouteRequest,
    RouteResult,
)



class StubStrategy(RoutingStrategy):
    """
    A test double for RoutingStrategy.

    Returns a fixed path or None depending on constructor argument.
    """

    def __init__(self, path: Optional[list[Waypoint]]):
        self._path = path

    def calculate_route(
        self,
        graph: NavigationGraph,
        start_id: str,
        end_id: str,
    ) -> Optional[list[Waypoint]]:
        return self._path


class ErrorStrategy(RoutingStrategy):
    """A strategy that always raises an exception — simulates a crash."""

    def calculate_route(self, graph, start_id, end_id):
        raise RuntimeError("Simulated strategy failure")



@pytest.fixture()
def malta() -> Waypoint:
    return Waypoint("MALTA", 35.9042, 14.5189, "Malta")


@pytest.fixture()
def piraeus() -> Waypoint:
    return Waypoint("PIRAEUS", 37.9475, 23.6425, "Piraeus")


@pytest.fixture()
def tripoli() -> Waypoint:
    return Waypoint("TRIPOLI", 32.8752, 13.1875, "Tripoli")


@pytest.fixture()
def simple_graph(malta, piraeus, tripoli) -> NavigationGraph:
    g = NavigationGraph()
    for wp in (malta, piraeus, tripoli):
        g.add_waypoint(wp)
    g.add_edge("MALTA", "PIRAEUS", bidirectional=True)
    g.add_edge("MALTA", "TRIPOLI", bidirectional=True)
    g.add_edge("TRIPOLI", "PIRAEUS", bidirectional=True)
    return g


@pytest.fixture()
def calculator(simple_graph) -> ParallelRouteCalculator:
    return ParallelRouteCalculator(simple_graph, max_workers=4)


class TestRouteRequest:
    def test_fields_are_stored(self, simple_graph, malta, piraeus):
        strategy = StubStrategy([malta, piraeus])
        req = RouteRequest("V1", "MALTA", "PIRAEUS", strategy)
        assert req.vessel_id == "V1"
        assert req.start_id == "MALTA"
        assert req.end_id == "PIRAEUS"
        assert req.strategy is strategy


class TestRouteResult:
    def test_default_values(self):
        result = RouteResult(vessel_id="V1")
        assert result.waypoints is None
        assert result.success is False
        assert result.error is None

    def test_successful_result(self, malta, piraeus):
        result = RouteResult(vessel_id="V1", waypoints=[malta, piraeus], success=True)
        assert result.success is True
        assert len(result.waypoints) == 2

    def test_failed_result_with_error(self):
        result = RouteResult(vessel_id="V1", success=False, error="No path found")
        assert result.success is False
        assert result.error == "No path found"



class TestParallelRouteCalculatorConstruction:
    def test_valid_construction(self, simple_graph):
        calc = ParallelRouteCalculator(simple_graph, max_workers=2)
        assert calc is not None

    def test_invalid_max_workers_raises(self, simple_graph):
        with pytest.raises(ValueError):
            ParallelRouteCalculator(simple_graph, max_workers=0)

    def test_negative_max_workers_raises(self, simple_graph):
        with pytest.raises(ValueError):
            ParallelRouteCalculator(simple_graph, max_workers=-1)



class TestCalculateRoutes:
    def test_empty_request_list_returns_empty(self, calculator):
        results = calculator.calculate_routes([])
        assert results == []

    def test_single_successful_request(self, calculator, malta, piraeus):
        strategy = StubStrategy([malta, piraeus])
        req = RouteRequest("V1", "MALTA", "PIRAEUS", strategy)
        results = calculator.calculate_routes([req])

        assert len(results) == 1
        assert results[0].vessel_id == "V1"
        assert results[0].success is True
        assert results[0].waypoints == [malta, piraeus]

    def test_single_no_path_request(self, calculator):
        strategy = StubStrategy(None)
        req = RouteRequest("V1", "MALTA", "PIRAEUS", strategy)
        results = calculator.calculate_routes([req])

        assert len(results) == 1
        assert results[0].success is False
        assert results[0].error is not None

    def test_multiple_requests_all_succeed(self, calculator, malta, piraeus, tripoli):
        requests = [
            RouteRequest("V1", "MALTA", "PIRAEUS", StubStrategy([malta, piraeus])),
            RouteRequest("V2", "MALTA", "TRIPOLI", StubStrategy([malta, tripoli])),
            RouteRequest("V3", "TRIPOLI", "PIRAEUS", StubStrategy([tripoli, piraeus])),
        ]
        results = calculator.calculate_routes(requests)

        assert len(results) == 3
        assert all(r.success for r in results)

    def test_results_preserve_order(self, calculator, malta, piraeus, tripoli):
        """Results must be in the same order as the input requests."""
        requests = [
            RouteRequest("V1", "MALTA", "PIRAEUS", StubStrategy([malta, piraeus])),
            RouteRequest("V2", "MALTA", "TRIPOLI", StubStrategy([malta, tripoli])),
            RouteRequest("V3", "TRIPOLI", "PIRAEUS", StubStrategy([tripoli, piraeus])),
        ]
        results = calculator.calculate_routes(requests)

        assert results[0].vessel_id == "V1"
        assert results[1].vessel_id == "V2"
        assert results[2].vessel_id == "V3"

    def test_one_failing_does_not_cancel_others(self, calculator, malta, piraeus):
        """A crashing strategy should not prevent other routes from completing."""
        requests = [
            RouteRequest("V1", "MALTA", "PIRAEUS", StubStrategy([malta, piraeus])),
            RouteRequest("V2", "MALTA", "PIRAEUS", ErrorStrategy()),
            RouteRequest("V3", "MALTA", "PIRAEUS", StubStrategy([malta, piraeus])),
        ]
        results = calculator.calculate_routes(requests)

        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is False
        assert results[1].error == "Simulated strategy failure"
        assert results[2].success is True

    def test_mixed_success_and_no_path(self, calculator, malta, piraeus):
        requests = [
            RouteRequest("V1", "MALTA", "PIRAEUS", StubStrategy([malta, piraeus])),
            RouteRequest("V2", "MALTA", "PIRAEUS", StubStrategy(None)),
        ]
        results = calculator.calculate_routes(requests)

        assert results[0].success is True
        assert results[1].success is False

    def test_large_batch_all_complete(self, calculator, malta, piraeus):
        """Stress test — 20 concurrent requests should all return results."""
        requests = [
            RouteRequest(f"V{i}", "MALTA", "PIRAEUS", StubStrategy([malta, piraeus]))
            for i in range(20)
        ]
        results = calculator.calculate_routes(requests)

        assert len(results) == 20
        assert all(r.success for r in results)


class TestCalculateSingleRoute:
    def test_success(self, calculator, malta, piraeus):
        strategy = StubStrategy([malta, piraeus])
        req = RouteRequest("V1", "MALTA", "PIRAEUS", strategy)
        result = calculator.calculate_single_route(req)

        assert result.success is True
        assert result.vessel_id == "V1"
        assert result.waypoints == [malta, piraeus]

    def test_no_path(self, calculator):
        req = RouteRequest("V1", "MALTA", "PIRAEUS", StubStrategy(None))
        result = calculator.calculate_single_route(req)

        assert result.success is False
        assert "No path" in result.error

    def test_strategy_exception_returns_failed_result(self, calculator):
        req = RouteRequest("V1", "MALTA", "PIRAEUS", ErrorStrategy())
        result = calculator.calculate_single_route(req)

        assert result.success is False
        assert result.error == "Simulated strategy failure"
