"""Custom exceptions for RefGuard."""


class RefGuardException(Exception):
    """Base exception for RefGuard."""

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class FetcherException(RefGuardException):
    """Raised by fetchers."""

    def __init__(self, message: str, source: str, details: dict | None = None):
        self.source = source
        super().__init__(message, details)


class ParserException(RefGuardException):
    """Raised by parsers."""


class ValidationException(RefGuardException):
    """Raised during validation."""


class RateLimitException(FetcherException):
    """Rate limit exceeded; retry_after when provided by server."""

    def __init__(self, source: str, retry_after: int | None = None):
        self.retry_after = retry_after
        message = f"Rate limit exceeded for {source}"
        if retry_after:
            message += f". Retry after {retry_after} seconds"
        super().__init__(message, source)


class TimeoutException(FetcherException):
    """Request timed out."""

    def __init__(self, source: str, timeout: int):
        message = f"Request to {source} timed out after {timeout}s"
        super().__init__(message, source)
