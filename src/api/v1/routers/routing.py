from fastapi import APIRouter
from core.services.routing_service import RoutingService

router = APIRouter()


class DummyStrategy:
    def calculate(self, request):
        return {"route": "calculated", "input": request}


@router.post("/routes")
def calculate_routes(requests: list):
    service = RoutingService(strategy=DummyStrategy())
    return service.calculate_routes_parallel(requests)
