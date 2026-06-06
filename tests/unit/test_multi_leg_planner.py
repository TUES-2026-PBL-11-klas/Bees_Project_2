"""Unit tests for the multi-leg voyage planner."""

from __future__ import annotations

from typing import Optional

import pytest

from src.core.graph import NavigationGraph, Waypoint
from src.core.routing.strategy import RoutingStrategy, VesselConstraints
from src.core.services.multi_leg_planner import MultiLegPlanner, VoyagePlan


# A *plain* navigation graph with 4 nodes laid out roughly along the equator.
# We don't need land masking or A* for these unit tests — we feed the planner
# a stub strategy that returns the straight-line path.


def _make_graph() -> NavigationGraph:
    graph = NavigationGraph()
    points = {
        "A": (0.0, 0.0),
        "B": (1.0, 0.0),
        "C": (2.0, 0.0),
        "D": (3.0, 0.0),
    }
    for name, (lon, lat) in points.items():
        graph.add_waypoint(Waypoint(node_id=name, longitude=lon, latitude=lat))
    return graph


class _StraightLineStrategy(RoutingStrategy):
    """Trivial strategy: return [start, end] for any in-graph pair."""

    def calculate_route(
        self,
        graph: NavigationGraph,
        start_id: str,
        end_id: str,
        vessel: Optional[VesselConstraints] = None,
    ):
        if not graph.has_waypoint(start_id) or not graph.has_waypoint(end_id):
            return None
        return [graph._nodes[start_id], graph._nodes[end_id]]


@pytest.fixture
def planner():
    return MultiLegPlanner(_make_graph(), _StraightLineStrategy())


class TestPlanInOrder:
    def test_two_port_voyage(self, planner):
        plan = planner.plan(["A", "B"])
        assert plan.legs_failed == 0
        assert len(plan.legs) == 1
        assert plan.legs[0].from_port == "A"
        assert plan.legs[0].to_port == "B"
        assert plan.legs[0].distance_nm > 0
        assert plan.reordered is False

    def test_four_port_voyage_keeps_order(self, planner):
        plan = planner.plan(["A", "B", "C", "D"])
        assert [l.from_port for l in plan.legs] == ["A", "B", "C"]
        assert [l.to_port for l in plan.legs] == ["B", "C", "D"]
        assert plan.total_distance_nm == pytest.approx(
            sum(l.distance_nm for l in plan.legs)
        )

    def test_less_than_two_ports_raises(self, planner):
        with pytest.raises(ValueError):
            planner.plan(["A"])

    def test_unknown_port_skips_leg(self, planner):
        plan = planner.plan(["A", "GHOSTPORT", "B"])
        # A→GHOST and GHOST→B both fail to resolve.
        assert plan.legs_failed == 2
        assert plan.legs == []


class TestOrderOptimisation:
    def test_optimisation_finds_shorter_order(self, planner):
        # Input order A → D → B → C (back-and-forth, long).
        # Best fixed-endpoints order: A → B → C → D (since first/last fixed
        # are A and C — let's swap end).
        plan = planner.plan(["A", "D", "B", "C"])
        baseline = plan.total_distance_nm

        optimised = planner.plan_optimised(
            ["A", "D", "B", "C"], objective="distance",
        )
        assert optimised.total_distance_nm <= baseline
        # The first and last must be preserved by the contract.
        assert optimised.order[0] == "A"
        assert optimised.order[-1] == "C"

    def test_optimisation_with_three_ports_is_a_noop(self, planner):
        # With 3 ports there's only one intermediate so no permutation can win.
        plan = planner.plan_optimised(["A", "B", "C"])
        assert plan.order == ["A", "B", "C"]

    def test_optimisation_with_two_ports_falls_through(self, planner):
        plan = planner.plan_optimised(["A", "B"])
        assert plan.order == ["A", "B"]
        assert plan.reordered is False


class TestFuelComputation:
    def test_vessel_with_known_rate_burns_more(self, planner):
        rate_low = VesselConstraints(fuel_consumption_rate=0.02, fuel_multiplier=1.0)
        rate_high = VesselConstraints(fuel_consumption_rate=0.20, fuel_multiplier=1.0)

        plan_low = planner.plan(["A", "B"], vessel=rate_low)
        plan_high = planner.plan(["A", "B"], vessel=rate_high)

        assert plan_high.total_fuel_tons > plan_low.total_fuel_tons

    def test_resistance_coefficient_increases_fuel(self, planner):
        baseline = VesselConstraints(fuel_consumption_rate=0.05, fuel_multiplier=1.0)
        dragged = VesselConstraints(
            fuel_consumption_rate=0.05,
            fuel_multiplier=1.0,
            hydro_resistance_coef=1.2,
        )
        assert (
            planner.plan(["A", "B"], vessel=dragged).total_fuel_tons
            > planner.plan(["A", "B"], vessel=baseline).total_fuel_tons
        )
