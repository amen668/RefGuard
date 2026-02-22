"""Workflow: enabled sources and order (strong id first, then title search)."""
from dataclasses import dataclass, field
from typing import List, Optional

# Default source order: DOI/arXiv ID lookups first, then title search
DEFAULT_SOURCES = [
    "crossref",
    "openalex",
    "arxiv",
    "semanticscholar",
    "dblp",
]


@dataclass
class WorkflowConfig:
    sources: List[str] = field(default_factory=list)
    enabled: Optional[List[str]] = None  # if None, use all in sources

    def get_enabled_sources(self) -> List[str]:
        src = self.sources or DEFAULT_SOURCES.copy()
        if self.enabled is not None:
            return [s for s in self.enabled if s in src]
        return src


def get_default_sources() -> List[str]:
    return DEFAULT_SOURCES.copy()
