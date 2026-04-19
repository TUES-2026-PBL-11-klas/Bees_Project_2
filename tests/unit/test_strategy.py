import pytest

from src.core.graph import NavigationGraph, Waypoint
from src.core.routing.strategy import EcoStrategy, FastestStrategy


class StubZoneSpatialService:
    def __init__(self, blocked_segments: set[tuple[str, str]]):
        self.blocked_segments = blocked_segments

    def is_route_blocked(self, coordinates: list[list[float]], vessel=None) -> bool:
        src = tuple(coordinates[0])
        dst = tuple(coordinates[1])
        return (str(src), str(dst)) in self.blocked_segments


@pytest.fixture()
def graph() -> NavigationGraph:
    g = NavigationGraph()

    malta = Waypoint("MALTA", 35.9042, 14.5189, "Malta")
    piraeus = Waypoint("PIRAEUS", 37.9475, 23.6425, "Piraeus")
    tripoli = Waypoint("TRIPOLI", 32.8752, 13.1875, "Tripoli")

    g.add_waypoint(malta)
    g.add_waypoint(piraeus)
    g.add_waypoint(tripoli)

    g.add_edge("MALTA", "PIRAEUS")
    g.add_edge("MALTA", "TRIPOLI")
    g.add_edge("TRIPOLI", "PIRAEUS")

    return g


def test_fastest_strategy_finds_direct_path(graph: NavigationGraph):
    strategy = FastestStrategy()

    path = strategy.calculate_route(graph, "MALTA", "PIRAEUS")

    assert path is not None
    assert [wp.node_id for wp in path] == ["MALTA", "PIRAEUS"]


def test_eco_strategy_blocks_zone_crossing_and_reroutes(graph: NavigationGraph):
    blocked_segment = (
        str((14.5189, 35.9042)),
        str((23.6425, 37.9475)),
    )
    strategy = EcoStrategy(spatial_service=StubZoneSpatialService({blocked_segment}))

    path = strategy.calculate_route(graph, "MALTA", "PIRAEUS")

    assert path is not None
    assert [wp.node_id for wp in path] == ["MALTA", "TRIPOLI", "PIRAEUS"]


def test_eco_strategy_does_not_mutate_original_graph(graph: NavigationGraph):
    blocked_segment = (
        str((14.5189, 35.9042)),
        str((23.6425, 37.9475)),
    )
    strategy = EcoStrategy(spatial_service=StubZoneSpatialService({blocked_segment}))

    _ = strategy.calculate_route(graph, "MALTA", "PIRAEUS")

    direct_edges = [
        edge
        for edge in graph._adjacency["MALTA"]
        if edge.destination.node_id == "PIRAEUS"
    ]
    assert len(direct_edges) == 1
    assert direct_edges[0].is_blocked is False
