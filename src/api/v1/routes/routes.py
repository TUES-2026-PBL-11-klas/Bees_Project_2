from fastapi import APIRouter
from .zones import router as zones_router

router = APIRouter()

router.include_router(zones_router)
