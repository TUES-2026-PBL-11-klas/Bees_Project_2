from typing import List, Optional

from bson import ObjectId

from src.models.route import Route


class RouteRepository:
    def create(self, route_data: dict) -> Route:
        route = Route(**route_data)
        route.save()
        return route

    def get_by_id(self, route_id: str) -> Optional[Route]:
        if not ObjectId.is_valid(route_id):
            return None
        return Route.objects(id=ObjectId(route_id)).first()

    def get_by_vessel(self, vessel_id: str) -> List[Route]:
        if not ObjectId.is_valid(vessel_id):
            return []
        return list(Route.objects(vessel_id=ObjectId(vessel_id)).order_by("-calculated_at"))

    def get_by_company(self, company_id: str) -> List[Route]:
        if not ObjectId.is_valid(company_id):
            return []
        return list(Route.objects(company_id=ObjectId(company_id)).order_by("-calculated_at"))

    def get_by_request(self, request_id: str) -> Optional[Route]:
        if not ObjectId.is_valid(request_id):
            return None
        return Route.objects(request_id=ObjectId(request_id)).first()
