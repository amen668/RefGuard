"""CitationContext: citation location and context (from BibGuard)."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class CitationContext:
    """Citation with its context for Mode B / LLM relevance."""
    key: str
    line_number: int
    command: str
    context_before: str
    context_after: str
    full_context: str
    raw_line: str
    file_path: Optional[str] = None
    window_left: Optional[str] = None
    window_right: Optional[str] = None
