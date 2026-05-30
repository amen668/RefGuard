#!/usr/bin/env python3
"""将基准数据记录转换为 RefGuard 可核验的最小 BibTeX。"""
def _escape_bibtex(s: str) -> str:
    """转义 BibTeX 字段值中的特殊字符。"""
    if not s:
        return ""
    s = s.replace("\\", "\\\\")
    return s.replace("{", "{{").replace("}", "}}")


def record_to_bibtex(record: dict, entry_key: str = "ref") -> str:
    """根据一条 JSONL 记录构造最小 BibTeX 条目。"""
    ref = record.get("reference") or {}
    parsed = ref.get("parsed") or {}
    title = (parsed.get("title") or "").strip() or "Unknown"
    year = parsed.get("year")
    if year is not None:
        year = str(int(year))
    else:
        year = ""
    doi = parsed.get("doi")
    doi = (str(doi).strip() if doi is not None else "")
    arxiv = parsed.get("arxiv")
    arxiv = (str(arxiv).strip() if arxiv is not None else "")
    authors_list = parsed.get("authors")
    if isinstance(authors_list, list):
        author = " and ".join(str(a).strip() for a in authors_list if a)
    else:
        author = (parsed.get("author") or "").strip() or "Unknown"

    title = _escape_bibtex(title)
    author = _escape_bibtex(author)

    lines = [f"@article{{{entry_key},"]
    lines.append(f"  title = {{{title}}},")
    lines.append(f"  author = {{{author}}},")
    if year:
        lines.append(f"  year = {{{year}}},")
    if doi:
        lines.append(f"  doi = {{{doi}}},")
    if arxiv:
        lines.append(f"  note = {{arXiv:{arxiv}}},")
    if not lines[-1].strip().endswith("}"):
        lines[-1] = lines[-1].rstrip(",")
    lines.append("}")

    return "\n".join(lines)
