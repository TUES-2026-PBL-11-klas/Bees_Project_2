"""Analytics router."""

from fastapi import APIRouter, HTTPException, Query

from src.core.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])
_service = AnalyticsService()


@router.get("/vessels/{vessel_id}")
def vessel_summary(vessel_id: str, limit: int = Query(default=200, ge=1, le=1000)):
    try:
        return _service.vessel_summary(vessel_id, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/companies/{company_id}")
def company_summary(company_id: str, limit: int = Query(default=500, ge=1, le=2000)):
    try:
        return _service.company_summary(company_id, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/strategy-effectiveness")
def strategy_effectiveness(limit: int = Query(default=1000, ge=1, le=5000)):
    try:
        return _service.strategy_effectiveness(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
