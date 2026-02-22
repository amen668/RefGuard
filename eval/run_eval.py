#!/usr/bin/env python3
"""Run evaluation: load labeled_matches.jsonl, compute metrics (stub)."""
import json
import sys
from pathlib import Path

def main() -> None:
    data_path = Path(__file__).parent / "labeled_matches_example.jsonl"
    if not data_path.exists():
        print("No labeled_matches_example.jsonl; run build_dataset.py or add your labeled_matches.jsonl")
        return
    labels = []
    with open(data_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            labels.append(obj.get("label", 0))
    if not labels:
        print("No labels found")
        return
    n = len(labels)
    pos = sum(labels)
    print(f"Total: {n}, Positive: {pos}, Negative: {n - pos}")
    print("(Full metrics: Precision/Recall/F1, ROC-AUC, Brier in eval_report.md)")

if __name__ == "__main__":
    main()
