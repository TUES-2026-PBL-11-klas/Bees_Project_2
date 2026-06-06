"""Schemas for the multi-leg voyage planner endpoint."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MultiLegPlanRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    port_ids:           list[str] = Field(..., min_length=2)
    optimization_mode:  str = "fastest"
    vessel_id:          Optional[str] = None
    vessel_type:        Optional[str] = None
    optimize_order:     bool = False
    objective:          str = Field(default="fuel", pattern="^(fuel|distance)$")
    include_waypoints:  bool = True


class LegOut(BaseModel):
    from_port:     str
    to_port:       str
    distance_nm:   float
    duration_h:    float
    fuel_tons:     float
    waypoints:     Optional[list[dict]] = None


class MultiLegPlanResponse(BaseModel):
    port_order:         list[str]
    total_distance_nm:  float
    total_duration_h:   float
    total_fuel_tons:    float
    reordered:          bool
    legs_failed:        int
    legs:               list[LegOut]
