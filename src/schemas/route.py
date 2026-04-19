from pydantic import BaseModel
from typing import Optional, List


class RouteCalculationSchema(BaseModel):
    """
    Request schema for route calculation.

    Port resolution:
        start_node_id / end_node_id accept either a graph node ID (e.g. "VARNA")
        or a city/port name (e.g. "Varna", "barcelona").  The backend will
        attempt case-insensitive matching against the port catalogue.

    Vessel:
        If vessel_id is provided AND points to a real vessel in the DB, the
        system will pull its specs (draft, speed, fuel rate, type) and factor
        them into the route calculation.

        Alternatively, vessel_type can be passed directly for anonymous
        calculations without a stored vessel.
    """
    company_id: str = ""
    vessel_id: str = ""
    vessel_type: Optional[str] = None
    start_node_id: str
    end_node_id: str
    optimization_mode: str = "fastest"


class WaypointOut(BaseModel):
    sequence: int
    coordinates: List[float]       # [lon, lat]
    point_type: str = "waypoint"
    name: Optional[str] = None


class RouteResultSchema(BaseModel):
    """Response schema returned by the calculate endpoint."""
    optimization_mode: str
    waypoints: List[WaypointOut]
    total_distance_nm: Optional[float] = None
    estimated_duration_h: Optional[float] = None
    estimated_fuel_tons: Optional[float] = None
    vessel_type_used: Optional[str] = None
    start_port: Optional[str] = None
    end_port: Optional[str] = None
