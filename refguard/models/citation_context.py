"""LaTeX 引用位置和上下文。"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class CitationContext:
    """单次引用命令及其前后文。"""
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
