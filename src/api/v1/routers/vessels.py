import json
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query

from src.core.services.vessel_status_service import VesselStatusService
from src.infrastructure.repositories.vessel_repository import VesselRepository
from src.models.vessel import Vessel as VesselModel
from src.schemas.vessel import VesselCreateSchema, VesselUpdateSchema

router = APIRouter(prefix="/api/v1/vessels", tags=["vessels"])
repo = VesselRepository()
status_service = VesselStatusService(repo)


@router.get("/")
def get_all_vessels(
    company_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
):
    if company_id:
        vessels = repo.get_by_company(company_id)
    elif status:
        vessels = repo.get_by_status(status)
    else:
        vessels = repo.get_all()
    return [json.loads(vessel.to_json()) for vessel in vessels]


@router.get("/{vessel_id}")
def get_vessel_by_id(vessel_id: str):
    vessel = repo.get_by_id(vessel_id)
    if not vessel:
        raise HTTPException(status_code=404, detail="Vessel not found")
    return json.loads(vessel.to_json())


@router.post("/")
def create_vessel(vessel_in: VesselCreateSchema):
    payload = vessel_in.model_dump(exclude_unset=True)

    if not ObjectId.is_valid(payload["company_id"]):
        raise HTTPException(status_code=400, detail="Invalid company_id")

    payload["company_id"] = ObjectId(payload["company_id"])
    vessel = VesselModel.build(**payload)
    created = repo.create(vessel)
    return json.loads(created.to_json())


@router.patch("/{vessel_id}")
def update_vessel(vessel_id: str, vessel_in: VesselUpdateSchema):
    payload = vessel_in.model_dump(exclude_unset=True)

    if "company_id" in payload:
        if not ObjectId.is_valid(payload["company_id"]):
            raise HTTPException(status_code=400, detail="Invalid company_id")
        payload["company_id"] = ObjectId(payload["company_id"])

    updated = status_service.update_vessel(vessel_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Vessel not found")
    return json.loads(updated.to_json())


@router.delete("/{vessel_id}")
def delete_vessel(vessel_id: str):
    if not repo.delete(vessel_id):
        raise HTTPException(status_code=404, detail="Vessel not found")
    return {"deleted": True}
