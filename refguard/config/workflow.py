"""数据源启用配置和默认顺序。"""
from dataclasses import dataclass, field
from typing import List, Optional

# 默认顺序优先使用 DOI 和 arXiv ID 等强标识。
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
    enabled: Optional[List[str]] = None

    def get_enabled_sources(self) -> List[str]:
        src = self.sources or DEFAULT_SOURCES.copy()
        if self.enabled is not None:
            return [s for s in self.enabled if s in src]
        return src


def get_default_sources() -> List[str]:
    return DEFAULT_SOURCES.copy()
