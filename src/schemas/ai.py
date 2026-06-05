from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class RerouteRequest(BaseModel):
    """POST /ai/reroute request body."""
    vessel_id: str
    reason: Optional[str] = None
    force: bool = False
    current_position: Optional[List[float]] = None


class GenerateRecommendationsRequest(BaseModel):
    """POST /ai/recommendations/generate request body."""
    vessel_id: Optional[str] = None
    company_id: Optional[str] = None


class ApplyRerouteRequest(BaseModel):
    """POST /ai/reroute/apply request body."""
    route_id: str
    new_waypoints: List[Dict[str, Any]]
    new_stats: Optional[Dict[str, Any]] = None


class ReroutePreviewRequest(BaseModel):
    """
    POST /ai/reroute/preview request body.

    Stateless reroute evaluation: re-runs the routing strategy with
    current + weather awareness against the same origin/destination as
    the user's *active* route on the map, then compares to the supplied
    stats.  Does *not* need a DB-backed vessel or persisted route.
    """
    start_node_id: str
    end_node_id: str
    optimization_mode: str = "fastest"
    vessel_id: Optional[str] = None
    vessel_type: Optional[str] = None
    current_position: Optional[List[float]] = None
    current_stats: Optional[Dict[str, float]] = None
    reason: Optional[str] = None


class RerouteResponse(BaseModel):
    """Response returned after a reroute evaluation."""
    reroute_id: str
    status: str
    reason: str
    original_route: dict
    new_route: Optional[dict] = None
    distance_delta_nm: Optional[float] = None
    eta_delta_h: Optional[float] = None
    fuel_delta_tons: Optional[float] = None
    recommendation: str


class RecommendationQuery(BaseModel):
    """GET /ai/recommendations query parameters."""
    vessel_id: Optional[str] = None
    company_id: Optional[str] = None
    types: Optional[List[str]] = None
    priority: Optional[str] = None
    status: Optional[str] = "active"
    limit: int = 20


class RecommendationOut(BaseModel):
    """Serialised AI recommendation returned to the client."""
    id: str
    vessel_id: Optional[str] = None
    company_id: Optional[str] = None
    recommendation_type: str
    title: str
    description: str
    data: Dict[str, Any] = {}
    confidence: float
    priority: str
    status: str
    expires_at: Optional[str] = None
    created_at: str


class RecommendationUpdate(BaseModel):
    """PATCH body for updating a recommendation's status."""
    status: Optional[str] = None


class AnomalyOut(BaseModel):
    """Serialised anomaly record returned to the client."""
    id: str
    vessel_id: str
    anomaly_type: str
    severity: str
    details: Dict[str, Any] = {}
    detected_at: str
    resolved: bool


class ETAPredictionOut(BaseModel):
    """Serialised ETA prediction returned to the client."""
    vessel_id: str
    route_id: str
    original_eta_h: float
    predicted_eta_h: float
    confidence: float
    factors: Dict[str, Any] = {}
    created_at: str


class WebSocketMessage(BaseModel):
    """Envelope for real-time messages pushed over WebSocket."""
    event_type: str
    payload: Dict[str, Any] = {}
    timestamp: str
