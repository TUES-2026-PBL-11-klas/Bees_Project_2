from fastapi import APIRouter
from src.api.v1.routers import companies, routes, routing, vessels, zones
from src.api.v1.routers import ai as ai_router

router = APIRouter()
router.include_router(routes.router)
router.include_router(routing.router)
router.include_router(vessels.router)
router.include_router(companies.router)
router.include_router(zones.router)
router.include_router(ai_router.router)
