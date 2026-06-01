import json
import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from src.core.services.ai.ai_service import AIService
from src.core.services.ai.ws_manager import WebSocketManager
from src.schemas.ai import (
    RerouteRequest,
    RerouteResponse,
    RecommendationOut,
    RecommendationUpdate,
    AnomalyOut,
    ETAPredictionOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])

_ai_service = None
ws_manager = WebSocketManager()


def _get_ai_service() -> AIService:
    """Lazy-initialize the AIService singleton."""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service


# ── POST /api/v1/ai/reroute ──────────────────────────────────────────

@router.post("/reroute", response_model=RerouteResponse)
def request_reroute(request: RerouteRequest):
    """
    Request an AI-powered reroute for a vessel.

    Evaluates the vessel's current route against alternatives and returns
    the best option with comparison statistics (distance, ETA, fuel deltas).
    """
    service = _get_ai_service()

    try:
        result = service.handle_reroute_request(
            vessel_id=request.vessel_id,
            reason=request.reason,
            current_position=request.current_position,
            force=request.force,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Reroute error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Reroute evaluation failed: {str(exc)}")

    return result


# ── GET /api/v1/ai/recommendations ───────────────────────────────────

@router.get("/recommendations", response_model=List[RecommendationOut])
def get_recommendations(
    vessel_id: Optional[str] = Query(default=None),
    company_id: Optional[str] = Query(default=None),
    types: Optional[str] = Query(default=None, description="Comma-separated recommendation types"),
    priority: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default="active"),
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    Get AI recommendations, optionally filtered by vessel, company, type,
    priority, and status.  Results are sorted by priority and confidence.
    """
    service = _get_ai_service()

    type_list = None
    if types:
        type_list = [t.strip() for t in types.split(",")]

    try:
        results = service.get_recommendations(
            vessel_id=vessel_id,
            company_id=company_id,
            types=type_list,
            priority=priority,
            status=status,
            limit=limit,
        )
    except Exception as exc:
        logger.error("Recommendations error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))

    return results


# ── GET /api/v1/ai/anomalies ─────────────────────────────────────────

@router.get("/anomalies", response_model=List[AnomalyOut])
def get_anomalies(
    vessel_id: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
):
    """List detected anomalies, filterable by vessel and severity."""
    service = _get_ai_service()

    try:
        results = service.get_anomalies(vessel_id=vessel_id, severity=severity)
    except Exception as exc:
        logger.error("Anomalies error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))

    return results


# ── POST /api/v1/ai/anomalies/scan/{vessel_id} ──────────────────────

@router.post("/anomalies/scan/{vessel_id}", response_model=List[AnomalyOut])
def scan_anomalies(vessel_id: str):
    """Manually trigger an anomaly scan for a specific vessel."""
    service = _get_ai_service()

    try:
        results = service.run_anomaly_scan(vessel_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Anomaly scan error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))

    return results


# ── GET /api/v1/ai/eta/{vessel_id}/{route_id} ────────────────────────

@router.get("/eta/{vessel_id}/{route_id}", response_model=ETAPredictionOut)
def get_eta_prediction(vessel_id: str, route_id: str):
    """Get predictive ETA for a specific vessel on a route."""
    service = _get_ai_service()

    try:
        result = service.predict_eta(vessel_id, route_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("ETA prediction error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))

    return result


# ── PATCH /api/v1/ai/recommendations/{rec_id} ────────────────────────

@router.patch("/recommendations/{rec_id}", response_model=RecommendationOut)
def update_recommendation(rec_id: str, body: RecommendationUpdate):
    """Update a recommendation's status (e.g., accept or dismiss)."""
    service = _get_ai_service()

    try:
        result = service.update_recommendation(rec_id, body.model_dump(exclude_unset=True))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Update recommendation error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))

    return result


# ── WebSocket /ws/ai/notifications ────────────────────────────────────

async def ws_notifications(websocket: WebSocket):
    """
    WebSocket endpoint for real-time AI event notifications.

    Clients can optionally subscribe to a specific vessel or company by
    passing query parameters: ?vessel_id=xxx&company_id=yyy
    """
    vessel_id = websocket.query_params.get("vessel_id")
    company_id = websocket.query_params.get("company_id")

    await ws_manager.connect(websocket, vessel_id=vessel_id, company_id=company_id)

    try:
        while True:
            # Keep the connection alive; client can send pings or commands
            data = await websocket.receive_text()
            # Echo back as acknowledgement
            await websocket.send_json({
                "event_type": "ack",
                "payload": {"message": data},
            })
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
        logger.info("WebSocket client disconnected (vessel=%s)", vessel_id)
    except Exception as exc:
        logger.error("WebSocket error: %s", exc)
        await ws_manager.disconnect(websocket)
