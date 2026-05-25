from typing import List, Optional
from src.models.route import Route, RouteHistory

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

    # RouteHistory methods
    def save_history(self, history_data: dict) -> RouteHistory:
        history = RouteHistory(**history_data)
        history.save()
        return history

    def find_cached_route(self, origin: str, destination: str, vessel_type: str, optimization_mode: str) -> Optional[RouteHistory]:
        return RouteHistory.objects(
            origin=origin,
            destination=destination,
            vessel_type=vessel_type,
            optimization_mode=optimization_mode
        ).order_by("-calculated_at").first()

    def update_actuals(self, history_id: str, actual_time: float, actual_fuel: float) -> Optional[RouteHistory]:
        RouteHistory.objects(id=history_id).update(
            set__actual_time_h=actual_time,
            set__actual_fuel_tons=actual_fuel
        )
        return RouteHistory.objects(id=history_id).first()

    def get_history_analytics(self, **filters) -> List[RouteHistory]:
        query = {}
        if filters:
            query.update(filters)
        return list(RouteHistory.objects(**query).order_by("-calculated_at"))
