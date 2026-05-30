"""RefGuard 自定义异常。"""


class RefGuardException(Exception):
    """RefGuard 基础异常。"""

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class FetcherException(RefGuardException):
    """数据源查询异常。"""

    def __init__(self, message: str, source: str, details: dict | None = None):
        self.source = source
        super().__init__(message, details)


class ParserException(RefGuardException):
    """解析异常。"""


class ValidationException(RefGuardException):
    """校验异常。"""


class RateLimitException(FetcherException):
    """请求频率超限。"""

    def __init__(self, source: str, retry_after: int | None = None):
        self.retry_after = retry_after
        message = f"{source} 请求频率超限"
        if retry_after:
            message += f"，请在 {retry_after} 秒后重试"
        super().__init__(message, source)


class TimeoutException(FetcherException):
    """请求超时异常。"""

    def __init__(self, source: str, timeout: int):
        message = f"{source} 请求在 {timeout} 秒后超时"
        super().__init__(message, source)
