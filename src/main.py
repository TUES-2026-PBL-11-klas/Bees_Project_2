from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException
from fastapi.responses import HTMLResponse
import traceback

from src.infrastructure.database.database import init_db, close_db
from src.api.routers.zones import router as zones_router
from src.api.routers.routes import router as routes_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    yield

    close_db()

app = FastAPI(title="ClearWake Routing", lifespan=lifespan)

app.include_router(zones_router)
app.include_router(routes_router)

app.mount("/static", StaticFiles(directory="src/static"), name="static")

@app.get("/map", response_class=HTMLResponse)
async def map_view():
    try:
        with open("src/static/map.html", "r", encoding="utf-8") as f:
            return f.read()

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="The file 'src/static/map.html' isn't found. Make sure you have started uvicorn from the main folder of the project."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Server error while reading: {str(e)}"
        )
