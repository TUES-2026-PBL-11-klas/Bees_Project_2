from .base import ValidationException


class InvalidSpeedException(ValidationException):
    def __init__(self, speed, max_speed):
        super().__init__(f"Speed {speed} exceeds max speed {max_speed}")


class InvalidWeightException(ValidationException):
    def __init__(self, weight):
        super().__init__(f"Invalid vessel weight: {weight}")
