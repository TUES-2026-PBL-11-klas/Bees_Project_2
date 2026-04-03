from abc import ABC, abstractmethod
from typing import Optional, List
from src.core.graph import NavigationGraph, Waypoint
from src.core.spatial.zone_spatial_service import ZoneSpatialService

class RoutingStrategy(ABC):
    @abstractmethod
    def calculate_route(self, graph: NavigationGraph, start_id: str, end_id: str) -> Optional[List[Waypoint]]:
        pass

class FastestStrategy(RoutingStrategy):
    def calculate_route(self, graph: NavigationGraph, start_id: str, end_id: str) -> Optional[List[Waypoint]]:
        return graph.find_path(start_id, end_id)

class EcoStrategy(RoutingStrategy):
    def __init__(self, spatial_service: Optional[ZoneSpatialService] = None):
        self.spatial_service = spatial_service or ZoneSpatialService()

    def _copy_graph(self, graph: NavigationGraph) -> NavigationGraph:
        copied = NavigationGraph()

        for waypoint in graph.get_all_waypoints():
            copied.add_waypoint(waypoint)

        for source_id, edges in graph._adjacency.items():
            for edge in edges:
                new_edge = copied.add_edge(source_id, edge.destination.node_id)
                if edge.is_blocked:
                    new_edge.block()

        return copied

    def calculate_route(self, graph: NavigationGraph, start_id: str, end_id: str) -> Optional[List[Waypoint]]:
        eco_graph = self._copy_graph(graph)

        for node_id, edges in eco_graph._adjacency.items():
            for edge in edges:
                if edge.is_blocked:
                    continue

                route_segment = [
                    [edge.source.longitude, edge.source.latitude],
                    [edge.destination.longitude, edge.destination.latitude]
                ]

                if self.spatial_service.is_route_blocked(route_segment):
                    edge.block()

        return eco_graph.find_path(start_id, end_id)
