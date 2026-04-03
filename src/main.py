from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from src.api.router import router as api_router

from src.infrastructure.database.database import init_db, close_db
from src.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    yield

    close_db()

app = FastAPI(title="ClearWake Routing", lifespan=lifespan)

app.include_router(api_router)
app.mount("/static", StaticFiles(directory="src/static"), name="static")


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")

@app.get("/map", response_class=HTMLResponse)
async def map_view():
    try:
        with open("src/static/map.html", "r", encoding="utf-8") as f:
            html = f.read()

        rendered = (
            html.replace("__MAP_PROVIDER__", settings.MAP_PROVIDER)
            .replace("__GOOGLE_MAPS_API_KEY__", settings.GOOGLE_MAPS_API_KEY or "")
        )
        return rendered

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
