from fastapi import APIRouter, HTTPException
from src.infrastructure.repositories.zone_repositories import ZoneRepository
import json

from src.schemas.zone import ZoneCreateSchema
from src.models.zone import Zone as ZoneModel

router = APIRouter(prefix="/api/v1/zones", tags=["zones"])
repo = ZoneRepository()

@router.get("/")
def get_all_zones():
    try:
        zones = repo.get_all()
        if not zones:
            return []
        import json
        return [json.loads(zone.to_json()) for zone in zones]
    except Exception as e:
        print(f"Error in GET all zones: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{zone_id}")
def get_zone_by_id(zone_id: str):
    try:
        zone = repo.get_by_id(zone_id)
        if not zone:
            raise HTTPException(status_code=404, detail="Zone not found")
        return zone
    except Exception as e:
        print(f"Error in GET single zone: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/")
def create_zone(zone_in: ZoneCreateSchema):
    zone_dict = zone_in.model_dump(exclude_unset=True)

    db_zone = ZoneModel(**zone_dict)

    created_zone = repo.create(db_zone)

    return json.loads(created_zone.to_json())

@router.patch("/{zone_id}/activate")
def activate_zone(zone_id: str):
    return repo.activate(zone_id)

@router.patch("/{zone_id}/deactivate")
def deactivate_zone(zone_id: str):
    return repo.deactivate(zone_id)

@router.delete("/{zone_id}")
def delete_zone(zone_id: str):
    success = repo.delete(zone_id)
    if not success:
        raise HTTPException(status_code=404, detail="Zone not found")
    return {"deleted": True}
