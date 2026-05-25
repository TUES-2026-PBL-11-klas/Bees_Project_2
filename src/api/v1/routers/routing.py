import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from concurrent.futures import ThreadPoolExecutor

from src.schemas.route import RouteCalculationSchema
from src.core.routing.strategy import (
    EcoStrategy,
    FastestStrategy,
    VesselConstraints,
    DEFAULT_SPEED_KNOTS,
    DEFAULT_FUEL_RATE,
    METRES_PER_NM,
)
from src.core.graph_builder import get_graph
from src.core.ports import resolve_port
from src.infrastructure.repositories.route_repository import RouteRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/routing", tags=["routing"])


_GRAPH = None
repo = RouteRepository()


_FUEL_MULTIPLIERS: dict[str, float] = {
    "tanker": 1.20, "container_ship": 1.10, "bulk_carrier": 1.15,
    "passenger_ship": 1.18, "ferry": 1.12, "ro_ro_ship": 1.14,
    "lng_carrier": 1.25, "lpg_carrier": 1.22, "chemical_tanker": 1.23,
    "car_carrier": 1.14, "general_cargo": 1.13, "offshore_support": 1.30,
    "research_vessel": 1.20, "icebreaker": 1.40, "tugboat": 1.35,
    "fishing_vessel": 1.16, "cruise_ship": 1.17, "yacht": 1.08,
    "patrol_boat": 1.28, "dredger": 1.32,
}

executor = ThreadPoolExecutor(max_workers=5)


def _resolve_node_id(raw: str) -> str:
    graph = get_graph()
    if graph.has_waypoint(raw):
        return raw
    upper = raw.upper().replace(" ", "_")
    if graph.has_waypoint(upper):
        return upper
    port = resolve_port(raw)
    if port and graph.has_waypoint(port.port_id):
        return port.port_id
    raise HTTPException(status_code=404, detail=f"Port '{raw}' not found.")


def _build_vessel_constraints(
    vessel_id: str = "",
    vessel_type: Optional[str] = None,
) -> Optional[VesselConstraints]:
    from bson import ObjectId
    if vessel_id and ObjectId.is_valid(vessel_id):
        try:
            from src.infrastructure.repositories.vessel_repository import VesselRepository
            vessel_doc = VesselRepository().get_by_id(vessel_id)
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
            logger.debug("Could not load vessel %s: %s", vessel_id, exc)

    if vessel_type:
        return VesselConstraints(
            vessel_type=vessel_type,
            fuel_multiplier=_FUEL_MULTIPLIERS.get(vessel_type, 1.0),
        )

    return None


def _compute_route_stats(waypoints, vessel=None):
    total_metres = sum(
        waypoints[i].distance_to(waypoints[i + 1])
        for i in range(len(waypoints) - 1)
    )
    total_nm = total_metres / METRES_PER_NM
    speed = (vessel.max_speed_knots if vessel and vessel.max_speed_knots else DEFAULT_SPEED_KNOTS)
    fuel_rate = (vessel.fuel_consumption_rate if vessel and vessel.fuel_consumption_rate else DEFAULT_FUEL_RATE)
    fuel_mult = vessel.fuel_multiplier if vessel else 1.0
    return {
        "total_distance_nm": round(total_nm, 2),
        "estimated_duration_h": round(total_nm / speed, 2) if speed > 0 else 0.0,
        "estimated_fuel_tons": round(fuel_rate * total_nm * fuel_mult, 2),
    }


@router.post("/calculate-parallel")
def calculate_routes_parallel(requests: list[RouteCalculationSchema]):

    def calculate_single(request: RouteCalculationSchema):
        try:
            start_id = _resolve_node_id(request.start_node_id)
            end_id = _resolve_node_id(request.end_node_id)
        except HTTPException as e:
            return {"error": e.detail}

        vessel = _build_vessel_constraints(request.vessel_id, request.vessel_type)
        vessel_type = vessel.vessel_type if vessel else "default"

        # Cache Lookup
        cached_history = repo.find_cached_route(start_id, end_id, vessel_type, request.optimization_mode)
        if cached_history:
            logger.info("Using cached route for %s -> %s", start_id, end_id)
            # For parallel, we might not have the full Route document if it wasn't saved.
            # But the requirement says we can return the result.
            # We need waypoints and stats.
            # Let's see if we can retrieve the route if it exists.
            if cached_history.route_id:
                route_doc = repo.get_by_id(str(cached_history.route_id))
                if route_doc:
                    stats = {
                        "total_distance_nm": route_doc.total_distance_nm,
                        "estimated_duration_h": route_doc.estimated_duration_h,
                        "estimated_fuel_tons": route_doc.estimated_fuel_tons,
                    }
                    waypoints = [
                        {
                            "sequence": wp.sequence,
                            "coordinates": wp.coordinates,
                            "point_type": wp.point_type,
                        }
                        for wp in route_doc.waypoints
                    ]
                    return {
                        "optimization_mode": request.optimization_mode,
                        "waypoints": waypoints,
                        **stats,
                        "vessel_type_used": vessel_type,
                    }

        if request.optimization_mode == "eco":
            strategy = EcoStrategy()
            strategy_name = "EcoStrategy"
        elif request.optimization_mode == "fastest":
            strategy = FastestStrategy()
            strategy_name = "FastestStrategy"
        else:
            return {"error": "Invalid optimization mode"}

        try:
            path = strategy.calculate_route(_GRAPH, start_id, end_id, vessel=vessel)
        except KeyError as error:
            return {"error": str(error)}

        if not path:
            return {"error": "No route found"}

        stats = _compute_route_stats(path, vessel)

        # Save to Route History
        try:
            repo.save_history({
                "origin": start_id,
                "destination": end_id,
                "vessel_type": vessel_type,
                "optimization_mode": request.optimization_mode,
                "strategy": strategy_name,
                "calculated_time_h": stats["estimated_duration_h"],
                "predicted_fuel_tons": stats["estimated_fuel_tons"],
                "route_id": None # Parallel doesn't create Route doc by default
            })
        except Exception as exc:
            logger.warning("Could not persist route history: %s", exc)

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
            **stats,
            "vessel_type_used": vessel.vessel_type if vessel else None,
        }

    return list(executor.map(calculate_single, requests))
