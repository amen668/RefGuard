"""报告和接口使用的数据结构。"""
from dataclasses import dataclass, field
from typing import Any, Optional

from .bib_entry import BibEntry
from .comparison import ComparisonResult


@dataclass
class RunMetadata:
    """用于复现实验的运行配置。"""
    profile: str = ""
    sources: list[str] = field(default_factory=list)
    top_k_candidates: int = 5
    match_threshold: float = 0.95
    gap_threshold: float = 0.05
    version: str = ""


@dataclass
class UsageResult:
    """单个 BibTeX 条目的引用使用情况。"""
    key: str
    is_cited: bool
    citation_count: int
    contexts: list[Any] = field(default_factory=list)


@dataclass
class EntryReport:
    """单条参考文献报告。"""
    entry: BibEntry
    comparison: Optional[ComparisonResult] = None
    usage: Optional[UsageResult] = None


@dataclass
class ProjectReport:
    """一次完整核验的报告结构。"""
    summary: dict[str, int]
    entry_reports: list[EntryReport] = field(default_factory=list)
    duplicate_groups: list[Any] = field(default_factory=list)
    missing_citations: list[str] = field(default_factory=list)
    unused_entries: list[str] = field(default_factory=list)
    run_metadata: Optional[RunMetadata] = None
