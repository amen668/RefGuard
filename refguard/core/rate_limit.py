"""Per-source rate limiting, retry with backoff, and optional Crossref header awareness."""
import random
import time
from dataclasses import dataclass, field
from typing import Callable, TypeVar

from .exceptions import RateLimitException
from .logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


@dataclass
class SourceRateLimit:
    """Per-source delay and concurrency (semaphore can be added by caller)."""
    source: str
    min_delay: float
    last_request_time: float = 0.0

    def wait_before_request(self) -> None:
        elapsed = time.monotonic() - self.last_request_time
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self.last_request_time = time.monotonic()


class RateLimitLayer:
    """Apply per-source delay and retry with exponential backoff."""

    def __init__(
        self,
        get_delay_for_source: Callable[[str], float],
        max_retries: int = 3,
        base_backoff: float = 1.0,
        jitter: bool = True,
    ) -> None:
        self.get_delay_for_source = get_delay_for_source
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self.jitter = jitter
        self._last: dict[str, float] = {}

    def wait(self, source: str) -> None:
        delay = self.get_delay_for_source(source)
        last = self._last.get(source, 0.0)
        elapsed = time.monotonic() - last
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last[source] = time.monotonic()

    def retry_with_backoff(
        self,
        source: str,
        fn: Callable[[], T],
        retry_after: Callable[[], int | None] | None = None,
    ) -> T:
        """Run fn; on 429/503/network errors, back off and retry. Respect Retry-After if provided."""
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            self.wait(source)
            try:
                return fn()
            except RateLimitException as e:
                last_exc = e
                wait = e.retry_after if e.retry_after else self.base_backoff * (2 ** attempt)
                if retry_after:
                    ra = retry_after()
                    if ra is not None:
                        wait = ra
                if self.jitter:
                    wait = wait * (0.5 + random.random())
                logger.warning("Rate limit for %s, retry in %.1fs (attempt %d)", source, wait, attempt + 1)
                time.sleep(wait)
            except (ConnectionError, TimeoutError) as e:
                last_exc = e
                wait = self.base_backoff * (2 ** attempt)
                if self.jitter:
                    wait = wait * (0.5 + random.random())
                logger.warning("Network error for %s: %s; retry in %.1fs", source, e, wait)
                time.sleep(wait)
        if last_exc:
            raise last_exc
        raise RuntimeError("retry_with_backoff: no result")
