from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


_ALLOWED_MODES = {"fastest", "eco"}


class FleetProfileCreateSchema(BaseModel):
    company_id: str
    name: str = Field(min_length=1)
    description: Optional[str] = None
    vessel_ids: List[str] = Field(default_factory=list)
    default_optimization_mode: str = "fastest"
    preferred_route_ids: List[str] = Field(default_factory=list)
    emission_target_kg_co2_per_nm: Optional[float] = None

    @field_validator("default_optimization_mode")
    @classmethod
    def _check_mode(cls, mode: str) -> str:
        if mode not in _ALLOWED_MODES:
            raise ValueError(f"default_optimization_mode must be one of {_ALLOWED_MODES}")
        return mode


class FleetProfileUpdateSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    vessel_ids: Optional[List[str]] = None
    default_optimization_mode: Optional[str] = None
    preferred_route_ids: Optional[List[str]] = None
    emission_target_kg_co2_per_nm: Optional[float] = None

    @field_validator("default_optimization_mode")
    @classmethod
    def _check_mode(cls, mode: Optional[str]) -> Optional[str]:
        if mode is None:
            return mode
        if mode not in _ALLOWED_MODES:
            raise ValueError(f"default_optimization_mode must be one of {_ALLOWED_MODES}")
        return mode
