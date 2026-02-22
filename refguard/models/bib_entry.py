"""BibEntry: unified bibliography entry model (extended from CiteScan)."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BibEntry:
    """Parsed bibliography entry with raw_bibtex and authors list for fusion."""
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

    @property
    def has_arxiv(self) -> bool:
        return bool(self.arxiv_id)

    @property
    def has_doi(self) -> bool:
        return bool(self.doi)

    @property
    def search_query(self) -> str:
        return self.title or self.key
