#!/usr/bin/env python3
"""Build RefGuard benchmark JSONL from the curated V4 citation dataset."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ARXIV_LEGACY_FIXES = {
    "9705013": "cmp-lg/9705013",
    "9705013v1": "cmp-lg/9705013v1",
    "9803002": "cmp-lg/9803002",
    "9803002v1": "cmp-lg/9803002v1",
}


def has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_year(value: Any) -> int | None:
    text = clean_text(value)
    match = re.search(r"(1[6-9]|20)\d{2}", text)
    return int(match.group(0)) if match else None


def split_authors(value: Any) -> list[str]:
    """Normalize common bibliography author formats into a list of names.

    The source data mixes "A and B", Chinese comma-separated names,
    "Last, First, Coauthor" arXiv-style strings, and "Last F, Last F" styles.
    This keeps intentionally malformed hallucination author fields intact when
    there is not enough evidence to split them safely.
    """
    text = clean_text(value)
    if not text:
        return []

    text = text.replace("，", ",")
    text = re.sub(r"\s*&\s*", " and ", text)

    if re.search(r"\s+and\s+", text, flags=re.IGNORECASE):
        return [a.strip(" ,") for a in re.split(r"\s+and\s+", text, flags=re.IGNORECASE) if a.strip(" ,")]

    if has_cjk(text):
        return [a.strip() for a in re.split(r"[,;；、]", text) if a.strip()]

    if ";" in text:
        return [a.strip(" ,") for a in text.split(";") if a.strip(" ,")]

    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) <= 1:
        return [text]

    # Already comma-separated initials, e.g. "Esteva A, Kuprel B, Novoa RA".
    if all(re.search(r"\b[A-Z][A-Za-z.'-]*\s+[A-Z]{1,4}\.?$", p) for p in parts):
        return parts

    # arXiv-like export: "Vaswani, Ashish, Noam Shazeer, Niki Parmar".
    if len(parts) >= 3 and re.fullmatch(r"[A-Z][A-Za-z'`.-]+(?:\s+[A-Z][A-Za-z'`.-]+)*", parts[0]):
        first_author = f"{parts[1]} {parts[0]}".strip()
        return [first_author] + parts[2:]

    # Two-part "Last, First" name.
    if len(parts) == 2:
        return [f"{parts[1]} {parts[0]}".strip()]

    return parts


def split_raw_author_segment(value: str) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    text = re.sub(r",?\s+and\s+", ", ", text, flags=re.IGNORECASE)
    if has_cjk(text):
        return split_authors(text)
    return [a.strip(" ,") for a in text.split(",") if a.strip(" ,")]


def parse_citation_text(value: Any) -> dict[str, Any]:
    """Extract a best-effort title/authors/year from a raw citation string."""
    raw = clean_text(value)
    if not raw:
        return {}

    lower = raw.lower()
    markers = [
        ". arxiv",
        ". in ",
        ". proceedings",
        ". proc.",
        ". ieee",
        ". acm",
        ". nature",
        ". science",
        ". neurips",
        ". icml",
        ". iclr",
        ". cvpr",
        ". international journal",
        ". journal of",
        ". journal",
    ]
    cut = None
    for marker in markers:
        idx = lower.find(marker)
        if idx > 0 and (cut is None or idx < cut):
            cut = idx
    if cut is None:
        return {}
    prefix = raw[:cut] if cut is not None else raw

    if ". " not in prefix:
        return {}
    author_part, title = prefix.rsplit(". ", 1)
    title = title.strip(" .")
    if not title or len(title) < 4:
        return {}
    return {
        "authors": split_raw_author_segment(author_part),
        "title": title,
        "year": normalize_year(raw),
    }


def is_suspicious_parsed_title(title: str, authors: list[str]) -> bool:
    title = clean_text(title)
    if len(title) <= 3:
        return True
    if title in {"Qiao, W", "Zhu, T", "Zhang, M", "Chen and N", "Garcia and A", "Smith and A"}:
        return True
    if len(authors) == 1 and len(authors[0]) <= 2:
        return True
    return False


def infer_language(row: dict[str, Any]) -> str:
    value = clean_text(row.get("language") or row.get("lang"))
    if value:
        return value
    blob = " ".join(clean_text(row.get(k)) for k in ("title", "authors", "venue", "citation_text"))
    return "Chinese" if has_cjk(blob) else "English"


def infer_doc_type(row: dict[str, Any]) -> str:
    value = clean_text(row.get("doc_type"))
    if value:
        return value
    venue = clean_text(row.get("venue")).lower()
    if "arxiv" in venue or "preprint" in venue or "biorxiv" in venue:
        return "preprint"
    if "conference" in venue or "proceedings" in venue or "neurips" in venue or "iclr" in venue:
        return "conference"
    if "press" in venue or "book" in venue:
        return "book"
    if "thesis" in venue:
        return "thesis"
    if "report" in venue:
        return "technical_report"
    return "journal"


def normalize_subset(row: dict[str, Any]) -> str:
    subset = clean_text(row.get("subset"))
    if subset:
        return subset
    label = clean_text(row.get("label"))
    return "hallucination_synthetic" if label == "hallucination" else "real_public_metadata"


def normalize_verification_status(row: dict[str, Any]) -> str:
    status = clean_text(row.get("verification_status"))
    if status:
        return status
    label = clean_text(row.get("label"))
    return "hallucination_verified" if label == "hallucination" else "verifiable_via_public_metadata"


def normalize_arxiv_id(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    text = re.sub(r"^arXiv:", "", text, flags=re.IGNORECASE)
    return ARXIV_LEGACY_FIXES.get(text, text)


def clean_url(value: Any) -> str:
    url = clean_text(value)
    if not url or "PLACEHOLDER" in url.upper():
        return ""
    return url


def make_raw_citation(row: dict[str, Any], authors: list[str], year: int | None) -> str:
    raw = clean_text(row.get("citation_text"))
    if raw:
        return raw
    pieces = []
    if authors:
        pieces.append(", ".join(authors))
    title = clean_text(row.get("title"))
    if title:
        pieces.append(title)
    venue = clean_text(row.get("venue"))
    if venue:
        pieces.append(venue)
    if year:
        pieces.append(str(year))
    doi = clean_text(row.get("doi"))
    arxiv_id = normalize_arxiv_id(row.get("arxiv_id"))
    if doi:
        pieces.append(f"doi: {doi}")
    elif arxiv_id:
        pieces.append(f"arXiv:{arxiv_id}")
    return ". ".join(pieces) + ("." if pieces else "")


def convert_record(row: dict[str, Any]) -> dict[str, Any]:
    label = clean_text(row.get("label"))
    authors = split_authors(row.get("authors"))
    title = clean_text(row.get("title"))
    year = normalize_year(row.get("year"))
    citation_parse = parse_citation_text(row.get("citation_text"))
    if citation_parse and (
        clean_text(row.get("subset")) == "hallucination_gptzero"
        or is_suspicious_parsed_title(title, authors)
    ):
        authors = citation_parse.get("authors") or authors
        title = citation_parse.get("title") or title
        year = citation_parse.get("year") or year
    arxiv_id = normalize_arxiv_id(row.get("arxiv_id"))
    source_url = clean_url(row.get("source_paper_url"))
    reference_url = clean_url(row.get("url")) or source_url or None
    doi = clean_text(row.get("doi")) or None
    hallucination_type = clean_text(row.get("hallucination_type")) or None
    verification_status = normalize_verification_status(row)
    verifiable = row.get("verifiable")
    if verifiable is None:
        verifiable = True

    notes = []
    if hallucination_type:
        notes.append(f"幻觉类型：{hallucination_type}")
    notes.append(f"标注状态：{verification_status}")
    notes.append(f"可核验：{str(bool(verifiable)).lower()}")
    note = clean_text(row.get("note"))
    if note:
        notes.append(note)

    return {
        "paper_id": clean_text(row.get("id")),
        "paper_title": clean_text(row.get("source_paper")),
        "paper_url": source_url,
        "reference": {
                "raw": make_raw_citation(row, authors, year),
                "parsed": {
                "title": title,
                "authors": authors,
                "year": year,
                "venue": clean_text(row.get("venue")),
                "doi": doi,
                "arxiv": arxiv_id,
                "url": reference_url,
            },
        },
        "ground_truth": {
            "is_hallucinated": label == "hallucination",
            "label": label,
            "notes": "；".join(notes),
        },
        "source": "refguard_citebench_v1",
        "meta": {
            "subset": normalize_subset(row),
            "language": infer_language(row),
            "doc_type": infer_doc_type(row),
            "discipline": clean_text(row.get("discipline")) or None,
            "hallucination_type": hallucination_type,
            "verifiable": bool(verifiable),
            "verification_status": verification_status,
        },
    }


def validate(
    records: list[dict[str, Any]],
    *,
    source_total: int,
    excluded: list[dict[str, Any]],
) -> dict[str, Any]:
    ids = [r["paper_id"] for r in records]
    required_missing: dict[str, int] = {}
    checks = {
        "paper_id": lambda r: r["paper_id"],
        "reference.raw": lambda r: r["reference"]["raw"],
        "reference.parsed.title": lambda r: r["reference"]["parsed"]["title"],
        "reference.parsed.authors": lambda r: r["reference"]["parsed"]["authors"],
        "reference.parsed.year": lambda r: r["reference"]["parsed"]["year"],
        "ground_truth.label": lambda r: r["ground_truth"]["label"],
        "meta.language": lambda r: r["meta"]["language"],
        "meta.doc_type": lambda r: r["meta"]["doc_type"],
        "meta.verification_status": lambda r: r["meta"]["verification_status"],
    }
    for name, getter in checks.items():
        required_missing[name] = sum(1 for r in records if not getter(r))
    return {
        "source_total": source_total,
        "total": len(records),
        "real": sum(1 for r in records if r["ground_truth"]["label"] == "real"),
        "hallucination": sum(1 for r in records if r["ground_truth"]["label"] == "hallucination"),
        "labels": dict(Counter(r["ground_truth"]["label"] for r in records)),
        "languages": dict(Counter(r["meta"]["language"] for r in records)),
        "doc_types": dict(Counter(r["meta"]["doc_type"] for r in records)),
        "subsets": dict(Counter(r["meta"]["subset"] for r in records)),
        "disciplines": dict(Counter(r["meta"]["discipline"] or "unknown" for r in records)),
        "verification_status": dict(Counter(r["meta"]["verification_status"] for r in records)),
        "excluded": {
            "total": len(excluded),
            "by_verification_status": {
                status: sum(1 for r in excluded if clean_text(r.get("verification_status")) == status)
                for status in sorted({clean_text(r.get("verification_status")) for r in excluded})
            },
        },
        "duplicate_ids": len(ids) - len(set(ids)),
        "placeholder_urls": sum(1 for r in records if "PLACEHOLDER" in json.dumps(r, ensure_ascii=False).upper()),
        "missing": required_missing,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build data/refguard_input.jsonl from citation_dataset_final_v4.json")
    parser.add_argument("--input", default="data/citation_dataset_final_v4.json")
    parser.add_argument("--output", default="data/refguard_input.jsonl")
    parser.add_argument("--summary", default="data/refguard_input_summary.json")
    parser.add_argument(
        "--exclude-verification-status",
        action="append",
        default=[],
        help="Exclude records with this verification_status. Can be repeated.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    summary_path = Path(args.summary)

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    # Public releases wrap records with a top-level ethics/licensing metadata
    # object; internal curated files remain a plain list for compatibility.
    rows = payload.get("records", []) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("input must be a record list or an object containing a 'records' list")
    excluded_statuses = {clean_text(s) for s in args.exclude_verification_status if clean_text(s)}
    included_rows = [row for row in rows if clean_text(row.get("verification_status")) not in excluded_statuses]
    excluded_rows = [row for row in rows if clean_text(row.get("verification_status")) in excluded_statuses]
    records = [convert_record(row) for row in included_rows]

    output_path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) for record in records) + "\n",
        encoding="utf-8",
    )
    summary = validate(records, source_total=len(rows), excluded=excluded_rows)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
