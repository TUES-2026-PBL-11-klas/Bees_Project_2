from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


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
    coordinates: List[float]
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


class RouteHistoryFilters(BaseModel):
    company_id: Optional[str] = None
    vessel_id: Optional[str] = None
    optimization_mode: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    is_valid: Optional[bool] = None


class RouteHistoryItem(BaseModel):
    id: str
    request_id: str
    company_id: str
    vessel_id: str
    optimization_mode: str
    total_distance_nm: Optional[float] = None
    estimated_duration_h: Optional[float] = None
    estimated_fuel_tons: Optional[float] = None
    waypoint_count: int = 0
    is_valid: bool = True
    calculated_at: Optional[datetime] = None


class RouteHistoryResponse(BaseModel):
    filters: RouteHistoryFilters
    total: int
    limit: int
    offset: int
    items: List[RouteHistoryItem]


class ModeAnalytics(BaseModel):
    count: int
    total_distance_nm: float = 0.0
    total_duration_h: float = 0.0
    total_fuel_tons: float = 0.0
    avg_distance_nm: float = 0.0
    avg_duration_h: float = 0.0
    avg_fuel_tons: float = 0.0


class RouteAnalyticsTotals(BaseModel):
    distance_nm: float = 0.0
    duration_h: float = 0.0
    fuel_tons: float = 0.0


class RouteAnalyticsAverages(BaseModel):
    distance_nm: float = 0.0
    duration_h: float = 0.0
    fuel_tons: float = 0.0


class RouteAnalyticsResponse(BaseModel):
    filters: RouteHistoryFilters
    total_routes: int
    valid_routes: int
    invalid_routes: int
    totals: RouteAnalyticsTotals
    averages: RouteAnalyticsAverages
    by_optimization_mode: dict[str, ModeAnalytics] = Field(default_factory=dict)
