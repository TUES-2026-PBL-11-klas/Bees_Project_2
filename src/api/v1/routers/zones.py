from fastapi import APIRouter, HTTPException
from bson import ObjectId
from src.core.events.event import Event
from src.core.events.dispatcher_instance import dispatcher

from src.models.zone import Zone

from src.core.events.event import Event
from src.core.events.dispatcher_instance import dispatcher

router = APIRouter(prefix="/zones", tags=["zones"])


@router.patch("/{zone_id}/status")
def update_zone_status(zone_id: str, status: str):
    zone = Zone.objects(id=zone_id).first()

    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    if status not in ["active", "inactive"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    zone.status = status
    zone.save()

    event = Event(
        event_type="ZONE_STATUS_CHANGED",
        data={
            "zone_id": str(zone.id),
            "status": zone.status
        }
    )

    dispatcher.dispatch(event)

    return {"message": "Zone status updated", "status": zone.status}


@router.get("/")
def get_zones():
    zones = Zone.objects()
    return [z.to_json() for z in zones]
