# src/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MONGODB_URI: str = "mongodb://localhost:27017"
    DB_NAME: str = "clearwake"

    class Config:
        env_file = ".env"

settings = Settings()
