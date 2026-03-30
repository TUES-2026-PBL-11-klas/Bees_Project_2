from fastapi import APIRouter
from .routes.routes import router as routes_router

router = APIRouter(prefix="/v1")

router.include_router(routes_router)
