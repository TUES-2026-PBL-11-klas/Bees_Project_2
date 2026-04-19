from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Optional, List

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in metres between two WGS-84 points."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

@dataclass(frozen=True)
class Waypoint:
    """
    An immutable geographic point on the navigation graph.

    Attributes:
        node_id:   Unique identifier (e.g. port code or grid coordinate string).
        latitude:  WGS-84 latitude  in decimal degrees  [-90,  90].
        longitude: WGS-84 longitude in decimal degrees [-180, 180].
        name:      Human-readable label (optional).
    """
    node_id: str
    latitude: float
    longitude: float
    name: str = ""

    def distance_to(self, other: "Waypoint") -> float:
        """Great-circle distance to *other* in metres."""
        return haversine(self.latitude, self.longitude, other.latitude, other.longitude)

    def to_geojson_point(self) -> dict:
        """Return a GeoJSON Point representation."""
        return {
            "type": "Point",
            "coordinates": [self.longitude, self.latitude],
        }


@dataclass
class Edge:
    """
    A directed, weighted connection between two :class:`Waypoint` nodes.

    Attributes:
        source:       Origin waypoint.
        destination:  Target waypoint.
        weight:       Cost of traversal (metres by default; strategies may
                      override this with fuel-cost or time-cost).
        is_blocked:   When ``True`` the edge is treated as impassable.
        max_draft_m:  Maximum vessel draft (in metres) allowed on this
                      passage.  ``None`` means no restriction.
    """
    source: Waypoint
    destination: Waypoint
    weight: float = field(init=False)
    is_blocked: bool = False
    max_draft_m: Optional[float] = None
    max_length_m: Optional[float] = None
    max_beam_m: Optional[float] = None

    def __post_init__(self) -> None:
        self.weight = self.source.distance_to(self.destination)

    def block(self) -> None:
        """Mark this edge as impassable (e.g. zone restriction applied)."""
        self.is_blocked = True

    def unblock(self) -> None:
        """Remove the impassable flag."""
        self.is_blocked = False

class NavigationGraph:
    """
    Directed weighted graph of maritime :class:`Waypoint` nodes.

    Internally the graph is stored as an adjacency list::

        _adjacency: dict[node_id -> list[Edge]]

    The class exposes an A* path-finding method that respects blocked edges
    (i.e. edges that cross restricted / prohibited zones).

    Example usage::

        graph = NavigationGraph()
        graph.add_waypoint(Waypoint("A", 36.0, 14.0, "Malta"))
        graph.add_waypoint(Waypoint("B", 37.9, 23.7, "Piraeus"))
        graph.add_edge("A", "B")
        graph.add_edge("B", "A")          # undirected pair
        path = graph.find_path("A", "B")
    """

    def __init__(self) -> None:
        self._nodes: dict[str, Waypoint] = {}
        self._adjacency: dict[str, list[Edge]] = {}

    def add_waypoint(self, waypoint: Waypoint) -> None:
        """Register a waypoint. Silently replaces if node_id already exists."""
        self._nodes[waypoint.node_id] = waypoint
        self._adjacency.setdefault(waypoint.node_id, [])

    def add_edge(
        self,
        source_id: str,
        destination_id: str,
        *,
        bidirectional: bool = False,
        max_draft_m: Optional[float] = None,
        max_length_m: Optional[float] = None,
        max_beam_m: Optional[float] = None,
    ) -> Edge:
        """
        Create a directed edge between two registered waypoints.

        Parameters:
            source_id:      node_id of the origin waypoint.
            destination_id: node_id of the destination waypoint.
            bidirectional:  If ``True`` a reverse edge is also created.
            max_draft_m:    Maximum vessel draft allowed on this passage.
            max_length_m:   Maximum vessel length allowed on this passage.
            max_beam_m:     Maximum vessel beam allowed on this passage.

        Returns:
            The newly created :class:`Edge` (forward direction).

        Raises:
            KeyError: If either node_id is not registered in the graph.
        """
        src = self._get_node(source_id)
        dst = self._get_node(destination_id)

        forward = Edge(src, dst, max_draft_m=max_draft_m, max_length_m=max_length_m, max_beam_m=max_beam_m)
        self._adjacency[source_id].append(forward)

        if bidirectional:
            reverse = Edge(dst, src, max_draft_m=max_draft_m, max_length_m=max_length_m, max_beam_m=max_beam_m)
            self._adjacency[destination_id].append(reverse)

        return forward

    def block_edge(self, source_id: str, destination_id: str) -> None:
        """Mark a specific directed edge as blocked."""
        for edge in self._adjacency.get(source_id, []):
            if edge.destination.node_id == destination_id:
                edge.block()
                return
        raise KeyError(f"Edge {source_id} → {destination_id} not found.")

    def unblock_edge(self, source_id: str, destination_id: str) -> None:
        """Remove the blocked flag from a specific directed edge."""
        for edge in self._adjacency.get(source_id, []):
            if edge.destination.node_id == destination_id:
                edge.unblock()
                return
        raise KeyError(f"Edge {source_id} → {destination_id} not found.")

    def find_path(
        self,
        origin_id: str,
        destination_id: str,
    ) -> Optional[list[Waypoint]]:
        """
        Find the shortest unblocked path between two waypoints using A*.

        The heuristic is the Haversine distance to the destination which is
        *admissible* (never over-estimates the true cost) and therefore
        guarantees an optimal solution.

        Parameters:
            origin_id:      node_id of the starting waypoint.
            destination_id: node_id of the target waypoint.

        Returns:
            An ordered list of :class:`Waypoint` objects from origin to
            destination (inclusive), or ``None`` if no path exists.

        Raises:
            KeyError: If either node_id is not registered.
        """
        origin = self._get_node(origin_id)
        destination = self._get_node(destination_id)

        g_score: dict[str, float] = {origin_id: 0.0}

        came_from: dict[str, str] = {}

        open_heap: list[tuple[float, str]] = []
        h0 = origin.distance_to(destination)
        heapq.heappush(open_heap, (h0, origin_id))

        closed: set[str] = set()

        while open_heap:
            _, current_id = heapq.heappop(open_heap)

            if current_id == destination_id:
                return self._reconstruct_path(came_from, destination_id)

            if current_id in closed:
                continue
            closed.add(current_id)

            for edge in self._adjacency.get(current_id, []):
                if edge.is_blocked:
                    continue

                neighbour_id = edge.destination.node_id
                if neighbour_id in closed:
                    continue

                tentative_g = g_score[current_id] + edge.weight

                if tentative_g < g_score.get(neighbour_id, math.inf):
                    g_score[neighbour_id] = tentative_g
                    came_from[neighbour_id] = current_id
                    h = self._get_node(neighbour_id).distance_to(destination)
                    heapq.heappush(open_heap, (tentative_g + h, neighbour_id))

        return None

    def get_waypoint(self, node_id: str) -> Waypoint:
        return self._get_node(node_id)

    def has_waypoint(self, node_id: str) -> bool:
        """Return True if the node_id is registered."""
        return node_id in self._nodes

    def get_all_waypoints(self) -> list[Waypoint]:
        return list(self._nodes.values())

    def get_edges(self, node_id: str) -> List[Edge]:
        """Return all edges originating from *node_id*."""
        return self._adjacency.get(node_id, [])

    def get_neighbours(self, node_id: str) -> list[Waypoint]:
        """Return all reachable (unblocked) neighbours of a waypoint."""
        return [
            e.destination
            for e in self._adjacency.get(node_id, [])
            if not e.is_blocked
        ]

    def node_count(self) -> int:
        return len(self._nodes)

    def edge_count(self) -> int:
        return sum(len(edges) for edges in self._adjacency.values())

    def _get_node(self, node_id: str) -> Waypoint:
        try:
            return self._nodes[node_id]
        except KeyError:
            raise KeyError(f"Waypoint '{node_id}' is not registered in the graph.")

    def _reconstruct_path(
        self, came_from: dict[str, str], current_id: str
    ) -> list[Waypoint]:
        path = []
        while current_id in came_from:
            path.append(self._get_node(current_id))
            current_id = came_from[current_id]
        path.append(self._get_node(current_id))
        path.reverse()
        return path
