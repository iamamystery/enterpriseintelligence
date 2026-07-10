class ETIPError(Exception):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(ETIPError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, status_code=404)


class AlreadyExistsError(ETIPError):
    def __init__(self, message: str = "Resource already exists") -> None:
        super().__init__(message, status_code=409)


class AuthenticationError(ETIPError):
    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message, status_code=401)


class AuthorizationError(ETIPError):
    def __init__(self, message: str = "Not authorized to perform this action") -> None:
        super().__init__(message, status_code=403)


class ValidationError(ETIPError):
    def __init__(self, message: str = "Validation failed") -> None:
        super().__init__(message, status_code=422)


class ScraperError(ETIPError):
    def __init__(self, message: str = "Scraper operation failed") -> None:
        super().__init__(message, status_code=502)
