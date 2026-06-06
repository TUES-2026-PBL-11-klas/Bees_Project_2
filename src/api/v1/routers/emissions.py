"""
Emissions & CII router (issue: new feature).

Endpoints
---------
* ``POST /api/v1/emissions/voyage`` — evaluate a single voyage end-to-end.
* ``GET  /api/v1/emissions/fleet/{company_id}`` — aggregate a company's
  recent voyages from ``RouteHistory`` and grade each vessel.

The fleet endpoint reads from ``RouteHistory`` (which the routes router
already persists on every successful calculation), so as soon as a fleet
operator has accumulated some history they get a real sustainability
dashboard with no extra integration work.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query

from src.core.services.emissions_service import EmissionsService
from src.models.route_history import RouteHistory
from src.models.vessel import Vessel
from src.schemas.emissions import (
    FleetEmissionsRow,
    FleetEmissionsSummary,
    VoyageEmissionsRequest,
    VoyageEmissionsResponse,
)

router = APIRouter(prefix="/api/v1/emissions", tags=["emissions"])


def _service(year: Optional[int]) -> EmissionsService:
    return EmissionsService(compliance_year=year) if year else EmissionsService()


@router.post("/voyage", response_model=VoyageEmissionsResponse)
def evaluate_voyage(payload: VoyageEmissionsRequest):
    """Evaluate CO2, CII rating, and EU ETS allowance cost for a single voyage."""
    svc = _service(payload.compliance_year)
    result = svc.evaluate_voyage(
        fuel_tons=payload.fuel_tons,
        vessel_type=payload.vessel_type,
        distance_nm=payload.distance_nm,
        dwt_tons=payload.dwt_tons,
        fuel_type=payload.fuel_type,
        calls_at_eu_port=payload.calls_at_eu_port,
    )
    return VoyageEmissionsResponse(**result.to_dict())


@router.get("/fleet/{company_id}", response_model=FleetEmissionsSummary)
def fleet_emissions(
    company_id: str,
    limit: int = Query(default=500, ge=1, le=5000),
    year: Optional[int] = Query(default=None, ge=2020, le=2050),
    fuel_type: str = Query(default="HFO"),
    calls_at_eu_port: bool = Query(
        default=False,
        description="Apply EU ETS allowance pricing to every voyage in scope.",
    ),
):
    """Aggregate the company's recent voyages and produce a per-vessel CII grade."""
    if not ObjectId.is_valid(company_id):
        raise HTTPException(status_code=400, detail="Invalid company_id")

    history = list(
        RouteHistory.objects(company_id=ObjectId(company_id))
        .order_by("-calculated_at")
        .limit(limit)
    )
    if not history:
        return FleetEmissionsSummary(
            company_id=company_id,
            voyages_considered=0,
            fleet_total_co2_tons=0.0,
            fleet_total_distance_nm=0.0,
            eu_ets_total_cost_eur=0.0,
            by_vessel=[],
        )

    # Pre-load vessels in bulk so we can resolve type / DWT without N+1 queries.
    vessel_ids = {h.vessel_id for h in history if h.vessel_id}
    vessels = {v.id: v for v in Vessel.objects(id__in=list(vessel_ids))}

    svc = _service(year)
    by_vessel_co2: dict[str, float] = defaultdict(float)
    by_vessel_dist: dict[str, float] = defaultdict(float)
    by_vessel_cii_sum: dict[str, float] = defaultdict(float)
    by_vessel_cii_n: dict[str, int] = defaultdict(int)
    by_vessel_voyages: dict[str, int] = defaultdict(int)
    fleet_ets_cost = 0.0

    for h in history:
        fuel = float(h.estimated_fuel_tons or 0.0)
        dist = float(h.total_distance_nm or 0.0)
        if fuel <= 0 or dist <= 0:
            continue

        vessel = vessels.get(h.vessel_id) if h.vessel_id else None
        vtype = getattr(vessel, "vessel_type", None) or "bulk_carrier"
        dwt = None
        if vessel and getattr(vessel, "specs", None):
            dwt = getattr(vessel.specs, "max_cargo_t", None) or getattr(vessel.specs, "cargo_weight_t", None)

        result = svc.evaluate_voyage(
            fuel_tons=fuel,
            vessel_type=vtype,
            distance_nm=dist,
            dwt_tons=dwt,
            fuel_type=fuel_type,
            calls_at_eu_port=calls_at_eu_port,
        )
        key = str(h.vessel_id) if h.vessel_id else "unknown"
        by_vessel_co2[key] += result.co2_tons
        by_vessel_dist[key] += dist
        by_vessel_voyages[key] += 1
        if result.cii_attained is not None:
            by_vessel_cii_sum[key] += result.cii_attained
            by_vessel_cii_n[key] += 1
        if result.eu_ets_allowance_cost_eur:
            fleet_ets_cost += result.eu_ets_allowance_cost_eur

    rows = []
    for vid, co2 in by_vessel_co2.items():
        vessel = vessels.get(ObjectId(vid)) if ObjectId.is_valid(vid) else None
        avg_cii = (
            by_vessel_cii_sum[vid] / by_vessel_cii_n[vid]
            if by_vessel_cii_n[vid] > 0
            else None
        )
        # Grade against this vessel's reference once we have its average CII.
        rating = None
        if avg_cii is not None and vessel:
            dwt = None
            if vessel.specs:
                dwt = vessel.specs.max_cargo_t or vessel.specs.cargo_weight_t
            if dwt and dwt > 0:
                from src.core.services.emissions_service import (
                    cii_rating,
                    required_cii_for_year,
                )
                required = required_cii_for_year(
                    vessel.vessel_type or "bulk_carrier",
                    dwt,
                    svc.compliance_year,
                )
                rating = cii_rating(avg_cii, required, vessel.vessel_type or "bulk_carrier")

        rows.append(FleetEmissionsRow(
            vessel_id=vid,
            vessel_name=getattr(vessel, "name", None) if vessel else None,
            vessel_type=getattr(vessel, "vessel_type", None) if vessel else None,
            total_co2_tons=round(co2, 3),
            total_distance_nm=round(by_vessel_dist[vid], 2),
            average_cii_attained=round(avg_cii, 4) if avg_cii is not None else None,
            rating=rating,
            voyages=by_vessel_voyages[vid],
        ))

    rows.sort(key=lambda r: r.total_co2_tons, reverse=True)

    return FleetEmissionsSummary(
        company_id=company_id,
        voyages_considered=len(history),
        fleet_total_co2_tons=round(sum(by_vessel_co2.values()), 3),
        fleet_total_distance_nm=round(sum(by_vessel_dist.values()), 2),
        eu_ets_total_cost_eur=round(fleet_ets_cost, 2),
        by_vessel=rows,
    )
