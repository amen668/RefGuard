"""Fetchers: unified search(entry) -> List[SourceHit]."""
from .base import BaseFetcher
from .crossref_fetcher import CrossrefFetcher
from .arxiv_fetcher import ArxivFetcher
from .openalex_fetcher import OpenAlexFetcher
from .semantic_scholar_fetcher import SemanticScholarFetcher
from .dblp_fetcher import DBLPFetcher

def get_fetcher(name: str, **kwargs) -> BaseFetcher | None:
    registry = {
        "crossref": CrossrefFetcher,
        "arxiv": ArxivFetcher,
        "openalex": OpenAlexFetcher,
        "semanticscholar": SemanticScholarFetcher,
        "dblp": DBLPFetcher,
    }
    cls = registry.get(name.lower())
    if cls is None:
        return None
    return cls(**kwargs)

__all__ = [
    "BaseFetcher",
    "CrossrefFetcher",
    "ArxivFetcher",
    "OpenAlexFetcher",
    "SemanticScholarFetcher",
    "DBLPFetcher",
    "get_fetcher",
]
