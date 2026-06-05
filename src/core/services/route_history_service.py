import json
from datetime import datetime
from typing import Optional

from bson import ObjectId

from src.infrastructure.repositories.route_repository import RouteRepository
from src.models.route import Route
from src.schemas.route import (
    ModeAnalytics,
    RouteAnalyticsAverages,
    RouteAnalyticsResponse,
    RouteAnalyticsTotals,
    RouteHistoryFilters,
    RouteHistoryItem,
    RouteHistoryResponse,
)


class RouteHistoryService:
    def __init__(self, repository: RouteRepository | None = None):
        self._repo = repository or RouteRepository()

    @staticmethod
    def _validate_object_id(value: str, field_name: str) -> None:
        if not ObjectId.is_valid(value):
            raise ValueError(f"Invalid {field_name}: must be a valid ObjectId.")

    @staticmethod
    def _validate_optimization_mode(value: str) -> None:
        if value not in ("fastest", "eco"):
            raise ValueError("optimization_mode must be 'fastest' or 'eco'.")

    def _normalize_filters(
        self,
        *,
        company_id: Optional[str] = None,
        vessel_id: Optional[str] = None,
        optimization_mode: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        is_valid: Optional[bool] = None,
    ) -> RouteHistoryFilters:
        if company_id is not None:
            self._validate_object_id(company_id, "company_id")
        if vessel_id is not None:
            self._validate_object_id(vessel_id, "vessel_id")
        if optimization_mode is not None:
            self._validate_optimization_mode(optimization_mode)
        if from_date and to_date and from_date > to_date:
            raise ValueError("from_date must be earlier than or equal to to_date.")

        return RouteHistoryFilters(
            company_id=company_id,
            vessel_id=vessel_id,
            optimization_mode=optimization_mode,
            from_date=from_date,
            to_date=to_date,
            is_valid=is_valid,
        )

    @staticmethod
    def _to_history_item(route: Route) -> RouteHistoryItem:
        data = json.loads(route.to_json())
        waypoints = data.get("waypoints") or []
        return RouteHistoryItem(
            id=str(data.get("_id", "")),
            request_id=str(data.get("request_id", "")),
            company_id=str(data.get("company_id", "")),
            vessel_id=str(data.get("vessel_id", "")),
            optimization_mode=data.get("optimization_mode", ""),
            total_distance_nm=data.get("total_distance_nm"),
            estimated_duration_h=data.get("estimated_duration_h"),
            estimated_fuel_tons=data.get("estimated_fuel_tons"),
            waypoint_count=len(waypoints),
            is_valid=bool(data.get("is_valid", True)),
            calculated_at=data.get("calculated_at"),
        )

    def get_history(
        self,
        *,
        company_id: Optional[str] = None,
        vessel_id: Optional[str] = None,
        optimization_mode: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        is_valid: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> RouteHistoryResponse:
        filters = self._normalize_filters(
            company_id=company_id,
            vessel_id=vessel_id,
            optimization_mode=optimization_mode,
            from_date=from_date,
            to_date=to_date,
            is_valid=is_valid,
        )

        query_kwargs = filters.model_dump(exclude_none=True)
        total = self._repo.count_filtered(**query_kwargs)
        routes = self._repo.find_filtered(
            **query_kwargs,
            limit=limit,
            offset=offset,
        )

        return RouteHistoryResponse(
            filters=filters,
            total=total,
            limit=limit,
            offset=offset,
            items=[self._to_history_item(route) for route in routes],
        )

    def get_analytics(
        self,
        *,
        company_id: Optional[str] = None,
        vessel_id: Optional[str] = None,
        optimization_mode: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        is_valid: Optional[bool] = None,
    ) -> RouteAnalyticsResponse:
        filters = self._normalize_filters(
            company_id=company_id,
            vessel_id=vessel_id,
            optimization_mode=optimization_mode,
            from_date=from_date,
            to_date=to_date,
            is_valid=is_valid,
        )

        routes = self._repo.find_all_filtered(**filters.model_dump(exclude_none=True))

        totals = RouteAnalyticsTotals()
        by_mode: dict[str, ModeAnalytics] = {}
        valid_count = 0

        for route in routes:
            distance = route.total_distance_nm or 0.0
            duration = route.estimated_duration_h or 0.0
            fuel = route.estimated_fuel_tons or 0.0

            totals.distance_nm += distance
            totals.duration_h += duration
            totals.fuel_tons += fuel

            if route.is_valid:
                valid_count += 1

            mode = route.optimization_mode or "unknown"
            bucket = by_mode.setdefault(
                mode,
                ModeAnalytics(count=0),
            )
            bucket.count += 1
            bucket.total_distance_nm += distance
            bucket.total_duration_h += duration
            bucket.total_fuel_tons += fuel

        total_routes = len(routes)
        averages = RouteAnalyticsAverages()
        if total_routes > 0:
            averages.distance_nm = round(totals.distance_nm / total_routes, 2)
            averages.duration_h = round(totals.duration_h / total_routes, 2)
            averages.fuel_tons = round(totals.fuel_tons / total_routes, 2)

        for bucket in by_mode.values():
            if bucket.count > 0:
                bucket.avg_distance_nm = round(bucket.total_distance_nm / bucket.count, 2)
                bucket.avg_duration_h = round(bucket.total_duration_h / bucket.count, 2)
                bucket.avg_fuel_tons = round(bucket.total_fuel_tons / bucket.count, 2)

        totals.distance_nm = round(totals.distance_nm, 2)
        totals.duration_h = round(totals.duration_h, 2)
        totals.fuel_tons = round(totals.fuel_tons, 2)

        return RouteAnalyticsResponse(
            filters=filters,
            total_routes=total_routes,
            valid_routes=valid_count,
            invalid_routes=total_routes - valid_count,
            totals=totals,
            averages=averages,
            by_optimization_mode=by_mode,
        )
