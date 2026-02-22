"""Usage checker: cited keys, missing citations, unused entries (Mode B)."""
from typing import List

from refguard.models import BibEntry, CitationContext
from refguard.parsers import TexParser
from refguard.models.report_models import UsageResult


class UsageChecker:
    def __init__(self, tex_parser: TexParser) -> None:
        self.tex_parser = tex_parser
        self._cited_keys = tex_parser.get_all_cited_keys()

    def check_usage(self, entry: BibEntry) -> UsageResult:
        key = entry.key
        is_cited = key in self._cited_keys
        contexts = self.tex_parser.get_citation_contexts(key)
        return UsageResult(
            key=key,
            is_cited=is_cited,
            citation_count=len(contexts),
            contexts=contexts,
        )

    def get_unused_entries(self, entries: List[BibEntry]) -> List[BibEntry]:
        return [e for e in entries if e.key not in self._cited_keys]

    def get_missing_citations(self, entries: List[BibEntry]) -> List[str]:
        entry_keys = {e.key for e in entries}
        return [k for k in self._cited_keys if k not in entry_keys]
