"""CandidateGenerator: aggregate multi-source candidates and keep Top-K."""
from typing import List

from refguard.models import BibEntry, SourceHit
from refguard.fetchers import get_fetcher
from refguard.config import get_profile


class CandidateGenerator:
    """Call enabled fetchers for one entry, merge, deduplicate, and keep Top-K."""

    def __init__(
        self,
        sources: List[str],
        top_k: int = 8,
    ) -> None:
        self.sources = sources
        self.top_k = top_k
        self._fetchers: dict = {}

    def _get_fetcher(self, name: str):
        if name not in self._fetchers:
            self._fetchers[name] = get_fetcher(name)
        return self._fetchers[name]

    def generate(self, entry: BibEntry) -> tuple[List[SourceHit], dict[str, int]]:
        """Return (candidates up to top_k, per_source_counts for reporting)."""
        all_hits: List[SourceHit] = []
        per_source: dict[str, int] = {}

        for src in self.sources:
            fetcher = self._get_fetcher(src)
            if fetcher is None:
                continue
            try:
                hits = fetcher.search(entry)
            except Exception:
                hits = []
            per_source[src] = len(hits)
            for h in hits:
                all_hits.append(h)
        # Deduplicate by (source, fetched_doi or fetched_title)
        seen = set()
        unique = []
        for h in all_hits:
            key = (h.source, h.fetched_doi or h.fetched_url or h.fetched_title)
            if key in seen:
                continue
            seen.add(key)
            unique.append(h)
        return unique[: self.top_k], per_source
