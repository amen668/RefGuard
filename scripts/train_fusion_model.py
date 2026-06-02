#!/usr/bin/env python3
"""在 dev 划分上训练融合模型权重，修正默认启发式权重的不可分问题。

背景：默认 `DEFAULT_WEIGHTS`/`DEFAULT_BIAS=1.0` 让所有候选的匹配概率被压在
0.73~0.86 窄带，真实与幻觉重叠、无法用阈值分开（全量评测 P=0.49）。本脚本用
dev(500) 的「最佳候选特征向量 → 记录级标签」训练一个 logistic 回归，权重直接落在
`FusionModel.predict_proba` 的 logit 空间，写出 `fusion_model.json` 即插即用。

标签语义：real 记录的最佳候选应判为真匹配(1)，hallucination 记录无真匹配，其
最佳候选作为难负例(0)。最佳候选按 title_sim（次序 doi_match）选，与被评测的
融合模型输出解耦，避免循环。

用法：
    python scripts/train_fusion_model.py            # 全量 dev，写 fusion_models/
    python scripts/train_fusion_model.py --limit 50 # 小样本冒烟
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from eval.benchmark_utils import record_to_bibtex  # noqa: E402
from refguard.parsers.bib_parser import BibParser  # noqa: E402
from refguard.retrieval.candidate_generator import CandidateGenerator  # noqa: E402
from refguard.fusion.feature_builder import FeatureBuilder, FEATURE_NAMES  # noqa: E402
from refguard.core import setup_logging  # noqa: E402


def load_dev_ids(final_path: Path) -> set[str]:
    data = json.loads(final_path.read_text(encoding="utf-8"))
    return {r["id"] for r in data if r.get("split") == "dev"}


def best_candidate_features(entry, candidates):
    """取 title_sim（次序 doi_match）最高的候选特征向量。"""
    feats = [
        FeatureBuilder.build(entry, h, rank=i + 1, total_candidates=len(candidates))
        for i, h in enumerate(candidates)
    ]
    return max(feats, key=lambda f: (f.title_sim, f.doi_match))


def train_logreg(X: np.ndarray, y: np.ndarray, l2: float = 1.0,
                 lr: float = 0.2, iters: int = 5000) -> tuple[np.ndarray, float]:
    """纯 numpy 梯度下降 logistic 回归（特征已在 [0,1]，无需标准化）。"""
    n, d = X.shape
    w = np.zeros(d)
    b = 0.0
    for _ in range(iters):
        z = X @ w + b
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
        grad_w = X.T @ (p - y) / n + l2 * w / n
        grad_b = float(np.sum(p - y) / n)
        w -= lr * grad_w
        b -= lr * grad_b
    return w, b


def main() -> None:
    ap = argparse.ArgumentParser(description="dev 划分训练融合模型权重")
    ap.add_argument("--final", default="data/citation_dataset_final_v4.json")
    ap.add_argument("--input", default="data/refguard_input.jsonl")
    ap.add_argument("--out", default="fusion_models", help="写 fusion_model.json 的目录")
    ap.add_argument("--sources", default="crossref,openalex,arxiv,dblp,semanticscholar,doicn")
    ap.add_argument("--limit", type=int, default=None, help="只用前 N 条 dev（冒烟）")
    ap.add_argument("--l2", type=float, default=1.0)
    ap.add_argument("--mask-presence", action="store_true",
                    help="训练前置零 has_doi/has_arxiv_id 两个『存在性』特征，"
                         "避免模型学到『有DOI字符串=真』的数据构造捷径")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass
    setup_logging()

    dev_ids = load_dev_ids(Path(args.final))
    rows = []
    for line in Path(args.input).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("paper_id") in dev_ids:
            rows.append(r)
    if args.limit:
        rows = rows[: args.limit]
    print(f"dev 记录 {len(rows)} 条，开始检索取特征…", flush=True)

    gen = CandidateGenerator(sources=[s.strip() for s in args.sources.split(",")])
    parser = BibParser()
    X, y, skipped = [], [], 0
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cache = out / "dev_features.jsonl"
    fcache = cache.open("w", encoding="utf-8")
    for i, r in enumerate(rows):
        label = (r.get("ground_truth") or {}).get("label", "hallucination")
        bib = record_to_bibtex(r, entry_key=r.get("paper_id", "ref").replace("-", "_"))
        entries = parser.parse_content(bib)
        if not entries:
            skipped += 1
            continue
        cands, _ = gen.generate(entries[0])
        if not cands:
            # real 无候选无法作正例；hallucination 无候选是易负例，决策引擎已能处理。两者都不进训练。
            skipped += 1
        else:
            f = best_candidate_features(entries[0], cands)
            vec = f.to_vector()
            X.append(vec)
            y.append(1.0 if label == "real" else 0.0)
            fcache.write(json.dumps({"id": r.get("paper_id"), "label": label, "x": vec}) + "\n")
        if (i + 1) % 20 == 0 or (i + 1) == len(rows):
            print(f"  [{i + 1}/{len(rows)}] 已取特征 {len(X)} 跳过 {skipped}", flush=True)
            fcache.flush()
    fcache.close()

    if len(X) < 20:
        print(f"训练样本太少（{len(X)}），中止。", file=sys.stderr)
        sys.exit(1)

    X = np.array(X, dtype=np.float64)
    y = np.array(y, dtype=np.float64)
    if args.mask_presence:
        # has_doi=9, has_arxiv_id=10：置零使其学得权重必为 0，迫使模型依赖
        # doi_match 等真实核验信号而非字段存在性捷径。
        idx_doi = FEATURE_NAMES.index("has_doi")
        idx_arx = FEATURE_NAMES.index("has_arxiv_id")
        X[:, idx_doi] = 0.0
        X[:, idx_arx] = 0.0
        print(f"已屏蔽存在性特征 has_doi/has_arxiv_id（列 {idx_doi}/{idx_arx}）", flush=True)
    w, b = train_logreg(X, y, l2=args.l2)

    # 训练集内分离度自检。
    p = 1.0 / (1.0 + np.exp(-(X @ w + b)))
    pr_real = p[y == 1.0]
    pr_hal = p[y == 0.0]
    print(f"\n训练样本 {len(X)}（real {int(y.sum())} / halluc {int((1 - y).sum())}）")
    print(f"训练内 real  prob 中位 {np.median(pr_real):.3f}  p05 {np.percentile(pr_real,5):.3f}")
    print(f"训练内 halluc prob 中位 {np.median(pr_hal):.3f}  p95 {np.percentile(pr_hal,95):.3f}")
    print("阈值扫描（pred_halluc = prob < thr）：")
    for thr in (0.7, 0.6, 0.5, 0.4, 0.3):
        tp = int(np.sum((y == 0) & (p < thr))); fp = int(np.sum((y == 1) & (p < thr)))
        fn = int(np.sum((y == 0) & (p >= thr))); tn = int(np.sum((y == 1) & (p >= thr)))
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * pr * rc / (pr + rc) if pr + rc else 0.0
        print(f"  thr={thr:.2f}  P={pr:.3f} R={rc:.3f} F1={f1:.3f}")

    model = {"weights": w.tolist(), "bias": float(b),
             "feature_names": FEATURE_NAMES, "trained_on": "dev",
             "n_train": len(X)}
    (out / "fusion_model.json").write_text(
        json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n写入 {out / 'fusion_model.json'}")
    print("权重：", dict(zip(FEATURE_NAMES, [round(x, 3) for x in w.tolist()])))
    print(f"bias：{b:.3f}")


if __name__ == "__main__":
    main()
