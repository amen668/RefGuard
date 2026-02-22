"""EntryReport, ProjectReport, RunMetadata for reports and API."""
from dataclasses import dataclass, field
from typing import Any, Optional

from .bib_entry import BibEntry
from .comparison import ComparisonResult


@dataclass
class RunMetadata:
    """Reproducibility: profile, sources, version."""
    profile: str = ""
    sources: list[str] = field(default_factory=list)
    top_k_candidates: int = 5
    stop_on_confidence: float = 0.995
    match_threshold: float = 0.95
    gap_threshold: float = 0.05
    version: str = ""
    config_snapshot: Optional[dict[str, Any]] = None


@dataclass
class UsageResult:
    """Mode B: usage for one entry."""
    key: str
    is_cited: bool
    citation_count: int
    contexts: list[Any] = field(default_factory=list)  # CitationContext[]


@dataclass
class EntryReport:
    """Single entry report: entry + comparison + optional usage/evaluations."""
    entry: BibEntry
    comparison: Optional[ComparisonResult] = None
    usage: Optional[UsageResult] = None
    evaluations: list[Any] = field(default_factory=list)


@dataclass
class ProjectReport:
    """Full run report (JSON / MD schema)."""
    summary: dict[str, int]  # total, verified, warning, error
    entry_reports: list[EntryReport] = field(default_factory=list)
    duplicate_groups: list[Any] = field(default_factory=list)
    missing_citations: list[str] = field(default_factory=list)
    unused_entries: list[str] = field(default_factory=list)
    run_metadata: Optional[RunMetadata] = None
    latex_issues: list[Any] = field(default_factory=list)
