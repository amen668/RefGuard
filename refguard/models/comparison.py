"""ComparisonResult: extended with match_probability, best_hit, explanations."""
from dataclasses import dataclass, field
from typing import Any, Optional

from .source_hit import SourceHit


@dataclass
class ComparisonResult:
    """Unified comparison output: integrity decision + evidence."""
    entry_key: str
    is_match: bool
    confidence: float
    issues: list[str]
    source: str
    match_probability: float = 0.0
    decision_profile: str = ""
    best_hit: Optional[SourceHit] = None
    top_hits: list[SourceHit] = field(default_factory=list)
    explanations: Optional[dict[str, Any]] = None
    # Legacy/field-level (for report)
    title_match: bool = False
    title_similarity: float = 0.0
    bib_title: str = ""
    fetched_title: str = ""
    author_match: bool = False
    author_similarity: float = 0.0
    bib_authors: list[str] = field(default_factory=list)
    fetched_authors: list[str] = field(default_factory=list)
    year_match: bool = False
    bib_year: str = ""
    fetched_year: str = ""
    fetched_doi: Optional[str] = None
    fetched_url: str = ""
    fetched_bibtex: str = ""

    @property
    def has_issues(self) -> bool:
        return len(self.issues) > 0
