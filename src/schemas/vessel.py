from pydantic import BaseModel
from pydantic import field_validator
from typing import Optional

from src.models.vessel import VESSEL_TYPES


class VesselTypeValidationMixin(BaseModel):
    @field_validator("vessel_type", check_fields=False)
    @classmethod
    def validate_vessel_type(cls, vessel_type: Optional[str]) -> Optional[str]:
        if vessel_type is None:
            return vessel_type
        if vessel_type not in VESSEL_TYPES:
            allowed = ", ".join(VESSEL_TYPES)
            raise ValueError(f"Unsupported vessel_type '{vessel_type}'. Allowed values: {allowed}")
        return vessel_type


class VesselSpecsSchema(BaseModel):
    max_draft_m: Optional[float] = None
    max_speed_knots: Optional[float] = None
    length_m: Optional[float] = None
    beam_m: Optional[float] = None


class VesselCreateSchema(VesselTypeValidationMixin):
    company_id: str
    name: str
    imo_number: str
    vessel_type: str
    specs: Optional[VesselSpecsSchema] = None
    fuel_consumption_rate: Optional[float] = None
    current_status: Optional[str] = "idle"


class VesselUpdateSchema(VesselTypeValidationMixin):
    company_id: Optional[str] = None
    name: Optional[str] = None
    imo_number: Optional[str] = None
    vessel_type: Optional[str] = None
    specs: Optional[VesselSpecsSchema] = None
    fuel_consumption_rate: Optional[float] = None
    current_status: Optional[str] = None
