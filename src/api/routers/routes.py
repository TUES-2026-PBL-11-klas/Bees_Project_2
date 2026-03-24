from fastapi import APIRouter, HTTPException
from bson import ObjectId
import json

from src.schemas.route import RouteCalculationSchema
from src.core.routing.strategy import FastestStrategy, EcoStrategy
from src.infrastructure.repositories.route_repository import RouteRepository
from src.core.graph import NavigationGraph, Waypoint

router = APIRouter(prefix="/api/v1/routes", tags=["routes"])
repo = RouteRepository()

def get_initialized_graph() -> NavigationGraph:
    g = NavigationGraph()
    g.add_waypoint(Waypoint("MALTA", 35.9042, 14.5189))
    g.add_waypoint(Waypoint("PIRAEUS", 37.9475, 23.6425))
    g.add_waypoint(Waypoint("TRIPOLI", 32.8752, 13.1875))
    g.add_edge("MALTA", "PIRAEUS")
    g.add_edge("MALTA", "TRIPOLI")
    g.add_edge("TRIPOLI", "PIRAEUS")
    return g

@router.post("/calculate")
def calculate_route(request: RouteCalculationSchema):
    graph = get_initialized_graph()

    if request.optimization_mode == "fastest":
        strategy = FastestStrategy()
    elif request.optimization_mode == "eco":
        strategy = EcoStrategy()
    else:
        raise HTTPException(status_code=400, detail="Invalid optimization mode")

    try:
        path = strategy.calculate_route(graph, request.start_node_id, request.end_node_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not path:
        raise HTTPException(status_code=404, detail="No route found")

    waypoints = []
    for idx, wp in enumerate(path):
        waypoints.append({
            "sequence": idx,
            "coordinates": [wp.longitude, wp.latitude],
            "point_type": "waypoint"
        })

    route_data = {
        "request_id": ObjectId(),
        "company_id": ObjectId(request.company_id) if ObjectId.is_valid(request.company_id) else ObjectId(),
        "vessel_id": ObjectId(request.vessel_id) if ObjectId.is_valid(request.vessel_id) else ObjectId(),
        "optimization_mode": request.optimization_mode,
        "waypoints": waypoints
    }

    created_route = repo.create(route_data)
    return json.loads(created_route.to_json())

@router.get("/{route_id}")
def get_route_by_id(route_id: str):
    route = repo.get_by_id(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    return json.loads(route.to_json())
