from fastapi import FastAPI
from src.infrastructure.database.database import init_db, close_db

app = FastAPI(title="ClearWake Routing")

@app.on_event("startup")
async def startup():
    init_db()

@app.on_event("shutdown")
async def shutdown():
    close_db()
