#!/usr/bin/env python3
"""运行 RefGuard 基准评测并计算幻觉文献检测指标。"""
import argparse
import json
import sys
from pathlib import Path

# 将项目根目录加入导入路径。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.benchmark_utils import record_to_bibtex


def main() -> None:
    parser = argparse.ArgumentParser(description="在 refguard_input.jsonl 上运行 RefGuard 基准评测")
    parser.add_argument("--input", "-i", default="data/refguard_input.jsonl",
                        help="基准数据路径，默认 data/refguard_input.jsonl")
    parser.add_argument("--out", "-o", default="./eval_report", help="评测报告输出目录")
    parser.add_argument("--profile", "-p", default="balanced",
                        choices=["strict", "balanced", "lenient", "adaptive"])
    parser.add_argument("--limit", "-n", type=int, default=None, help="最多评测多少条，默认全部")
    parser.add_argument("--sources", "-s", default="crossref,openalex,arxiv,dblp,semanticscholar,doicn",
                        help="逗号分隔的数据源名称")
    parser.add_argument("--shuffle", action="store_true",
                        help="抽样前先打乱（配合 --limit 取代表性样本，避免按采集顺序取到单一切片）")
    parser.add_argument("--seed", type=int, default=20260601, help="--shuffle 的随机种子，保证可复现")
    parser.add_argument("--model-dir", default=None,
                        help="加载训练好的 fusion_model.json 的目录；缺省用启发式默认权重")
    parser.add_argument("--split", default=None, choices=["dev", "test"],
                        help="只评测该划分（需配合 --split-source 读取 split 字段）")
    parser.add_argument("--split-source", default="data/citation_dataset_final_v4.json",
                        help="带 split 字段的源数据集，用于 --split 过滤")
    parser.add_argument("--resume", action="store_true",
                        help="从 <out>/eval_partial.json 断点续跑，跳过已完成的前 N 条（长跑被杀不丢进度）")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误：找不到输入文件：{input_path}", file=sys.stderr)
        sys.exit(1)

    records = []
    with open(input_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))

    if args.split:
        split_src = Path(args.split_source)
        if not split_src.exists():
            print(f"错误：--split 需要 --split-source，但找不到 {split_src}", file=sys.stderr)
            sys.exit(1)
        split_data = json.loads(split_src.read_text(encoding="utf-8"))
        keep = {r["id"] for r in split_data if r.get("split") == args.split}
        records = [r for r in records if r.get("paper_id") in keep]
        print(f"按 split={args.split} 过滤后剩 {len(records)} 条", file=sys.stderr)

    if args.shuffle:
        import random
        random.Random(args.seed).shuffle(records)

    if args.limit:
        records = records[: args.limit]

    if not records:
        print("没有可评测的记录。", file=sys.stderr)
        sys.exit(1)

    from refguard.services import VerificationService
    from refguard.core import setup_logging
    setup_logging()

    # 行缓冲：重定向到文件时 tail -f 能实时看到逐条进度。
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass

    sources = [s.strip() for s in args.sources.split(",")]
    svc = VerificationService(sources=sources, profile_name=args.profile, model_dir=args.model_dir)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    n_total = len(records)
    results = []
    resume_from = 0
    if args.resume:
        partial_path = out_dir / "eval_partial.json"
        if partial_path.exists():
            results = json.loads(partial_path.read_text(encoding="utf-8"))
            resume_from = len(results)
            print(f"断点续跑：已完成 {resume_from} 条，从第 {resume_from + 1} 条继续", flush=True)
    print(f"开始评测 {n_total} 条 | profile={args.profile} | sources={','.join(sources)}", flush=True)
    for i, rec in enumerate(records):
        if i < resume_from:
            continue
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
        pred_hallucinated = not is_match
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
        if (i + 1) % 10 == 0 or (i + 1) == n_total:
            ncorrect = sum(1 for r in results if r["correct"])
            print(f"  [{i + 1}/{n_total}] 累计正确 {ncorrect}/{i + 1} "
                  f"(running acc {ncorrect / (i + 1):.3f})", flush=True)
            # 断点保护：定期落盘已完成的逐条结果，崩溃不全丢。
            with open(out_dir / "eval_partial.json", "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False)

    # 正类定义为幻觉文献。
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

    report_json = {
        "summary": summary,
        "results": results,
    }
    with open(out_dir / "eval_report.json", "w", encoding="utf-8") as f:
        json.dump(report_json, f, ensure_ascii=False, indent=2)

    report_md = [
        "# RefGuard 基准评测报告",
        "",
        f"**Input:** `{input_path.name}` | **Profile:** {args.profile} | **N:** {n}",
        "",
        "## 指标",
        "",
        "| Metric | Value |",
        "|--------|--------|",
        f"| Accuracy | {accuracy:.4f} |",
        f"| Precision (hallucination) | {precision:.4f} |",
        f"| Recall (hallucination) | {recall:.4f} |",
        f"| F1 (hallucination) | {f1:.4f} |",
        "",
        "## 混淆矩阵（正类 = 幻觉文献）",
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
    print(f"报告已写入 {out_dir}/eval_report.json 和 {out_dir}/eval_report.md")


if __name__ == "__main__":
    main()
