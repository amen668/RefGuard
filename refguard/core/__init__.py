"""Core: config, logging, exceptions, and cache."""
from .config import settings
from .exceptions import (
    RefGuardException,
    FetcherException,
    ParserException,
    TimeoutException,
)
from .logging import get_logger, setup_logging
from .cache import cache_manager

__all__ = [
    "settings",
    "RefGuardException",
    "FetcherException",
    "ParserException",
    "TimeoutException",
    "get_logger",
    "setup_logging",
    "cache_manager",
]
