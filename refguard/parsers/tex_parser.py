"""LaTeX parser for citation extraction."""
import re
from pathlib import Path
from typing import Optional

from refguard.models import CitationContext


class TexParser:
    """Extract \\cite keys and context from .tex files."""

    CITE_REGEX = re.compile(
        r"\\(cite[a-z]*)\*?\s*(?:\[[^\]]*\])?\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        self.citations: dict[str, list[CitationContext]] = {}
        self.all_keys: set[str] = set()
        self.lines: list[str] = []
        self.content: str = ""
        self.current_filepath: Optional[str] = None

    def parse_file(self, filepath: str) -> dict[str, list[CitationContext]]:
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"TeX file not found: {filepath}")
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        self.current_filepath = filepath
        return self.parse_content(content)

    def parse_content(self, content: str) -> dict[str, list[CitationContext]]:
        self.content = content
        self.lines = content.split("\n")
        self.citations = {}
        self.all_keys = set()

        for line_num, line in enumerate(self.lines, 1):
            if line.strip().startswith("%"):
                continue
            line_no_comment = re.sub(r"(?<!\\)%.*$", "", line)
            for match in self.CITE_REGEX.finditer(line_no_comment):
                command = match.group(1)
                keys_str = match.group(2)
                for key in [k.strip() for k in keys_str.split(",") if k.strip()]:
                    self.all_keys.add(key)
                    ctx = self._extract_context(line_num)
                    citation = CitationContext(
                        key=key,
                        line_number=line_num,
                        command=f"\\{command}",
                        context_before=ctx["before"],
                        context_after=ctx["after"],
                        full_context=ctx["full"],
                        raw_line=line,
                        file_path=self.current_filepath,
                    )
                    if key not in self.citations:
                        self.citations[key] = []
                    self.citations[key].append(citation)
        return self.citations

    def _extract_context(self, line_num: int, context_sentences: int = 2) -> dict:
        start_line = max(0, line_num - 10)
        end_line = min(len(self.lines), line_num + 10)
        before_lines = self.lines[start_line : line_num - 1]
        after_lines = self.lines[line_num:end_line]
        current_clean = self._clean_text(self.lines[line_num - 1])
        before_clean = self._clean_text(" ".join(before_lines))
        after_clean = self._clean_text(" ".join(after_lines))

        def split_sentences(text: str) -> list[str]:
            return re.split(r"(?<=[.!?])\s+", text)

        before_sentences = split_sentences(before_clean)
        after_sentences = split_sentences(after_clean)
        context_before = " ".join(before_sentences[-context_sentences:]) if before_sentences else ""
        context_after = " ".join(after_sentences[:context_sentences]) if after_sentences else ""
        full_context = f"{context_before} {current_clean} {context_after}".strip()
        return {"before": context_before, "after": context_after, "full": full_context}

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])*\s*", " ", text)
        text = re.sub(r"[{}]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def get_all_cited_keys(self) -> set[str]:
        return self.all_keys.copy()

    def get_citation_contexts(self, key: str) -> list[CitationContext]:
        return self.citations.get(key, [])
