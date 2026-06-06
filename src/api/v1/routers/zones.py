import json
import logging

from fastapi import APIRouter, HTTPException, Query

from src.core.events.dispatcher import dispatcher
from src.core.events.event import Event
from src.infrastructure.repositories.zone_repositories import ZoneRepository
from src.models.zone import Zone as ZoneModel
from src.schemas.zone import ZoneCreateSchema, ZoneUpdateSchema

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/zones", tags=["zones"])
repo = ZoneRepository()


def _normalize_lon(lon: float) -> float:
    while lon > 180:
        lon -= 360
    while lon < -180:
        lon += 360
    return lon


def _normalize_geometry_coordinates(coordinates):
    if not isinstance(coordinates, list):
        return coordinates

    if coordinates and isinstance(coordinates[0], (int, float)) and len(coordinates) >= 2:
        return [_normalize_lon(float(coordinates[0])), float(coordinates[1])]

    return [_normalize_geometry_coordinates(item) for item in coordinates]


def _normalize_geometry(geometry: dict | None):
    if not geometry or "coordinates" not in geometry:
        return geometry

    normalized = dict(geometry)
    normalized["coordinates"] = _normalize_geometry_coordinates(geometry["coordinates"])
    return normalized


@router.get("/")
def get_zones(status: str | None = Query(default=None), zone_type: str | None = Query(default=None)):
    if status == "active":
        zones = repo.get_active()
    elif zone_type:
        zones = repo.get_by_type(zone_type)
    else:
        zones = repo.get_all()

    return [json.loads(zone.to_json()) for zone in zones]


@router.get("/{zone_id}")
def get_zone_by_id(zone_id: str):
    zone = repo.get_by_id(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    return json.loads(zone.to_json())


@router.post("/")
def create_zone(zone_in: ZoneCreateSchema):
    payload = zone_in.model_dump(exclude_unset=True)
    payload["geometry"] = _normalize_geometry(payload.get("geometry"))
    zone = ZoneModel(**payload)
    created = repo.create(zone)
    return json.loads(created.to_json())


@router.patch("/{zone_id}")
def update_zone(zone_id: str, zone_in: ZoneUpdateSchema):
    payload = zone_in.model_dump(exclude_unset=True)
    if "geometry" in payload:
        payload["geometry"] = _normalize_geometry(payload.get("geometry"))
    updated = repo.update(zone_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Zone not found")
    return json.loads(updated.to_json())


def _dispatch_zone_status(zone, new_status: str) -> None:
    """Fire a ZONE_STATUS_CHANGED event so observers and the audit log react.

    Wrapped in try/except so a misbehaving observer or a Mongo hiccup on
    the audit-log write cannot break the activate/deactivate response —
    the user-facing status change is the priority; notifications are
    best-effort.
    """
    try:
        dispatcher.dispatch(
            Event(
                event_type="ZONE_STATUS_CHANGED",
                data={
                    "zone_id": str(zone.id),
                    "new_status": new_status,
                    "zone_type": getattr(zone, "zone_type", None),
                    "name": getattr(zone, "name", None),
                },
            )
        )
    except Exception:  # pragma: no cover
        logger.exception("Failed to dispatch ZONE_STATUS_CHANGED for %s", zone.id)


@router.post("/{zone_id}/activate")
def activate_zone(zone_id: str):
    zone = repo.activate(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    _dispatch_zone_status(zone, "active")
    return json.loads(zone.to_json())


@router.post("/{zone_id}/deactivate")
def deactivate_zone(zone_id: str):
    zone = repo.deactivate(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    _dispatch_zone_status(zone, "inactive")
    return json.loads(zone.to_json())


@router.delete("/{zone_id}")
def delete_zone(zone_id: str):
    if not repo.delete(zone_id):
        raise HTTPException(status_code=404, detail="Zone not found")
    return {"deleted": True}
