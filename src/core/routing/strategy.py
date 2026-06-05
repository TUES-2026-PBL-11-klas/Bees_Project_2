from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Callable
from src.core.graph import NavigationGraph, Waypoint, Edge
from src.core.spatial.zone_spatial_service import ZoneSpatialService


@dataclass
class VesselConstraints:
    """
    Vessel parameters that influence routing decisions.

    Attributes:
        vessel_type:          One of the VESSEL_TYPES strings (e.g. "tanker").
        max_draft_m:          Maximum draft of the vessel (metres).  Passages
                              whose max_draft_m is less than this are blocked.
        max_speed_knots:      Service speed in knots, used to estimate duration.
        fuel_consumption_rate: Base fuel consumption rate (tonnes per NM).
        fuel_multiplier:      Type-specific multiplier from the Vessel subclass.
        length_m:             Vessel length (metres) – can restrict canals.
        beam_m:               Vessel beam (metres) – can restrict canals.
    """
    vessel_type: Optional[str] = None
    max_draft_m: Optional[float] = None
    max_speed_knots: Optional[float] = None
    fuel_consumption_rate: Optional[float] = None
    fuel_multiplier: float = 1.0
    length_m: Optional[float] = None
    beam_m: Optional[float] = None



DEFAULT_SPEED_KNOTS = 14.0
DEFAULT_FUEL_RATE = 0.05
METRES_PER_NM = 1852.0


class RoutingStrategy(ABC):
    @abstractmethod
    def calculate_route(
        self,
        graph: NavigationGraph,
        start_id: str,
        end_id: str,
        vessel: Optional[VesselConstraints] = None,
    ) -> Optional[List[Waypoint]]:
        pass


def _make_vessel_filter(vessel: Optional[VesselConstraints]) -> Optional[Callable[[Edge], bool]]:
    """
    Build an edge-filter callback for vessel constraint checks.

    Returns None if no vessel is given (no filtering needed).
    The filter returns True if the edge is passable, False if blocked.
    """
    if vessel is None:
        return None

    v_draft = vessel.max_draft_m
    v_length = vessel.length_m
    v_beam = vessel.beam_m

    # Fast path: vessel has no dimensional constraints at all
    if v_draft is None and v_length is None and v_beam is None:
        return None

    def _filter(edge: Edge) -> bool:
        if v_draft is not None and edge.max_draft_m is not None and v_draft > edge.max_draft_m:
            return False
        if v_length is not None and edge.max_length_m is not None and v_length > edge.max_length_m:
            return False
        if v_beam is not None and edge.max_beam_m is not None and v_beam > edge.max_beam_m:
            return False
        return True

    return _filter


class FastestStrategy(RoutingStrategy):
    """
    Find the shortest-distance route.

    If a vessel is provided, edges whose draft / length / beam restriction
    is exceeded by the vessel will be filtered out during pathfinding.

    Uses the shared graph directly (no copy) for maximum speed.
    """

    def calculate_route(
        self,
        graph: NavigationGraph,
        start_id: str,
        end_id: str,
        vessel: Optional[VesselConstraints] = None,
    ) -> Optional[List[Waypoint]]:
        edge_filter = _make_vessel_filter(vessel)
        return graph.find_path(start_id, end_id, edge_filter=edge_filter)


class EcoStrategy(RoutingStrategy):
    """
    Find a route that additionally avoids active ecological / restricted zones.

    Draft / length / beam restrictions from the vessel are also applied.

    Zone intersection checks are performed **lazily** — only edges that A*
    actually explores get checked against the database.  This reduces zone
    queries from ~8 000 (one per edge in the graph) to ~50–100 (only the
    edges in the explored portion of the search tree), cutting query time
    from minutes to under a second.
    """

    def __init__(self, spatial_service: Optional[ZoneSpatialService] = None):
        self.spatial_service = spatial_service or ZoneSpatialService()

    def calculate_route(
        self,
        graph: NavigationGraph,
        start_id: str,
        end_id: str,
        vessel: Optional[VesselConstraints] = None,
    ) -> Optional[List[Waypoint]]:

        vessel_filter = _make_vessel_filter(vessel)

        # Cache zone-check results so repeated edge visits don't re-query
        zone_cache: dict[tuple[str, str], bool] = {}

        def eco_filter(edge: Edge) -> bool:
            # 1. Vessel dimensional constraints (cheap, no DB)
            if vessel_filter is not None and not vessel_filter(edge):
                return False

            # 2. Zone intersection check (expensive, cached)
            key = (edge.source.node_id, edge.destination.node_id)
            if key not in zone_cache:
                route_segment = [
                    [edge.source.longitude, edge.source.latitude],
                    [edge.destination.longitude, edge.destination.latitude],
                ]
                zone_cache[key] = not self.spatial_service.is_route_blocked(
                    route_segment, vessel,
                )
            return zone_cache[key]

        return graph.find_path(start_id, end_id, edge_filter=eco_filter)


class CurrentAwareStrategy(RoutingStrategy):
    """
    A routing strategy that accounts for ocean currents.

    Wraps a base strategy (FastestStrategy or EcoStrategy) and adjusts
    edge weights using ocean current data before pathfinding.  Edges with
    favourable currents become cheaper to traverse; opposing currents
    make them more expensive.

    Usage::

        base = FastestStrategy()
        strategy = CurrentAwareStrategy(base, current_data)
        path = strategy.calculate_route(graph, start, end, vessel)

    ``current_data`` is a dict mapping ``(lat, lon)`` grid keys to
    ``(u_ms, v_ms)`` tuples.  Grid keys are rounded to 0.5° for lookup.
    """

    def __init__(
        self,
        base_strategy: RoutingStrategy,
        current_data: Optional[dict] = None,
    ) -> None:
        self._base = base_strategy
        self._current_data = current_data or {}

    @staticmethod
    def _grid_key(lat: float, lon: float) -> tuple[float, float]:
        """Round to 0.5° grid for cache/lookup efficiency."""
        return (round(lat * 2) / 2, round(lon * 2) / 2)

    def _inject_currents(self, graph: NavigationGraph) -> None:
        """
        Set current_u / current_v on every edge in the graph using
        the midpoint of each edge to look up current data.
        """
        if not self._current_data:
            return

        for node_id in list(graph._nodes.keys()):
            for edge in graph.get_edges(node_id):
                mid_lat = (edge.source.latitude + edge.destination.latitude) / 2
                mid_lon = (edge.source.longitude + edge.destination.longitude) / 2
                key = self._grid_key(mid_lat, mid_lon)
                if key in self._current_data:
                    u, v = self._current_data[key]
                    edge.current_u = u
                    edge.current_v = v

    def calculate_route(
        self,
        graph: NavigationGraph,
        start_id: str,
        end_id: str,
        vessel: Optional[VesselConstraints] = None,
    ) -> Optional[List[Waypoint]]:
        """
        Calculate a current-aware route.

        1. Inject current data into graph edges.
        2. Delegate to the base strategy for pathfinding.

        The base strategy's A* will pick up the effective_weight
        through the edge filter or directly, depending on the strategy.
        """
        self._inject_currents(graph)
        return self._base.calculate_route(graph, start_id, end_id, vessel)
