"""Pydantic schemas for the optimization router (#80)."""

from typing import Optional

from pydantic import BaseModel, Field


class DraftTrimRequest(BaseModel):
    vessel_id: Optional[str] = Field(default=None, description="Optional DB vessel id; if set, dimensions are loaded from it")
    length_m: Optional[float] = Field(default=None, gt=0)
    beam_m: Optional[float] = Field(default=None, gt=0)
    max_draft_m: Optional[float] = Field(default=None, gt=0)
    max_speed_knots: Optional[float] = Field(default=None, gt=0)
    speed_knots: float = Field(..., gt=0)
    cargo_weight_t: float = Field(..., ge=0)
    max_cargo_t: float = Field(..., gt=0)
    wave_height_m: float = Field(default=0.0, ge=0)
    water_depth_m: Optional[float] = Field(default=None, gt=0)


class DraftTrimResponse(BaseModel):
    optimal_trim_m: float
    optimal_mean_draft_m: float
    optimal_forward_draft_m: float
    optimal_aft_draft_m: float
    baseline_resistance_index: float
    optimized_resistance_index: float
    fuel_savings_pct: float
    notes: list[str] = []
