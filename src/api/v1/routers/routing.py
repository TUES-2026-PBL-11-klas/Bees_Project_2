from fastapi import APIRouter
from concurrent.futures import ThreadPoolExecutor

from src.core.graph import NavigationGraph, Waypoint
from src.core.routing.strategy import EcoStrategy, FastestStrategy
from src.schemas.route import RouteCalculationSchema

router = APIRouter(prefix="/api/v1/routing", tags=["routing"])


def get_initialized_graph() -> NavigationGraph:
    g = NavigationGraph()
    g.add_waypoint(Waypoint("MALTA", 35.9042, 14.5189))
    g.add_waypoint(Waypoint("PIRAEUS", 37.9475, 23.6425))
    g.add_waypoint(Waypoint("TRIPOLI", 32.8752, 13.1875))
    g.add_edge("MALTA", "PIRAEUS")
    g.add_edge("MALTA", "TRIPOLI")
    g.add_edge("TRIPOLI", "PIRAEUS")
    return g


executor = ThreadPoolExecutor(max_workers=5)


@router.post("/calculate-parallel")
def calculate_routes_parallel(requests: list[RouteCalculationSchema]):
    graph = get_initialized_graph()

    def calculate_single(request: RouteCalculationSchema):
        if request.optimization_mode == "fastest":
            strategy = FastestStrategy()
        elif request.optimization_mode == "eco":
            strategy = EcoStrategy()
        else:
            return {"error": "Invalid optimization mode"}

        try:
            path = strategy.calculate_route(graph, request.start_node_id, request.end_node_id)
        except KeyError as error:
            return {"error": str(error)}

        if not path:
            return {"error": "No route found"}

        return {
            "optimization_mode": request.optimization_mode,
            "waypoints": [
                {
                    "sequence": idx,
                    "coordinates": [wp.longitude, wp.latitude],
                    "point_type": "waypoint",
                }
                for idx, wp in enumerate(path)
            ],
        }

    return list(executor.map(calculate_single, requests))
