"""Base fetcher: search(entry) -> List[SourceHit]."""
from abc import ABC, abstractmethod
from typing import List

from refguard.models import BibEntry, SourceHit


class BaseFetcher(ABC):
    """All fetchers return List[SourceHit] for a BibEntry."""

    @abstractmethod
    def search(self, entry: BibEntry) -> List[SourceHit]:
        """Return candidates for this entry (strong id first, then title)."""
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        """e.g. 'crossref', 'arxiv'."""
        pass
