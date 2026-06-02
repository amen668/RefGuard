"""多数据源候选生成。"""

from refguard.models import BibEntry, SourceHit
from refguard.fetchers import get_fetcher
from refguard.core import get_logger

logger = get_logger(__name__)


class CandidateGenerator:
    """调用启用的数据源，合并去重后保留 Top-K。"""

    def __init__(
        self,
        sources: list[str],
        top_k: int = 8,
    ) -> None:
        self.sources = sources
        self.top_k = top_k
        self._fetchers: dict = {}

    def _get_fetcher(self, name: str):
        if name not in self._fetchers:
            self._fetchers[name] = get_fetcher(name)
        return self._fetchers[name]

    def generate(self, entry: BibEntry) -> tuple[list[SourceHit], dict[str, int]]:
        """返回候选列表和每个数据源的命中数。"""
        all_hits: list[SourceHit] = []
        per_source: dict[str, int] = {}

        for src in self.sources:
            fetcher = self._get_fetcher(src)
            if fetcher is None:
                logger.debug("跳过未知数据源: %s", src)
                per_source[src] = 0
                continue
            try:
                hits = fetcher.search(entry)
            except Exception as exc:
                logger.debug("数据源 %s 查询异常: %s", src, exc)
                hits = []
            per_source[src] = len(hits)
            for h in hits:
                all_hits.append(h)
        seen = set()
        unique = []
        for h in all_hits:
            key = (h.source, h.fetched_doi or h.fetched_url or h.fetched_title)
            if key in seen:
                continue
            seen.add(key)
            unique.append(h)
        return unique[: self.top_k], per_source
