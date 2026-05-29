from .base import BaseAppException


class WeatherServiceException(BaseAppException):
    def __init__(self, message: str, details: str | None = None):
        self.details = details
        super().__init__(message)


class WeatherApiKeyMissingException(WeatherServiceException):
    def __init__(self):
        super().__init__(
            "Weather API is not configured. Set WEATHER_API_KEY in the environment."
        )
