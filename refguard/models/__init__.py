"""RefGuard 的统一数据模型。"""
from .bib_entry import BibEntry
from .citation_context import CitationContext
from .source_hit import SourceHit
from .match_features import MatchFeatures
from .comparison import ComparisonResult
from .report_models import EntryReport, ProjectReport, RunMetadata, UsageResult
from .status import ReportStatus, resolve_report_status

__all__ = [
    "BibEntry",
    "CitationContext",
    "SourceHit",
    "MatchFeatures",
    "ComparisonResult",
    "ReportStatus",
    "resolve_report_status",
    "EntryReport",
    "ProjectReport",
    "RunMetadata",
    "UsageResult",
]

