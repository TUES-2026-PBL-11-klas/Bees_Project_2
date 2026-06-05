from typing import List, Optional

from bson import ObjectId
from bson.errors import InvalidId

from src.models.route import Route

class RouteRepository:
    def create(self, route_data: dict) -> Route:
        route = Route(**route_data)
        route.save()
        return route

    def get_by_id(self, route_id: str) -> Optional[Route]:
        try:
            ObjectId(route_id)
        except (InvalidId, TypeError):
            return None
        return Route.objects(id=route_id).first()

    def get_by_vessel(self, vessel_id: str) -> List[Route]:
        return list(Route.objects(vessel_id=vessel_id).order_by("-calculated_at"))

    def get_by_company(self, company_id: str) -> List[Route]:
        return list(Route.objects(company_id=company_id).order_by("-calculated_at"))

    def get_by_request(self, request_id: str) -> Optional[Route]:
        return Route.objects(request_id=request_id).first()

    def update(self, route_id: str, data: dict) -> Optional[Route]:
        route = self.get_by_id(route_id)
        if route is None:
            return None
        route.update(**data)
        route.reload()
        return route
