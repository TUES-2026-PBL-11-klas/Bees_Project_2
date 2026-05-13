from typing import List, Optional
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
