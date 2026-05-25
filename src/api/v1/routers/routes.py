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
from src.core.graph_builder import get_graph
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


_LAND_MASK_PATH = Path(__file__).resolve().parents[4] / "ne_50m_land.geojson"




def _resolve_node_id(raw: str) -> str:
    """Resolve a user-supplied port/city name to a graph node_id."""
    graph = get_graph()
    if graph.has_waypoint(raw):
        return raw


    upper = raw.upper().replace(" ", "_")
    if graph.has_waypoint(upper):
        return upper


    port = resolve_port(raw)
    if port and graph.has_waypoint(port.port_id):
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

    vessel_type = vessel.vessel_type if vessel else "default"

    # Cache Lookup
    cached_history = repo.find_cached_route(start_id, end_id, vessel_type, request.optimization_mode)
    if cached_history and cached_history.route_id:
        route_doc = repo.get_by_id(str(cached_history.route_id))
        if route_doc:
            logger.info("Using cached route %s for %s -> %s", route_doc.id, start_id, end_id)
            result = json.loads(route_doc.to_json())
            result["vessel_type_used"] = vessel_type
            result["start_port"] = start_id
            result["end_port"] = end_id
            return result

    if request.optimization_mode == "eco":
        strategy = EcoStrategy()
        strategy_name = "EcoStrategy"
    elif request.optimization_mode == "fastest":
        strategy = FastestStrategy()
        strategy_name = "FastestStrategy"
    else:
        raise HTTPException(status_code=400, detail="Invalid optimization mode. Use 'fastest' or 'eco'.")


    try:
        path = strategy.calculate_route(get_graph(), start_id, end_id, vessel=vessel)
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

        # Save to Route History
        repo.save_history({
            "origin": start_id,
            "destination": end_id,
            "vessel_type": vessel_type,
            "optimization_mode": request.optimization_mode,
            "strategy": strategy_name,
            "calculated_time_h": stats["estimated_duration_h"],
            "predicted_fuel_tons": stats["estimated_fuel_tons"],
            "route_id": created_route.id
        })

        result = json.loads(created_route.to_json())
    except Exception as exc:
        logger.warning("Could not persist route to DB: %s", exc)
        result = {"_id": None, "waypoints": waypoints}


    result["total_distance_nm"] = stats["total_distance_nm"]
    result["estimated_duration_h"] = stats["estimated_duration_h"]
    result["estimated_fuel_tons"] = stats["estimated_fuel_tons"]
    result["vessel_type_used"] = vessel_type
    result["start_port"] = start_id
    result["end_port"] = end_id

    return result


@router.get("/history/analytics")
def get_route_history_analytics(
    vessel_type: Optional[str] = None,
    optimization_mode: Optional[str] = None,
    strategy: Optional[str] = None
):
    """
    Get route history analytics, including average fuel and time deviations.
    """
    filters = {}
    if vessel_type:
        filters["vessel_type"] = vessel_type
    if optimization_mode:
        filters["optimization_mode"] = optimization_mode
    if strategy:
        filters["strategy"] = strategy

    history = repo.get_history_analytics(**filters)

    if not history:
        return {"message": "No history data available for the given filters."}

    total_routes = len(history)

    # Calculate average fuel and time
    sum_predicted_fuel = sum(h.predicted_fuel_tons for h in history)
    sum_actual_fuel = sum(h.actual_fuel_tons for h in history if h.actual_fuel_tons is not None)
    count_actual_fuel = sum(1 for h in history if h.actual_fuel_tons is not None)

    sum_predicted_time = sum(h.calculated_time_h for h in history)
    sum_actual_time = sum(h.actual_time_h for h in history if h.actual_time_h is not None)
    count_actual_time = sum(1 for h in history if h.actual_time_h is not None)

    # Strategy efficiency
    strategy_stats = {}
    for h in history:
        s = h.strategy
        if s not in strategy_stats:
            strategy_stats[s] = {"count": 0, "predicted_fuel": 0, "actual_fuel": 0, "actual_count": 0}
        strategy_stats[s]["count"] += 1
        strategy_stats[s]["predicted_fuel"] += h.predicted_fuel_tons
        if h.actual_fuel_tons is not None:
            strategy_stats[s]["actual_fuel"] += h.actual_fuel_tons
            strategy_stats[s]["actual_count"] += 1

    efficiency = {}
    for s, data in strategy_stats.items():
        avg_pred = data["predicted_fuel"] / data["count"]
        avg_act = data["actual_fuel"] / data["actual_count"] if data["actual_count"] > 0 else None
        efficiency[s] = {
            "total_routes": data["count"],
            "avg_predicted_fuel": round(avg_pred, 2),
            "avg_actual_fuel": round(avg_act, 2) if avg_act is not None else None,
            "deviation_pct": round(((avg_act - avg_pred) / avg_pred * 100), 2) if avg_act is not None else None
        }

    return {
        "summary": {
            "total_routes": total_routes,
            "avg_predicted_fuel": round(sum_predicted_fuel / total_routes, 2),
            "avg_actual_fuel": round(sum_actual_fuel / count_actual_fuel, 2) if count_actual_fuel > 0 else None,
            "avg_predicted_time": round(sum_predicted_time / total_routes, 2),
            "avg_actual_time": round(sum_actual_time / count_actual_time, 2) if count_actual_time > 0 else None,
        },
        "strategy_efficiency": efficiency
    }

@router.patch("/history/{history_id}/actuals")
def update_route_actuals(history_id: str, actual_time: float, actual_fuel: float):
    """
    Update a route history record with actual reported values after voyage completion.
    """
    try:
        updated = repo.update_actuals(history_id, actual_time, actual_fuel)
        if not updated:
            raise HTTPException(status_code=404, detail="Route history record not found")
        return {"status": "updated", "history_id": updated.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
            path = strategy.calculate_route(get_graph(), start_id, end_id, vessel=vessel)
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
