"""
Port scheduling router (GitHub issue #82).

Endpoints
---------
GET    /api/v1/ports
POST   /api/v1/ports
DELETE /api/v1/ports/{port_id}

GET    /api/v1/ports/{port_id}/schedule
PUT    /api/v1/ports/{port_id}/schedule

GET    /api/v1/dock-reservations
POST   /api/v1/dock-reservations
GET    /api/v1/dock-reservations/{reservation_id}
DELETE /api/v1/dock-reservations/{reservation_id}   (sets status=cancelled)
"""

from __future__ import annotations

import json
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query

from src.infrastructure.repositories.port_scheduling_repository import (
    DockReservationRepository,
    PortRepository,
    PortScheduleRepository,
)
from src.models.port_scheduling import DockReservation
from src.schemas.port_scheduling import (
    DockReservationCreateSchema,
    PortCreateSchema,
    PortScheduleSchema,
)

router = APIRouter(prefix="/api/v1", tags=["port-scheduling"])
_ports = PortRepository()
_schedules = PortScheduleRepository()
_reservations = DockReservationRepository()


def _to_dict(doc) -> dict:
    return json.loads(doc.to_json())


# ── Ports CRUD ──────────────────────────────────────────────────────


@router.get("/ports")
def list_ports(limit: int = Query(default=500, ge=1, le=2000)):
    return [_to_dict(p) for p in _ports.list_all(limit=limit)]


@router.post("/ports", status_code=201)
def create_port(payload: PortCreateSchema):
    existing = _ports.get_by_port_id(payload.port_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="port_id already exists")
    created = _ports.create(payload.model_dump())
    return _to_dict(created)


@router.get("/ports/{port_id}")
def get_port(port_id: str):
    port = _ports.get_by_port_id(port_id)
    if port is None:
        raise HTTPException(status_code=404, detail="Port not found")
    return _to_dict(port)


@router.delete("/ports/{port_id}", status_code=204)
def delete_port(port_id: str):
    if not _ports.delete(port_id):
        raise HTTPException(status_code=404, detail="Port not found")
    return None


# ── Port schedule ───────────────────────────────────────────────────


@router.get("/ports/{port_id}/schedule")
def get_port_schedule(port_id: str):
    schedule = _schedules.get(port_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return _to_dict(schedule)


@router.put("/ports/{port_id}/schedule")
def upsert_port_schedule(port_id: str, payload: PortScheduleSchema):
    data = payload.model_dump()
    # convert pydantic BlackoutWindow models back to plain dicts
    data["blackouts"] = [b for b in data.get("blackouts", [])]
    schedule = _schedules.upsert(port_id, data)
    return _to_dict(schedule)


# ── Dock reservations ───────────────────────────────────────────────


@router.get("/dock-reservations")
def list_reservations(
    port_id: str = Query(...),
    berth_number: Optional[int] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
):
    items = _reservations.list_for_port(port_id, berth_number=berth_number, limit=limit)
    return [_to_dict(r) for r in items]


@router.post("/dock-reservations", status_code=201)
def create_reservation(payload: DockReservationCreateSchema):
    if not ObjectId.is_valid(payload.vessel_id):
        raise HTTPException(status_code=400, detail="Invalid vessel_id")
    if payload.company_id and not ObjectId.is_valid(payload.company_id):
        raise HTTPException(status_code=400, detail="Invalid company_id")

    candidate = DockReservation(
        port_id=payload.port_id,
        berth_number=payload.berth_number,
        vessel_id=ObjectId(payload.vessel_id),
        company_id=ObjectId(payload.company_id) if payload.company_id else None,
        start_at=payload.start_at,
        end_at=payload.end_at,
        purpose=payload.purpose,
        notes=payload.notes,
    )

    conflicts = _reservations.find_conflicts(candidate)
    if conflicts:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Reservation conflicts with existing slot(s)",
                "conflicts": [_to_dict(c) for c in conflicts],
            },
        )

    created = _reservations.create(candidate.to_mongo().to_dict())
    return _to_dict(created)


@router.get("/dock-reservations/{reservation_id}")
def get_reservation(reservation_id: str):
    reservation = _reservations.get_by_id(reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return _to_dict(reservation)


@router.delete("/dock-reservations/{reservation_id}")
def cancel_reservation(reservation_id: str):
    cancelled = _reservations.cancel(reservation_id)
    if cancelled is None:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return _to_dict(cancelled)


# ── Port congestion forecasting ─────────────────────────────────────


from datetime import datetime  # noqa: E402

from src.core.services.port_congestion_service import (  # noqa: E402
    DEFAULT_BUCKET_MINUTES,
    DEFAULT_CONFIRMED_WEIGHT,
    DEFAULT_HORIZON_HOURS,
    PortCongestionService,
)


@router.get("/ports/{port_id}/congestion")
def get_port_congestion(
    port_id: str,
    start_at: Optional[datetime] = Query(
        default=None,
        description="UTC timestamp to start the forecast at (defaults to now).",
    ),
    horizon_hours: int = Query(default=DEFAULT_HORIZON_HOURS, ge=1, le=24 * 14),
    bucket_minutes: int = Query(default=DEFAULT_BUCKET_MINUTES, ge=15, le=720),
    confirmed_weight: float = Query(default=DEFAULT_CONFIRMED_WEIGHT, ge=0.0, le=1.0),
    history_lookback_days: int = Query(default=90, ge=1, le=365),
):
    """
    Forecast berth occupancy at a port for the next ``horizon_hours``,
    blending confirmed reservations and a historical baseline.

    Returns per-bucket occupancy, available berth estimates and a
    congestion score in [0, 1] (higher = busier).
    """
    service = PortCongestionService(
        history_lookback_days=history_lookback_days,
        confirmed_weight=confirmed_weight,
    )
    try:
        forecast = service.forecast(
            port_id,
            start_at=start_at,
            horizon_hours=horizon_hours,
            bucket_minutes=bucket_minutes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return forecast.to_dict()
