"""Schemas for the /api/v1/emissions endpoints."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class VoyageEmissionsRequest(BaseModel):
    """Inputs for evaluating a single voyage's emissions."""
    model_config = ConfigDict(extra="ignore")

    fuel_tons:        float = Field(..., ge=0)
    vessel_type:      str
    distance_nm:      float = Field(..., gt=0)
    dwt_tons:         Optional[float] = Field(default=None, ge=0)
    fuel_type:        str = "HFO"
    calls_at_eu_port: bool = False
    compliance_year:  Optional[int] = Field(default=None, ge=2020, le=2050)


class VoyageEmissionsResponse(BaseModel):
    fuel_tons:                      float
    fuel_type:                      str
    co2_tons:                       float
    cii_attained_g_per_dwt_nm:      Optional[float] = None
    cii_required_g_per_dwt_nm:      Optional[float] = None
    cii_ratio:                      Optional[float] = None
    rating:                         Optional[str] = None
    eu_ets_eligible_co2_tons:       Optional[float] = None
    eu_ets_allowance_cost_eur:      Optional[float] = None


class FleetEmissionsRow(BaseModel):
    vessel_id:                  str
    vessel_name:                Optional[str] = None
    vessel_type:                Optional[str] = None
    total_co2_tons:             float
    total_distance_nm:          float
    average_cii_attained:       Optional[float] = None
    rating:                     Optional[str] = None
    voyages:                    int


class FleetEmissionsSummary(BaseModel):
    company_id:                 str
    voyages_considered:         int
    fleet_total_co2_tons:       float
    fleet_total_distance_nm:    float
    eu_ets_total_cost_eur:      float
    by_vessel:                  list[FleetEmissionsRow]
