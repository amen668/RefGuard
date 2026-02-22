"""Unified data models for RefGuard."""
from .bib_entry import BibEntry
from .citation_context import CitationContext
from .source_hit import SourceHit
from .match_features import MatchFeatures
from .comparison import ComparisonResult
from .report_models import EntryReport, ProjectReport, RunMetadata, UsageResult

__all__ = [
    "BibEntry",
    "CitationContext",
    "SourceHit",
    "MatchFeatures",
    "ComparisonResult",
    "EntryReport",
    "ProjectReport",
    "RunMetadata",
    "UsageResult",
]

