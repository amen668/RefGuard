"""用于 DOI 查询和高频检索的线程安全缓存。"""
import hashlib
import json
import threading
from functools import wraps
from typing import Any, Callable, Optional

from cachetools import TTLCache

from .config import settings
from .logging import get_logger

logger = get_logger(__name__)


class CacheManager:
    """线程安全的 TTL 缓存。"""

    def __init__(self) -> None:
        self._cache: Optional[TTLCache] = None
        self._lock = threading.Lock()
        self._init()

    def _init(self) -> None:
        if settings.cache_enabled:
            self._cache = TTLCache(maxsize=settings.cache_max_size, ttl=settings.cache_ttl)
        else:
            self._cache = None

    def _key(self, *args: Any, **kwargs: Any) -> str:
        data = {"args": args, "kwargs": sorted(kwargs.items())}
        return hashlib.md5(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        if not settings.cache_enabled or self._cache is None:
            return None
        with self._lock:
            return self._cache.get(key)

    def set(self, key: str, value: Any) -> None:
        if not settings.cache_enabled or self._cache is None:
            return
        with self._lock:
            self._cache[key] = value

    def get_stats(self) -> dict[str, Any]:
        if not settings.cache_enabled or self._cache is None:
            return {"enabled": False, "size": 0, "max_size": 0, "ttl": 0}
        with self._lock:
            return {
                "enabled": True,
                "size": len(self._cache),
                "max_size": self._cache.maxsize,
                "ttl": self._cache.ttl,
            }

    def cached(self, key_prefix: str = "") -> Callable:
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                k = f"{key_prefix}:{func.__name__}:{self._key(*args, **kwargs)}"
                v = self.get(k)
                if v is not None:
                    return v
                v = func(*args, **kwargs)
                self.set(k, v)
                return v
            return wrapper
        return decorator


cache_manager = CacheManager()
