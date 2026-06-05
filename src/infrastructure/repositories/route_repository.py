from datetime import datetime
from typing import List, Optional

from bson import ObjectId

from src.models.route import Route


class RouteRepository:
    def create(self, route_data: dict) -> Route:
        route = Route(**route_data)
        route.save()
        return route

    def get_by_id(self, route_id: str) -> Optional[Route]:
        return Route.objects(id=route_id).first()

    def get_by_vessel(self, vessel_id: str) -> List[Route]:
        return list(Route.objects(vessel_id=vessel_id).order_by("-calculated_at"))

    def get_by_company(self, company_id: str) -> List[Route]:
        return list(Route.objects(company_id=company_id).order_by("-calculated_at"))

    def get_by_request(self, request_id: str) -> Optional[Route]:
        return Route.objects(request_id=request_id).first()

    def _apply_filters(
        self,
        queryset,
        *,
        company_id: str | None = None,
        vessel_id: str | None = None,
        optimization_mode: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        is_valid: bool | None = None,
    ):
        if company_id is not None:
            queryset = queryset.filter(company_id=ObjectId(company_id))
        if vessel_id is not None:
            queryset = queryset.filter(vessel_id=ObjectId(vessel_id))
        if optimization_mode is not None:
            queryset = queryset.filter(optimization_mode=optimization_mode)
        if from_date is not None:
            queryset = queryset.filter(calculated_at__gte=from_date)
        if to_date is not None:
            queryset = queryset.filter(calculated_at__lte=to_date)
        if is_valid is not None:
            queryset = queryset.filter(is_valid=is_valid)
        return queryset

    def find_filtered(
        self,
        *,
        company_id: str | None = None,
        vessel_id: str | None = None,
        optimization_mode: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        is_valid: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Route]:
        queryset = self._apply_filters(
            Route.objects,
            company_id=company_id,
            vessel_id=vessel_id,
            optimization_mode=optimization_mode,
            from_date=from_date,
            to_date=to_date,
            is_valid=is_valid,
        )
        return list(
            queryset.order_by("-calculated_at").skip(offset).limit(limit)
        )

    def count_filtered(
        self,
        *,
        company_id: str | None = None,
        vessel_id: str | None = None,
        optimization_mode: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        is_valid: bool | None = None,
    ) -> int:
        queryset = self._apply_filters(
            Route.objects,
            company_id=company_id,
            vessel_id=vessel_id,
            optimization_mode=optimization_mode,
            from_date=from_date,
            to_date=to_date,
            is_valid=is_valid,
        )
        return queryset.count()

    def find_all_filtered(
        self,
        *,
        company_id: str | None = None,
        vessel_id: str | None = None,
        optimization_mode: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        is_valid: bool | None = None,
    ) -> List[Route]:
        """Return all matching routes (for analytics aggregation)."""
        queryset = self._apply_filters(
            Route.objects,
            company_id=company_id,
            vessel_id=vessel_id,
            optimization_mode=optimization_mode,
            from_date=from_date,
            to_date=to_date,
            is_valid=is_valid,
        )
        return list(queryset.order_by("-calculated_at"))
