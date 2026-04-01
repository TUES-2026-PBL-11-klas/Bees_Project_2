from fastapi import APIRouter
from api.v1 import router as v1_router
from v1.routers import zones,vessels,companies

router = APIRouter()
router.include_router(zones.router, prefix="/v1/zones", tags=["zones"])
router.include_router(vessels.router, prefix="/v1/vessels", tags=["vessels"])
router.include_router(companies.router, prefix="/v1/companies", tags=["companies"])
