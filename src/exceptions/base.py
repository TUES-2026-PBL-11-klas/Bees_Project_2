class BaseAppException(Exception):
    """Base class for all custom exceptions."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ValidationException(BaseAppException):
    pass


class NotFoundException(BaseAppException):
    pass


class ConflictException(BaseAppException):
    pass
