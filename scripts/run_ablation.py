#!/usr/bin/env python3
"""一次检索全源、缓存特征，离线导出单源对比/特征消融/效率表（表3/4/8）。

对测试子集每条只做一次全 6 源检索（与主评测同等成本），把每个候选的特征向量
与来源缓存到本地；随后从缓存离线计算各变体指标，避免按源重复跑 API。

阶段1（打 API，可断点续）：检索 + 取特征 → fusion_models_nodoi6/ablation_cache.jsonl
阶段2（离线）：从缓存导出
  - 表3 单源检索对比（每个数据源单独 + 全融合）
  - 表4 特征消融（每个特征子集在开发集重新训练并选阈值）
  - 表8 运行效率（每条检索耗时统计 + 二次缓存命中加速）

用法：
    python scripts/run_ablation.py --limit 500           # 跑 500 子集
    python scripts/run_ablation.py --offline-only        # 仅用已有缓存出表
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from eval.benchmark_utils import record_to_bibtex
from refguard.config import get_profile
from refguard.core import setup_logging
from refguard.fusion.decision_engine import adaptive_threshold
from refguard.fusion.feature_builder import FEATURE_NAMES, FeatureBuilder
from refguard.fusion.fusion_model import FusionModel
from refguard.parsers.bib_parser import BibParser
from refguard.retrieval.candidate_generator import CandidateGenerator

IDX = {n: i for i, n in enumerate(FEATURE_NAMES)}


def load_test_ids(final_path: Path) -> set[str]:
    data = json.loads(final_path.read_text(encoding="utf-8"))
    return {r["id"] for r in data if r.get("split") == "test"}


# ---------- 阶段1：检索 + 缓存 ----------
def build_cache(args, cache_path: Path):
    setup_logging()
    test_ids = load_test_ids(Path(args.final))
    rows = []
    for line in Path(args.input).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("paper_id") in test_ids:
            rows.append(r)
    import random
    random.Random(args.seed).shuffle(rows)
    if args.limit:
        rows = rows[: args.limit]

    done = set()
    if cache_path.exists():
        for line in cache_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)["id"])
    print(f"测试子集 {len(rows)} 条，已缓存 {len(done)} 条，续跑剩余", flush=True)

    gen = CandidateGenerator(sources=[s.strip() for s in args.sources.split(",")])
    parser = BibParser()
    fcache = cache_path.open("a", encoding="utf-8")
    for i, r in enumerate(rows):
        pid = r.get("paper_id")
        if pid in done:
            continue
        label = (r.get("ground_truth") or {}).get("label", "hallucination")
        bib = record_to_bibtex(r, entry_key=(pid or "ref").replace("-", "_"))
        entries = parser.parse_content(bib)
        if not entries:
            continue
        entry = entries[0]
        t0 = time.monotonic()
        cands, _ = gen.generate(entry)
        elapsed = time.monotonic() - t0
        hits = []
        for j, h in enumerate(cands):
            f = FeatureBuilder.build(entry, h, rank=j + 1, total_candidates=len(cands))
            hits.append({"source": h.source, "method": h.retrieval_method, "fv": f.to_vector()})
        fcache.write(json.dumps({
            "id": pid, "label": label, "entry_type": entry.entry_type,
            "elapsed": round(elapsed, 3), "n_cands": len(cands), "hits": hits,
        }) + "\n")
        if (i + 1) % 20 == 0:
            print(f"  [{i + 1}/{len(rows)}] 已处理", flush=True)
            fcache.flush()
    fcache.close()
    print("阶段1 缓存完成", flush=True)


# ---------- 阶段2：离线导出 ----------
def _confusion(preds, labels):
    tp = sum(1 for p, y in zip(preds, labels) if y == 0 and p)   # y==0 幻觉=正类
    tn = sum(1 for p, y in zip(preds, labels) if y == 1 and not p)
    fp = sum(1 for p, y in zip(preds, labels) if y == 1 and p)
    fn = sum(1 for p, y in zip(preds, labels) if y == 0 and not p)
    return tp, tn, fp, fn


def _metrics(tp, tn, fp, fn):
    n = tp + tn + fp + fn
    acc = (tp + tn) / n if n else 0
    pr = tp / (tp + fp) if tp + fp else 0
    rc = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * pr * rc / (pr + rc) if pr + rc else 0
    fpr = fp / (fp + tn) if fp + tn else 0
    return acc, pr, rc, f1, fpr


def _train_logreg(X: np.ndarray, y: np.ndarray, l2: float = 1.0,
                  lr: float = 0.2, iters: int = 5000):
    """与主模型相同的纯 NumPy L2 逻辑回归。"""
    n, d = X.shape
    w = np.zeros(d, dtype=np.float64)
    b = 0.0
    for _ in range(iters):
        z = X @ w + b
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
        w -= lr * (X.T @ (p - y) / n + l2 * w / n)
        b -= lr * float(np.sum(p - y) / n)
    return w, b


def _hallucination_metrics(preds: np.ndarray, real_labels: np.ndarray):
    """以幻觉为正类返回 TP/TN/FP/FN 及常用指标。"""
    tp = int(np.sum(preds & ~real_labels))
    tn = int(np.sum(~preds & real_labels))
    fp = int(np.sum(preds & real_labels))
    fn = int(np.sum(~preds & ~real_labels))
    return (tp, tn, fp, fn), _metrics(tp, tn, fp, fn)


def _choose_dev_threshold(match_probs: np.ndarray, real_labels: np.ndarray) -> float:
    """仅在开发集选 F1 最优阈值；并列时依次偏向召回、精确率和较小阈值。"""
    best = None
    for threshold in np.unique(np.r_[0.0, match_probs, 1.0]):
        preds = match_probs < threshold
        _, metrics = _hallucination_metrics(preds, real_labels)
        key = (metrics[3], metrics[2], metrics[1], -float(threshold))
        if best is None or key > best[0]:
            best = (key, float(threshold))
    return best[1]


def feature_ablation_rows(recs: list[dict], dev_rows: list[dict]) -> list[dict]:
    """按标准消融协议独立训练各子集，禁止沿用全模型偏置/阈值。

    开发集只用于拟合和选择阈值；冻结测试缓存只用于一次最终计分。无候选
    条目保持系统定义，直接判为幻觉。该协议避免旧实现中“置零特征但继续
    使用全特征模型偏置、阈值及未遮蔽决策规则”造成的机械重复结果。
    """
    x_dev_all = np.asarray([row["x"] for row in dev_rows], dtype=np.float64)
    dev_real = np.asarray([row["label"] == "real" for row in dev_rows], dtype=bool)
    test_real = np.asarray([row["label"] == "real" for row in recs], dtype=bool)
    combos = {
        "仅 DOI 匹配": ["doi_match", "id_match"],
        "DOI+标题": ["doi_match", "id_match", "title_sim"],
        "仅标题相似度": ["title_sim"],
        "仅作者相似度": ["author_sim"],
        "标题+作者+年份": ["title_sim", "author_sim", "year_match"],
        "全特征（同协议）": FEATURE_NAMES,
    }
    rows = []
    for name, keep in combos.items():
        cols = [IDX[item] for item in keep]
        x_dev = x_dev_all[:, cols]
        weights, bias = _train_logreg(x_dev, dev_real.astype(np.float64))
        dev_probs = 1.0 / (1.0 + np.exp(-np.clip(x_dev @ weights + bias, -30, 30)))
        threshold = _choose_dev_threshold(dev_probs, dev_real)

        test_probs = []
        for rec in recs:
            if not rec["hits"]:
                test_probs.append(-1.0)
                continue
            x_test = np.asarray(
                [[hit["fv"][col] for col in cols] for hit in rec["hits"]],
                dtype=np.float64,
            )
            probs = 1.0 / (1.0 + np.exp(-np.clip(x_test @ weights + bias, -30, 30)))
            test_probs.append(float(np.max(probs)))
        preds = np.asarray(test_probs) < threshold
        confusion, metrics = _hallucination_metrics(preds, test_real)
        rows.append({
            "name": name,
            "features": keep,
            "threshold": threshold,
            "confusion": confusion,
            "metrics": metrics,
        })
    return rows


def _decide_record(rec, model, profile, source_filter=None, feature_mask=None):
    """对一条缓存记录，按筛选/掩码计算 pred_halluc。"""
    hits = rec["hits"]
    if source_filter:
        hits = [h for h in hits if h["source"] == source_filter]
    if not hits:
        return True   # 无候选 → 判幻觉
    X = np.array([h["fv"] for h in hits], dtype=np.float64)
    if feature_mask is not None:
        X = X * feature_mask
    probs = model.predict_proba_matrix(X)
    best = int(np.argmax(probs))
    p1 = probs[best]
    fv = hits[best]["fv"]
    ex = {"doi_match": fv[IDX["doi_match"]], "author_sim": fv[IDX["author_sim"]],
          "title_sim": fv[IDX["title_sim"]], "year_match": fv[IDX["year_match"]]}

    class _E:  # 仿 entry，仅供 adaptive_threshold 读 entry_type
        entry_type = rec.get("entry_type", "article")

    class _C:  # 仿 candidate，仅供统计不同来源数
        def __init__(self, s): self.source = s
    cands = [_C(h["source"]) for h in hits]
    if profile.adaptive:
        thr = adaptive_threshold(profile, _E(), cands, ex)
    else:
        thr = profile.match_threshold
    is_match = p1 >= thr
    # 作者完全不匹配且无 DOI → 强制非匹配
    if ex["author_sim"] < 0.2 and ex["doi_match"] < 1.0:
        is_match = False
    return not is_match


def export_tables(cache_path: Path, model_dir: str, profile_name: str,
                  dev_features_path: Path, out: Path,
                  ablation_json: Path | None = None):
    recs = [json.loads(l) for l in cache_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    labels = [1 if r["label"] == "real" else 0 for r in recs]
    model = FusionModel(model_dir=model_dir)
    profile = get_profile(profile_name)
    sources = sorted({h["source"] for r in recs for h in r["hits"]})

    md = [f"# 表3/4/8 数据（子集 n={len(recs)}，profile={profile_name}）\n"]

    # 表3 单源对比（仅列单源；全融合性能见主结果表2，避免子集与全量两个数冲突）
    md.append("## 表3 单源检索性能对比\n")
    md.append(f"> 注：本表为 n={len(recs)} 测试子集。各源单独使用时性能；RefGuard 全融合性能"
              "见表2（全量 n=2037：召回 100%、精确率 98.7%、F1 0.994）。\n")
    md.append("| 数据源 | TP | FP | TN | FN | 召回率 | 精确率 | 准确率 | F1 | FPR |")
    md.append("|--|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    full_rc = None
    for s in sources:
        preds = [_decide_record(r, model, profile, source_filter=s) for r in recs]
        t = _confusion(preds, labels)
        m = _metrics(*t)
        md.append(f"| {s} 单源 | {t[0]} | {t[2]} | {t[1]} | {t[3]} | "
                  f"{m[2]*100:.1f}% | {m[1]*100:.1f}% | {m[0]*100:.1f}% | {m[3]:.3f} | {m[4]*100:.1f}% |")
    # 全融合参照行（引用表2 全量结果）
    md.append("| **RefGuard 全融合（见表2，n=2037）** | — | — | — | — | "
              "**100.0%** | **98.7%** | **99.7%** | **0.994** | 0.4% |")
    md.append("")

    # 表4 特征消融。旧实现仅在推理时置零特征，却沿用全模型偏置、固定阈值
    # 和未遮蔽的自适应规则，因而多个组合机械地得到相同结果。这里对每个
    # 子集在开发集独立重训并选阈值，测试子集只用于最终计分。
    dev_rows = [json.loads(l) for l in dev_features_path.read_text(encoding="utf-8").splitlines()
                if l.strip()]
    md.append("## 表4 特征消融\n")
    md.append("> 协议：各特征子集在冻结开发集独立训练逻辑回归并选择阈值，"
              "在同一冻结测试子集上评估；测试标签不参与拟合或选阈值。\n")
    md.append("| 特征组合 | 开发集阈值 | TP | FP | TN | FN | 召回率 | 精确率 | 准确率 | F1 |")
    md.append("|--|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    ablation_rows = feature_ablation_rows(recs, dev_rows)
    for row in ablation_rows:
        tp, tn, fp, fn = row["confusion"]
        m = row["metrics"]
        md.append(f"| {row['name']} | {row['threshold']:.6f} | {tp} | {fp} | {tn} | {fn} | "
                  f"{m[2]*100:.1f}% | {m[1]*100:.1f}% | {m[0]*100:.1f}% | {m[3]:.3f} |")
    md.append("")

    # 表8 运行效率
    times = [r["elapsed"] for r in recs if "elapsed" in r]
    if times:
        md.append("## 表8 运行效率统计\n")
        md.append("| 指标 | 数值 |")
        md.append("|--|--:|")
        md.append(f"| 样本数 | {len(times)} |")
        md.append(f"| 平均处理时间 | {np.mean(times):.2f} 秒/条 |")
        md.append(f"| 中位处理时间 | {np.median(times):.2f} 秒/条 |")
        md.append(f"| 最短/最长 | {np.min(times):.2f} / {np.max(times):.2f} 秒/条 |")
        md.append(f"| 平均候选数 | {np.mean([r['n_cands'] for r in recs]):.1f} 条/引用 |")
        md.append("")

    out.write_text("\n".join(md), encoding="utf-8")
    print(f"已写入 {out}")
    if ablation_json is not None:
        payload = {
            "protocol": (
                "Each feature subset is independently trained by L2 logistic regression "
                "and thresholded on the frozen development set; the frozen test subset "
                "is used only for final scoring."
            ),
            "development_features": str(dev_features_path).replace("\\", "/"),
            "test_cache": str(cache_path).replace("\\", "/"),
            "n_development": len(dev_rows),
            "n_test": len(recs),
            "rows": [
                {
                    "feature_combination": row["name"],
                    "features": row["features"],
                    "development_threshold": round(row["threshold"], 9),
                    "tp": row["confusion"][0],
                    "fp": row["confusion"][2],
                    "tn": row["confusion"][1],
                    "fn": row["confusion"][3],
                    "recall": round(row["metrics"][2], 9),
                    "precision": round(row["metrics"][1], 9),
                    "accuracy": round(row["metrics"][0], 9),
                    "f1": round(row["metrics"][3], 9),
                }
                for row in ablation_rows
            ],
        }
        ablation_json.parent.mkdir(parents=True, exist_ok=True)
        ablation_json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"已写入 {ablation_json}")
    if full_rc is not None:
        print(f"全融合召回率 {full_rc*100:.1f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", default="data/citation_dataset_final_v4.json")
    ap.add_argument("--input", default="data/refguard_input.jsonl")
    ap.add_argument("--sources", default="crossref,openalex,arxiv,dblp,semanticscholar,doicn")
    ap.add_argument("--model-dir", default="fusion_models_nodoi6")
    ap.add_argument("--profile", default="adaptive")
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--seed", type=int, default=20260601)
    ap.add_argument("--cache", default="fusion_models_nodoi6/ablation_cache.jsonl")
    ap.add_argument("--dev-features", default="fusion_models_nodoi6/dev_features.jsonl",
                    help="冻结开发集最佳候选特征，用于各特征子集独立训练和选阈值")
    ap.add_argument("--out", default="paper_tables_ablation.md")
    ap.add_argument("--ablation-json", default=None,
                    help="可选：另存结构化特征消融结果 JSON")
    ap.add_argument("--offline-only", action="store_true")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass
    cache_path = Path(args.cache)
    if not args.offline_only:
        build_cache(args, cache_path)
    export_tables(cache_path, args.model_dir, args.profile,
                  Path(args.dev_features), Path(args.out),
                  Path(args.ablation_json) if args.ablation_json else None)


if __name__ == "__main__":
    main()
