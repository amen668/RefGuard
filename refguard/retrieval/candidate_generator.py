"""多数据源候选生成。"""

from concurrent.futures import ThreadPoolExecutor

from refguard.core import get_logger
from refguard.fetchers import get_fetcher
from refguard.fetchers.base import FetcherUnavailableError
from refguard.models import BibEntry, SourceHit

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
        """并行查询各数据源，按配置顺序合并候选并返回命中数。"""
        all_hits: list[SourceHit] = []
        per_source: dict[str, int] = {}

        active: list[tuple[str, object]] = []
        for src in self.sources:
            fetcher = self._get_fetcher(src)
            if fetcher is None:
                logger.debug("跳过未知数据源: %s", src)
                per_source[src] = 0
                continue
            active.append((src, fetcher))

        def fetch_one(item: tuple[str, object]) -> tuple[str, list[SourceHit]]:
            src, fetcher = item
            try:
                hits = fetcher.search(entry)
            except FetcherUnavailableError:
                # 研究评测不能把数据源故障等同于“无文献命中”。向上抛出以保留
                # 已写断点并停止本次运行，待额度/网络恢复后再续跑。
                raise
            except Exception as exc:  # noqa: BLE001 - isolate ordinary source-specific failures
                logger.debug("数据源 %s 查询异常: %s", src, exc)
                hits = []
            return src, hits

        # executor.map 按提交顺序返回结果，保证并行化前后的候选优先级一致。
        if active:
            with ThreadPoolExecutor(
                max_workers=len(active), thread_name_prefix="refguard-source"
            ) as pool:
                results = pool.map(fetch_one, active)
                for src, hits in results:
                    per_source[src] = len(hits)
                    all_hits.extend(hits)
        seen = set()
        unique = []
        for h in all_hits:
            key = (h.source, h.fetched_doi or h.fetched_url or h.fetched_title)
            if key in seen:
                continue
            seen.add(key)
            unique.append(h)
        return unique[: self.top_k], per_source
