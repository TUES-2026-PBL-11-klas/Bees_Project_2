"""Pydantic schemas for port scheduling endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class PortCreateSchema(BaseModel):
    port_id: str
    name: str
    country: Optional[str] = None
    latitude: float
    longitude: float
    berth_count: int = Field(default=1, ge=1)
    timezone: str = "UTC"


class PortOutSchema(PortCreateSchema):
    pass


class BlackoutWindow(BaseModel):
    start: datetime
    end: datetime
    reason: Optional[str] = None

    @field_validator("end")
    @classmethod
    def _end_after_start(cls, v, info):
        start = info.data.get("start")
        if start is not None and v <= start:
            raise ValueError("end must be after start")
        return v


class PortScheduleSchema(BaseModel):
    opens_at_min: int = Field(default=0, ge=0, le=1439)
    closes_at_min: int = Field(default=1439, ge=0, le=1439)
    operates_weekends: bool = True
    blackouts: List[BlackoutWindow] = Field(default_factory=list)
    notes: Optional[str] = None


class DockReservationCreateSchema(BaseModel):
    port_id: str
    berth_number: int = Field(default=1, ge=1)
    vessel_id: str
    company_id: Optional[str] = None
    start_at: datetime
    end_at: datetime
    purpose: str = "loading"
    notes: Optional[str] = None

    @field_validator("end_at")
    @classmethod
    def _end_after_start(cls, v, info):
        start = info.data.get("start_at")
        if start is not None and v <= start:
            raise ValueError("end_at must be after start_at")
        return v
