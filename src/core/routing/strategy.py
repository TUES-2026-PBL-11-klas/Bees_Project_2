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
    def __init__(self):
        self.spatial_service = ZoneSpatialService()

    def calculate(self, request):
        return {"route": "eco path", "request": request}

    def calculate_route(self, graph: NavigationGraph, start_id: str, end_id: str) -> Optional[List[Waypoint]]:
        edges_to_unblock = []

        for node_id, edges in graph._adjacency.items():
            for edge in edges:
                if edge.is_blocked:
                    continue

                route_segment = [
                    [edge.source.longitude, edge.source.latitude],
                    [edge.destination.longitude, edge.destination.latitude]
                ]

                if self.spatial_service.is_route_blocked(route_segment):
                    edge.block()
                    edges_to_unblock.append(edge)

        path = graph.find_path(start_id, end_id)

        for edge in edges_to_unblock:
            edge.unblock()

        return path
