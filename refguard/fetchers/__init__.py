"""数据源抓取器注册表。"""
from .base import BaseFetcher
from .crossref_fetcher import CrossrefFetcher
from .arxiv_fetcher import ArxivFetcher
from .openalex_fetcher import OpenAlexFetcher
from .semantic_scholar_fetcher import SemanticScholarFetcher
from .dblp_fetcher import DBLPFetcher
from .doi_cn_fetcher import DOIContentNegotiationFetcher

FETCHER_REGISTRY = {
    "crossref": CrossrefFetcher,
    "arxiv": ArxivFetcher,
    "openalex": OpenAlexFetcher,
    "semanticscholar": SemanticScholarFetcher,
    "semantic_scholar": SemanticScholarFetcher,
    "dblp": DBLPFetcher,
    "doicn": DOIContentNegotiationFetcher,
}


def get_fetcher(name: str, **kwargs) -> BaseFetcher | None:
    """按名称创建抓取器，未知数据源返回 None。"""
    cls = FETCHER_REGISTRY.get(name.lower())
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
    "DOIContentNegotiationFetcher",
    "FETCHER_REGISTRY",
    "get_fetcher",
]
