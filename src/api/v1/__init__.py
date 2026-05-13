from fastapi import APIRouter
from src.api.v1.routers.routes import router as routes_router

router = APIRouter(prefix="/v1")

router.include_router(routes_router)
