import json
import logging
from typing import Optional
from pathlib import Path

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from concurrent.futures import ThreadPoolExecutor
from fastapi.responses import FileResponse

from src.schemas.route import RouteCalculationSchema
from src.core.routing.strategy import (
    FastestStrategy,
    EcoStrategy,
    VesselConstraints,
    DEFAULT_SPEED_KNOTS,
    DEFAULT_FUEL_RATE,
    METRES_PER_NM,
)
from src.infrastructure.repositories.route_repository import RouteRepository
from src.core.graph_builder import build_navigation_graph
from src.core.ports import resolve_port, list_all_ports

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/routes", tags=["routes"])
repo = RouteRepository()



_FUEL_MULTIPLIERS: dict[str, float] = {
    "tanker": 1.20,
    "container_ship": 1.10,
    "bulk_carrier": 1.15,
    "passenger_ship": 1.18,
    "ferry": 1.12,
    "ro_ro_ship": 1.14,
    "lng_carrier": 1.25,
    "lpg_carrier": 1.22,
    "chemical_tanker": 1.23,
    "car_carrier": 1.14,
    "general_cargo": 1.13,
    "offshore_support": 1.30,
    "research_vessel": 1.20,
    "icebreaker": 1.40,
    "tugboat": 1.35,
    "fishing_vessel": 1.16,
    "cruise_ship": 1.17,
    "yacht": 1.08,
    "patrol_boat": 1.28,
    "dredger": 1.32,
}


_GRAPH = build_navigation_graph()
_LAND_MASK_PATH = Path(__file__).resolve().parents[4] / "ne_50m_land.geojson"




def _resolve_node_id(raw: str) -> str:
    """Resolve a user-supplied port/city name to a graph node_id."""

    if _GRAPH.has_waypoint(raw):
        return raw


    upper = raw.upper().replace(" ", "_")
    if _GRAPH.has_waypoint(upper):
        return upper


    port = resolve_port(raw)
    if port and _GRAPH.has_waypoint(port.port_id):
        return port.port_id

    raise HTTPException(
        status_code=404,
        detail=f"Port '{raw}' not found.  Use /api/v1/routes/ports to list available ports.",
    )


def _build_vessel_constraints(
    vessel_id: str = "",
    vessel_type: Optional[str] = None,
) -> Optional[VesselConstraints]:
    """
    Build VesselConstraints from either a DB vessel or a bare vessel_type.

    Returns None if no vessel info is available (route will use defaults).
    """

    if vessel_id and ObjectId.is_valid(vessel_id):
        try:
            from src.infrastructure.repositories.vessel_repository import VesselRepository
            vessel_repo = VesselRepository()
            vessel_doc = vessel_repo.get_by_id(vessel_id)
            if vessel_doc:
                specs = vessel_doc.specs
                vt = vessel_doc.vessel_type
                return VesselConstraints(
                    vessel_type=vt,
                    max_draft_m=float(specs.max_draft_m) if specs and specs.max_draft_m else None,
                    max_speed_knots=float(specs.max_speed_knots) if specs and specs.max_speed_knots else None,
                    fuel_consumption_rate=float(vessel_doc.fuel_consumption_rate) if vessel_doc.fuel_consumption_rate else None,
                    fuel_multiplier=_FUEL_MULTIPLIERS.get(vt, 1.0) if vt else 1.0,
                    length_m=float(specs.length_m) if specs and specs.length_m else None,
                    beam_m=float(specs.beam_m) if specs and specs.beam_m else None,
                )
        except Exception as exc:
            logger.debug("Could not load vessel %s from DB: %s", vessel_id, exc)


    if vessel_type:
        return VesselConstraints(
            vessel_type=vessel_type,
            fuel_multiplier=_FUEL_MULTIPLIERS.get(vessel_type, 1.0),
        )

    return None


def _compute_route_stats(
    waypoints,
    vessel: Optional[VesselConstraints] = None,
) -> dict:
    """
    Compute total distance (NM), duration (hours), and fuel (tonnes)
    from an ordered list of graph Waypoint objects.
    """
    total_metres = 0.0
    for i in range(len(waypoints) - 1):
        total_metres += waypoints[i].distance_to(waypoints[i + 1])

    total_nm = total_metres / METRES_PER_NM

    speed = DEFAULT_SPEED_KNOTS
    fuel_rate = DEFAULT_FUEL_RATE
    fuel_mult = 1.0

    if vessel:
        if vessel.max_speed_knots:
            speed = vessel.max_speed_knots
        if vessel.fuel_consumption_rate:
            fuel_rate = vessel.fuel_consumption_rate
        fuel_mult = vessel.fuel_multiplier

    duration_h = total_nm / speed if speed > 0 else 0.0
    fuel_tons = fuel_rate * total_nm * fuel_mult

    return {
        "total_distance_nm": round(total_nm, 2),
        "estimated_duration_h": round(duration_h, 2),
        "estimated_fuel_tons": round(fuel_tons, 2),
    }




@router.get("/ports")
def get_available_ports():
    """Return all ports that can be used as origin/destination."""
    ports = list_all_ports()
    return [
        {"port_id": p.port_id, "name": p.name, "lat": p.latitude, "lon": p.longitude}
        for p in ports
    ]


@router.get("/landmask")
def get_landmask_geojson():
    if not _LAND_MASK_PATH.exists():
        raise HTTPException(status_code=404, detail="Land mask file is missing")
    return FileResponse(
        _LAND_MASK_PATH,
        media_type="application/geo+json",
        filename="ne_50m_land.geojson",
    )


@router.post("/calculate")
def calculate_route(request: RouteCalculationSchema):

    start_id = _resolve_node_id(request.start_node_id)
    end_id = _resolve_node_id(request.end_node_id)


    vessel = _build_vessel_constraints(request.vessel_id, request.vessel_type)


    if request.optimization_mode == "eco":
        strategy = EcoStrategy()
    elif request.optimization_mode == "fastest":
        strategy = FastestStrategy()
    else:
        raise HTTPException(status_code=400, detail="Invalid optimization mode. Use 'fastest' or 'eco'.")


    try:
        path = strategy.calculate_route(_GRAPH, start_id, end_id, vessel=vessel)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not path:
        raise HTTPException(status_code=404, detail=f"No route found from {start_id} to {end_id}.")


    waypoints = []
    for idx, wp in enumerate(path):
        point_type = "waypoint"
        if idx == 0:
            point_type = "port"
        elif idx == len(path) - 1:
            point_type = "port"
        elif not wp.node_id.startswith("WP_"):
            point_type = "port"

        waypoints.append({
            "sequence": idx,
            "coordinates": [wp.longitude, wp.latitude],
            "point_type": point_type,
            "name": wp.name if not wp.node_id.startswith("WP_") else None,
        })


    stats = _compute_route_stats(path, vessel)


    route_data = {
        "request_id": ObjectId(),
        "company_id": ObjectId(request.company_id) if ObjectId.is_valid(request.company_id) else ObjectId(),
        "vessel_id": ObjectId(request.vessel_id) if ObjectId.is_valid(request.vessel_id) else ObjectId(),
        "optimization_mode": request.optimization_mode,
        "total_distance_nm": stats["total_distance_nm"],
        "estimated_duration_h": stats["estimated_duration_h"],
        "estimated_fuel_tons": stats["estimated_fuel_tons"],
        "waypoints": waypoints,
    }

    try:
        created_route = repo.create(route_data)
        result = json.loads(created_route.to_json())
    except Exception as exc:
        logger.warning("Could not persist route to DB: %s", exc)
        result = {"_id": None, "waypoints": waypoints}


    result["total_distance_nm"] = stats["total_distance_nm"]
    result["estimated_duration_h"] = stats["estimated_duration_h"]
    result["estimated_fuel_tons"] = stats["estimated_fuel_tons"]
    result["vessel_type_used"] = vessel.vessel_type if vessel else None
    result["start_port"] = start_id
    result["end_port"] = end_id

    return result


@router.get("/{route_id}")
def get_route_by_id(route_id: str):
    route = repo.get_by_id(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    return json.loads(route.to_json())


executor = ThreadPoolExecutor(max_workers=5)


@router.post("/calculate-batch")
def calculate_routes_batch(requests: list[RouteCalculationSchema]):

    def calculate_single(request: RouteCalculationSchema):
        try:
            start_id = _resolve_node_id(request.start_node_id)
            end_id = _resolve_node_id(request.end_node_id)
        except HTTPException as e:
            return {"error": e.detail}

        vessel = _build_vessel_constraints(request.vessel_id, request.vessel_type)

        if request.optimization_mode == "eco":
            strategy = EcoStrategy()
        elif request.optimization_mode == "fastest":
            strategy = FastestStrategy()
        else:
            return {"error": "Invalid optimization mode"}

        try:
            path = strategy.calculate_route(_GRAPH, start_id, end_id, vessel=vessel)
        except KeyError as e:
            return {"error": str(e)}

        if not path:
            return {"error": "No route found"}

        waypoints = []
        for idx, wp in enumerate(path):
            waypoints.append({
                "sequence": idx,
                "coordinates": [wp.longitude, wp.latitude],
                "point_type": "waypoint",
            })

        stats = _compute_route_stats(path, vessel)

        return {
            "optimization_mode": request.optimization_mode,
            "waypoints": waypoints,
            **stats,
            "vessel_type_used": vessel.vessel_type if vessel else None,
        }

    results = list(executor.map(calculate_single, requests))
    return results
