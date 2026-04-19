"""
Unit tests for src/core/graph.py
Run with:  pytest tests/unit/test_graph.py -v
"""

import math
import pytest

from src.core.graph import (
    Edge,
    NavigationGraph,
    Waypoint,
    haversine,
)


# ---------------------------------------------------------------------------
# Fixtures – a small Mediterranean test graph
#
#   MALTA ──────────────────────────► PIRAEUS
#     │                                   ▲
#     ▼                                   │
#   TRIPOLI ────────────────────────────►─┘
#
# All edges are one-directional unless stated otherwise.
# ---------------------------------------------------------------------------

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
    """
    Graph topology:
        MALTA → PIRAEUS  (direct)
        MALTA → TRIPOLI
        TRIPOLI → PIRAEUS
    """
    g = NavigationGraph()
    for wp in (malta, piraeus, tripoli):
        g.add_waypoint(wp)
    g.add_edge("MALTA", "PIRAEUS")
    g.add_edge("MALTA", "TRIPOLI")
    g.add_edge("TRIPOLI", "PIRAEUS")
    return g


# ---------------------------------------------------------------------------
# haversine()
# ---------------------------------------------------------------------------

class TestHaversine:
    def test_same_point_is_zero(self):
        assert haversine(35.0, 14.0, 35.0, 14.0) == 0.0

    def test_known_distance_approximate(self):
        # Malta → Piraeus ≈ 930 km  (±5 km tolerance)
        dist = haversine(35.9042, 14.5189, 37.9475, 23.6425)
        assert 835_000 < dist < 850_000

    def test_symmetry(self):
        d1 = haversine(35.0, 14.0, 38.0, 24.0)
        d2 = haversine(38.0, 24.0, 35.0, 14.0)
        assert math.isclose(d1, d2, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# Waypoint
# ---------------------------------------------------------------------------

class TestWaypoint:
    def test_distance_to_uses_haversine(self, malta, piraeus):
        expected = haversine(malta.latitude, malta.longitude,
                             piraeus.latitude, piraeus.longitude)
        assert math.isclose(malta.distance_to(piraeus), expected)

    def test_to_geojson_point_structure(self, malta):
        gj = malta.to_geojson_point()
        assert gj["type"] == "Point"
        # GeoJSON uses [longitude, latitude]
        assert gj["coordinates"] == [malta.longitude, malta.latitude]

    def test_waypoint_is_hashable(self, malta):
        """Frozen dataclasses must be usable in sets / as dict keys."""
        s = {malta}
        assert malta in s


# ---------------------------------------------------------------------------
# Edge
# ---------------------------------------------------------------------------

class TestEdge:
    def test_weight_equals_haversine(self, malta, piraeus):
        edge = Edge(malta, piraeus)
        assert math.isclose(edge.weight, malta.distance_to(piraeus))

    def test_default_not_blocked(self, malta, piraeus):
        edge = Edge(malta, piraeus)
        assert edge.is_blocked is False

    def test_block_and_unblock(self, malta, piraeus):
        edge = Edge(malta, piraeus)
        edge.block()
        assert edge.is_blocked is True
        edge.unblock()
        assert edge.is_blocked is False


# ---------------------------------------------------------------------------
# NavigationGraph – construction
# ---------------------------------------------------------------------------

class TestNavigationGraphConstruction:
    def test_add_waypoint_increases_node_count(self, malta):
        g = NavigationGraph()
        g.add_waypoint(malta)
        assert g.node_count() == 1

    def test_add_edge_increases_edge_count(self, simple_graph):
        # Fixture adds 3 edges
        assert simple_graph.edge_count() == 3

    def test_bidirectional_edge_adds_two_edges(self, malta, piraeus):
        g = NavigationGraph()
        g.add_waypoint(malta)
        g.add_waypoint(piraeus)
        g.add_edge("MALTA", "PIRAEUS", bidirectional=True)
        assert g.edge_count() == 2

    def test_add_edge_unknown_source_raises(self, malta, piraeus):
        g = NavigationGraph()
        g.add_waypoint(piraeus)
        with pytest.raises(KeyError):
            g.add_edge("UNKNOWN", "PIRAEUS")

    def test_add_edge_unknown_destination_raises(self, malta, piraeus):
        g = NavigationGraph()
        g.add_waypoint(malta)
        with pytest.raises(KeyError):
            g.add_edge("MALTA", "UNKNOWN")

    def test_get_waypoint_returns_correct_node(self, simple_graph, malta):
        wp = simple_graph.get_waypoint("MALTA")
        assert wp == malta

    def test_get_unknown_waypoint_raises(self, simple_graph):
        with pytest.raises(KeyError):
            simple_graph.get_waypoint("NOWHERE")

    def test_get_neighbours_returns_unblocked_only(self, simple_graph):
        # MALTA has edges to PIRAEUS and TRIPOLI
        neighbours = {wp.node_id for wp in simple_graph.get_neighbours("MALTA")}
        assert neighbours == {"PIRAEUS", "TRIPOLI"}


# ---------------------------------------------------------------------------
# NavigationGraph – A* path finding
# ---------------------------------------------------------------------------

class TestAStarPathFinding:
    def test_direct_path_found(self, simple_graph):
        path = simple_graph.find_path("MALTA", "PIRAEUS")
        assert path is not None
        assert path[0].node_id == "MALTA"
        assert path[-1].node_id == "PIRAEUS"

    def test_path_to_self_is_single_node(self, simple_graph):
        path = simple_graph.find_path("MALTA", "MALTA")
        assert path == [simple_graph.get_waypoint("MALTA")]

    def test_no_path_returns_none(self, malta, piraeus):
        """Graph with no edges → no path."""
        g = NavigationGraph()
        g.add_waypoint(malta)
        g.add_waypoint(piraeus)
        # No edges added
        assert g.find_path("MALTA", "PIRAEUS") is None

    def test_blocked_direct_edge_uses_alternative(self, simple_graph):
        """
        Block MALTA → PIRAEUS; the algorithm should reroute via TRIPOLI.
        """
        simple_graph.block_edge("MALTA", "PIRAEUS")
        path = simple_graph.find_path("MALTA", "PIRAEUS")
        assert path is not None
        node_ids = [wp.node_id for wp in path]
        assert node_ids == ["MALTA", "TRIPOLI", "PIRAEUS"]

    def test_all_paths_blocked_returns_none(self, simple_graph):
        simple_graph.block_edge("MALTA", "PIRAEUS")
        simple_graph.block_edge("MALTA", "TRIPOLI")
        assert simple_graph.find_path("MALTA", "PIRAEUS") is None

    def test_path_contains_only_registered_waypoints(self, simple_graph):
        path = simple_graph.find_path("MALTA", "PIRAEUS")
        all_ids = {wp.node_id for wp in simple_graph.get_all_waypoints()}
        for wp in path:
            assert wp.node_id in all_ids

    def test_unblock_restores_direct_path(self, simple_graph):
        simple_graph.block_edge("MALTA", "PIRAEUS")
        simple_graph.unblock_edge("MALTA", "PIRAEUS")
        path = simple_graph.find_path("MALTA", "PIRAEUS")
        assert path is not None
        assert path[0].node_id == "MALTA"
        assert path[-1].node_id == "PIRAEUS"

    def test_block_nonexistent_edge_raises(self, simple_graph):
        with pytest.raises(KeyError):
            simple_graph.block_edge("PIRAEUS", "MALTA")  # reverse doesn't exist

    def test_unknown_origin_raises(self, simple_graph):
        with pytest.raises(KeyError):
            simple_graph.find_path("NOWHERE", "PIRAEUS")

    def test_unknown_destination_raises(self, simple_graph):
        with pytest.raises(KeyError):
            simple_graph.find_path("MALTA", "NOWHERE")
