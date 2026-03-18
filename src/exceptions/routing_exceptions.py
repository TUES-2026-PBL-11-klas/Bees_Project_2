from .base import BaseAppException


class RouteNotFoundException(BaseAppException):
    def __init__(self, source, destination):
        super().__init__(f"No route found from {source} to {destination}")
