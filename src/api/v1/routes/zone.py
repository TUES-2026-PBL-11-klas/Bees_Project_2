from fastapi import APIRouter

router = APIRouter()


@router.get("/zones")
def get_zones():
    return {"message": "List of zones"}
