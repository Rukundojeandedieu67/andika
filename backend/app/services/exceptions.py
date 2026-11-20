"""Application errors raised by services and translated at the API edge."""


class ServiceError(Exception):
    """A client-facing failure with a stable public message."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ConflictError(ServiceError):
    """A unique account field is already taken."""

    def __init__(self, message: str) -> None:
        super().__init__(message, 409)


class NotFoundError(ServiceError):
    """The requested record does not exist or is not visible."""

    def __init__(self, message: str = "Article not found.") -> None:
        super().__init__(message, 404)


class UnauthorizedError(ServiceError):
    """Credentials or a presented token cannot be accepted."""

    def __init__(self, message: str = "Invalid email or password.") -> None:
        super().__init__(message, 401)
