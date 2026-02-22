#!/usr/bin/env python3
"""Build labeled_matches.jsonl from bib entries and retrieval dump (stub for repro)."""
import json
import sys
from pathlib import Path

# Add parent for refguard
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main() -> None:
    out = Path(__file__).parent / "labeled_matches.jsonl"
    # Example: append one line
    example = {
        "bib_entry": {"key": "sample", "title": "Sample Paper", "year": "2022", "doi": "10.0000/sample"},
        "candidates": [{"source": "crossref", "fetched_title": "Sample Paper", "fetched_doi": "10.0000/sample"}],
        "label": 1,
        "meta": {"noise": "clean"},
    }
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(example, ensure_ascii=False) + "\n")
    print(f"Appended example to {out}")

if __name__ == "__main__":
    main()
