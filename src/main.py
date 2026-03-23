from fastapi import FastAPI
from src.infrastructure.database.database import init_db, close_db
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

app = FastAPI(title="ClearWake Routing")

@app.on_event("startup")
async def startup():
    init_db()

@app.on_event("shutdown")
async def shutdown():
    close_db()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/map", response_class=HTMLResponse)
async def map_view():
    with open("static/map.html") as f:
        return f.read()
