"""SourceHit: single candidate from a data source (unified fetcher return type)."""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SourceHit:
    """One candidate hit from a source; all fetchers return List[SourceHit]."""
    source: str
    confidence_raw: float
    retrieval_method: str  # 'doi', 'arxiv_id', 'title_search'
    query: str
    rank: int
    fetched_title: str = ""
    fetched_authors: list[str] = field(default_factory=list)
    fetched_year: str = ""
    fetched_doi: Optional[str] = None
    fetched_url: str = ""
    fetched_bibtex: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
