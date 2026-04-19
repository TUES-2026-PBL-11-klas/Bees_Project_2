from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List
from src.core.graph import NavigationGraph, Waypoint
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


class FastestStrategy(RoutingStrategy):
    """
    Find the shortest-distance route.

    If a vessel is provided, edges whose draft restriction is exceeded
    by the vessel's draft will be blocked before pathfinding.
    """

    def calculate_route(
        self,
        graph: NavigationGraph,
        start_id: str,
        end_id: str,
        vessel: Optional[VesselConstraints] = None,
    ) -> Optional[List[Waypoint]]:
        working_graph = _prepare_graph(graph, vessel)
        return working_graph.find_path(start_id, end_id)


class EcoStrategy(RoutingStrategy):
    """
    Find a route that additionally avoids active ecological/restricted zones.

    Draft restrictions from the vessel are also applied.
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
        eco_graph = _prepare_graph(graph, vessel)


        for node_id in list(eco_graph._adjacency.keys()):
            for edge in eco_graph._adjacency.get(node_id, []):
                if edge.is_blocked:
                    continue

                route_segment = [
                    [edge.source.longitude, edge.source.latitude],
                    [edge.destination.longitude, edge.destination.latitude]
                ]

                if self.spatial_service.is_route_blocked(route_segment, vessel):
                    edge.block()

        return eco_graph.find_path(start_id, end_id)




def _copy_graph(graph: NavigationGraph) -> NavigationGraph:
    """Deep-copy a NavigationGraph (nodes + edges) for safe mutation."""
    from src.core.graph import Edge as _Edge

    copied = NavigationGraph()
    for waypoint in graph.get_all_waypoints():
        copied.add_waypoint(waypoint)

    for source_id, edges in graph._adjacency.items():
        for edge in edges:
            new_edge = copied.add_edge(
                source_id,
                edge.destination.node_id,
                max_draft_m=edge.max_draft_m,
                max_length_m=edge.max_length_m,
                max_beam_m=edge.max_beam_m,
            )
            if edge.is_blocked:
                new_edge.block()

    return copied


def _prepare_graph(
    graph: NavigationGraph,
    vessel: Optional[VesselConstraints],
) -> NavigationGraph:
    """
    Copy the graph and apply vessel-specific edge blocking.

    Blocks edges where:
    - Vessel draft exceeds the edge's max_draft_m.
    - Vessel beam/length exceeds canal constraints (Messina Strait ≤ 8m draft).
    """
    working = _copy_graph(graph)

    if vessel is None:
        return working

    vessel_draft = vessel.max_draft_m
    vessel_length = vessel.length_m
    vessel_beam = vessel.beam_m

    for edges in working._adjacency.values():
        for edge in edges:
            if edge.is_blocked:
                continue

            if vessel_draft is not None and edge.max_draft_m is not None and vessel_draft > edge.max_draft_m:
                edge.block()
                continue

            if vessel_length is not None and edge.max_length_m is not None and vessel_length > edge.max_length_m:
                edge.block()
                continue

            if vessel_beam is not None and edge.max_beam_m is not None and vessel_beam > edge.max_beam_m:
                edge.block()
                continue

    return working
