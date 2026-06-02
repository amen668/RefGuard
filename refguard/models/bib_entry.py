"""统一的参考文献条目模型。"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BibEntry:
    """解析后的参考文献条目，供召回和融合判断使用。"""
    key: str
    entry_type: str
    title: str = ""
    author: str = ""
    year: str = ""
    abstract: str = ""
    url: str = ""
    doi: str = ""
    arxiv_id: str = ""
    journal: str = ""
    booktitle: str = ""
    publisher: str = ""
    pages: str = ""
    volume: str = ""
    number: str = ""
    raw_entry: dict = field(default_factory=dict)
    raw_bibtex: str = ""
    authors: list[str] = field(default_factory=list)
    venue: str = ""
