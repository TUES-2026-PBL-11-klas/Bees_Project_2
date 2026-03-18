from .base import BaseAppException


class ZoneIntersectionException(BaseAppException):
    def __init__(self):
        super().__init__("Route intersects restricted zone")
