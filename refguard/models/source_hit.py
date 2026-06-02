"""数据源返回的单个候选结果。"""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SourceHit:
    """所有数据源抓取器统一返回的候选结构。"""
    source: str
    confidence_raw: float
    retrieval_method: str
    query: str
    rank: int
    fetched_title: str = ""
    fetched_authors: list[str] = field(default_factory=list)
    fetched_year: str = ""
    fetched_doi: Optional[str] = None
    fetched_url: str = ""
    fetched_bibtex: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
