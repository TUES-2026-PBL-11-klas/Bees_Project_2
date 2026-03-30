from pydantic import BaseModel
from typing import Optional


class VesselSpecsSchema(BaseModel):
    max_draft_m: Optional[float] = None
    max_speed_knots: Optional[float] = None
    length_m: Optional[float] = None
    beam_m: Optional[float] = None


class VesselCreateSchema(BaseModel):
    company_id: str
    name: str
    imo_number: str
    vessel_type: str
    specs: Optional[VesselSpecsSchema] = None
    fuel_consumption_rate: Optional[float] = None
    current_status: Optional[str] = "idle"


class VesselUpdateSchema(BaseModel):
    company_id: Optional[str] = None
    name: Optional[str] = None
    imo_number: Optional[str] = None
    vessel_type: Optional[str] = None
    specs: Optional[VesselSpecsSchema] = None
    fuel_consumption_rate: Optional[float] = None
    current_status: Optional[str] = None
