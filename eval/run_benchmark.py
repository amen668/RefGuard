#!/usr/bin/env python3
"""
Run RefGuard on refguard_input.jsonl benchmark and compute metrics.

Usage:
  python eval/run_benchmark.py --input /path/to/refguard_input.jsonl --out ./eval_report
  python eval/run_benchmark.py --input refguard_input.jsonl --profile strict --limit 10

Input: refguard_input.jsonl (each line: paper_id, reference {raw, parsed}, ground_truth {is_hallucinated, notes}).
Output: RefGuard predicts is_match per reference; we treat is_match=False as "hallucination predicted".
Metrics: accuracy, precision, recall, F1 for hallucination class; confusion matrix.
"""
import argparse
import json
import sys
from pathlib import Path

# Add project root for refguard
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.benchmark_utils import record_to_bibtex


def main() -> None:
    parser = argparse.ArgumentParser(description="RefGuard benchmark on refguard_input.jsonl")
    parser.add_argument("--input", "-i", default="data/refguard_input.jsonl",
                        help="Path to refguard_input.jsonl (default: data/refguard_input.jsonl)")
    parser.add_argument("--out", "-o", default="./eval_report", help="Output directory for report")
    parser.add_argument("--profile", "-p", default="balanced", choices=["strict", "balanced", "lenient"])
    parser.add_argument("--limit", "-n", type=int, default=None, help="Max number of records to run (default: all)")
    parser.add_argument("--sources", "-s", default="crossref,openalex,arxiv,dblp,semanticscholar",
                        help="Comma-separated retrieval sources")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    records = []
    with open(input_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))

    if args.limit:
        records = records[: args.limit]

    if not records:
        print("No records to evaluate.", file=sys.stderr)
        sys.exit(1)

    from refguard.services import VerificationService
    from refguard.core import setup_logging
    setup_logging()

    sources = [s.strip() for s in args.sources.split(",")]
    svc = VerificationService(sources=sources, profile_name=args.profile)

    results = []
    for i, rec in enumerate(records):
        entry_key = rec.get("paper_id", "ref") + f"_{i}"
        bib_content = record_to_bibtex(rec, entry_key=entry_key)
        report_gen = svc.verify_bib(bib_content, check_duplicates=False)
        entry_reports = report_gen.entry_reports
        if not entry_reports:
            is_match = False
            status = "error"
            prob = 0.0
        else:
            comp = entry_reports[0].comparison
            is_match = comp.is_match if comp else False
            prob = comp.match_probability if comp else 0.0
            if comp and (comp.issues or []) and "author_mismatch" in comp.issues:
                status = "error"
            else:
                status = "verified" if is_match else ("warning" if prob >= 0.3 else "error")
        gt_hallucinated = (rec.get("ground_truth") or {}).get("is_hallucinated", True)
        pred_hallucinated = not is_match  # RefGuard no match -> we predict hallucination
        results.append({
            "index": i,
            "paper_id": rec.get("paper_id"),
            "ground_truth_hallucinated": gt_hallucinated,
            "predicted_hallucinated": pred_hallucinated,
            "refguard_status": status,
            "refguard_is_match": is_match,
            "match_probability": prob,
            "correct": gt_hallucinated == pred_hallucinated,
        })

    # Metrics: positive class = hallucination
    tp = sum(1 for r in results if r["ground_truth_hallucinated"] and r["predicted_hallucinated"])
    tn = sum(1 for r in results if not r["ground_truth_hallucinated"] and not r["predicted_hallucinated"])
    fp = sum(1 for r in results if not r["ground_truth_hallucinated"] and r["predicted_hallucinated"])
    fn = sum(1 for r in results if r["ground_truth_hallucinated"] and not r["predicted_hallucinated"])

    n = len(results)
    accuracy = (tp + tn) / n if n else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    summary = {
        "total": n,
        "accuracy": round(accuracy, 4),
        "precision_hallucination": round(precision, 4),
        "recall_hallucination": round(recall, 4),
        "f1_hallucination": round(f1, 4),
        "confusion": {"TP": tp, "TN": tn, "FP": fp, "FN": fn},
        "profile": args.profile,
        "sources": sources,
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    report_json = {
        "summary": summary,
        "results": results,
    }
    with open(out_dir / "eval_report.json", "w", encoding="utf-8") as f:
        json.dump(report_json, f, ensure_ascii=False, indent=2)

    report_md = [
        "# RefGuard Benchmark Report",
        "",
        f"**Input:** `{input_path.name}` | **Profile:** {args.profile} | **N:** {n}",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|--------|--------|",
        f"| Accuracy | {accuracy:.4f} |",
        f"| Precision (hallucination) | {precision:.4f} |",
        f"| Recall (hallucination) | {recall:.4f} |",
        f"| F1 (hallucination) | {f1:.4f} |",
        "",
        "## Confusion Matrix (positive = hallucination)",
        "",
        "| | Predicted Hallucination | Predicted Not Hallucination |",
        "|--|--------------------------|-----------------------------|",
        f"| **GT Hallucination** | TP = {tp} | FN = {fn} |",
        f"| **GT Not Hallucination** | FP = {fp} | TN = {tn} |",
        "",
    ]
    with open(out_dir / "eval_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report_md))

    print(f"Total: {n} | Accuracy: {accuracy:.4f} | P: {precision:.4f} R: {recall:.4f} F1: {f1:.4f}")
    print(f"Report written to {out_dir}/eval_report.json and {out_dir}/eval_report.md")


if __name__ == "__main__":
    main()
