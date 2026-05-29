from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    MONGODB_URI: str = "mongodb://localhost:27017"
    DB_NAME: str = "clearwake"
    APP_PORT: int = 8080
    APP_ENV: str = "development"
    ROUTING_ENGINE_URL: Optional[str] = None
    ROUTING_API_KEY: Optional[str] = None
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    LOG_LEVEL: str = "info"
    MAP_PROVIDER: str = "carto-voyager"
    WEATHER_API_KEY: Optional[str] = None
    WEATHER_API_BASE_URL: str = "https://api.openweathermap.org/data/2.5"
    WEATHER_CACHE_TTL_SECONDS: int = 600
    WEATHER_MAP_MAX_GRID_POINTS: int = 64
    WEATHER_HTTP_TIMEOUT_SECONDS: float = 10.0

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
