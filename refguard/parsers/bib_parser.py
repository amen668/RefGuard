"""BibTeX 解析器，补充原始条目、作者列表和来源字段。"""
import re
from pathlib import Path

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode

from refguard.models import BibEntry


class BibParser:
    """将 .bib 内容解析为 BibEntry 列表。"""

    ARXIV_PATTERNS = [
        r'(\d{4}\.\d{4,5}(?:v\d+)?)',
        r'([a-z-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)',
        r'arXiv:(\d{4}\.\d{4,5}(?:v\d+)?)',
        r'arXiv:([a-z-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)',
    ]
    ARXIV_URL_PATTERNS = [
        r'arxiv\.org/abs/(\d{4}\.\d{4,5}(?:v\d+)?)',
        r'arxiv\.org/abs/([a-z-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)',
        r'arxiv\.org/pdf/(\d{4}\.\d{4,5}(?:v\d+)?)(?:\.pdf)?',
        r'arxiv\.org/pdf/([a-z-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)(?:\.pdf)?',
    ]

    def __init__(self) -> None:
        self.entries: list[BibEntry] = []

    def parse_file(self, filepath: str) -> list[BibEntry]:
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"找不到 Bib 文件：{filepath}")
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return self.parse_content(content)

    def parse_content(self, content: str) -> list[BibEntry]:
        parser = BibTexParser(common_strings=True)
        parser.customization = convert_to_unicode
        try:
            bib_database = bibtexparser.loads(content, parser=parser)
        except Exception as e:
            raise ValueError(f"Bib 内容解析失败：{e}") from e
        self.entries = []
        for entry in bib_database.entries:
            bib_entry = self._convert_entry(entry)
            self.entries.append(bib_entry)
        return self.entries

    def _convert_entry(self, entry: dict) -> BibEntry:
        author_str = entry.get("author", "")
        authors_list: list[str] = []
        if author_str:
            authors_list = [a.strip() for a in re.split(r"\s+and\s+", author_str, flags=re.IGNORECASE) if a.strip()]
        journal = entry.get("journal", "")
        booktitle = entry.get("booktitle", "")
        venue = journal or booktitle or ""

        bib_entry = BibEntry(
            key=entry.get("ID", ""),
            entry_type=entry.get("ENTRYTYPE", "misc"),
            title=entry.get("title", ""),
            author=author_str,
            year=entry.get("year", ""),
            abstract=entry.get("abstract", ""),
            url=entry.get("url", ""),
            doi=entry.get("doi", ""),
            journal=journal,
            booktitle=booktitle,
            publisher=entry.get("publisher", ""),
            pages=entry.get("pages", ""),
            volume=entry.get("volume", ""),
            number=entry.get("number", ""),
            raw_entry=entry.copy(),
            raw_bibtex="",
            authors=authors_list,
            venue=venue,
        )
        bib_entry.arxiv_id = self._extract_arxiv_id(entry)
        return bib_entry

    def _extract_arxiv_id(self, entry: dict) -> str:
        for field in ("eprint", "arxiv", "url", "journal", "note"):
            val = entry.get(field, "")
            if not val:
                continue
            if field == "url":
                for pattern in self.ARXIV_URL_PATTERNS:
                    m = re.search(pattern, val, re.IGNORECASE)
                    if m:
                        return m.group(1)
                continue
            if field == "journal" and "arxiv" not in val.lower():
                continue
            for pattern in self.ARXIV_PATTERNS:
                m = re.search(pattern, val)
                if m:
                    return m.group(1)
        return ""
