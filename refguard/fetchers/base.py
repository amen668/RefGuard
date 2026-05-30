"""数据源抓取器基类。"""
from abc import ABC
import time
from typing import ClassVar

import requests

from refguard.core import get_logger, settings
from refguard.models import BibEntry, SourceHit

logger = get_logger(__name__)


class BaseFetcher(ABC):
    """按统一流程查询候选，子类只实现具体数据源逻辑。"""

    source_name: ClassVar[str] = ""
    max_results: ClassVar[int] = 10
    user_agent: ClassVar[str] = "RefGuard/1.0"

    def __init__(self, *, rate_limit_delay: float = 0.0, timeout: int | None = None) -> None:
        self._last_request_at = 0.0
        self._delay = rate_limit_delay
        self._timeout = timeout or getattr(settings, "request_timeout", 30)
        self._session = requests.Session()
        self._session.headers["User-Agent"] = self.user_agent

    def search(self, entry: BibEntry) -> list[SourceHit]:
        """先查强标识，再查题名，并统一补齐候选元数据。"""
        hits: list[SourceHit] = []
        for method, query, hook in self._query_plan(entry):
            if not query or len(hits) >= self.max_results:
                continue
            try:
                new_hits = hook(query)
            except Exception as exc:
                logger.debug("%s 查询失败: %s", self.source_name, exc)
                new_hits = []
            hits.extend(self._prepare_hits(new_hits, method, query, start_rank=len(hits) + 1))
        return hits[: self.max_results]

    def _query_plan(self, entry: BibEntry) -> list[tuple[str, str | None, object]]:
        return [
            ("doi", entry.doi, self.lookup_by_doi),
            ("arxiv_id", entry.arxiv_id, self.lookup_by_arxiv_id),
            ("title_search", entry.title, self.search_by_title),
        ]

    def lookup_by_doi(self, doi: str) -> list[SourceHit]:
        return []

    def lookup_by_arxiv_id(self, arxiv_id: str) -> list[SourceHit]:
        return []

    def search_by_title(self, title: str) -> list[SourceHit]:
        return []

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._delay:
            time.sleep(self._delay - elapsed)
        self._last_request_at = time.monotonic()

    def _prepare_hits(
        self,
        hits: list[SourceHit] | SourceHit | None,
        method: str,
        query: str,
        start_rank: int,
    ) -> list[SourceHit]:
        if hits is None:
            return []
        if isinstance(hits, SourceHit):
            hit_list = [hits]
        else:
            hit_list = [hit for hit in hits if hit]
        prepared: list[SourceHit] = []
        for offset, hit in enumerate(hit_list):
            hit.source = hit.source or self.source_name
            hit.rank = start_rank + offset
            hit.retrieval_method = hit.retrieval_method or method
            hit.query = hit.query or query
            prepared.append(hit)
        return prepared
