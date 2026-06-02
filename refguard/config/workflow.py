"""数据源启用配置和默认顺序。"""
from dataclasses import dataclass, field
from typing import List, Optional

# 默认顺序优先使用 DOI 和 arXiv ID 等强标识。
# doicn（DOI 内容协商）跨注册商解析非标准与中文文献的 DOI（DataCite/Airiti 等）。
DEFAULT_SOURCES = [
    "crossref",
    "openalex",
    "arxiv",
    "semanticscholar",
    "dblp",
    "doicn",
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
