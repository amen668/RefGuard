#!/usr/bin/env python3
"""从评测报告离线生成论文图表数据（不打 API）。

读取 `eval/run_benchmark.py` 产出的 eval_report.json（逐条含 match_probability、
refguard_status、paper_id），结合数据集 citation_dataset_final_v4.json 的类型/
语种/学科/DOI 字段，输出以下表的数据（对应论文表号）：

- 表1  幻觉类型分布（来自数据集，不依赖评测）
- 表2  主实验混淆矩阵 + 头条指标
- 表5  判定阈值扫描（在 match_probability 上扫全局阈值的 P/R/F1/Acc/FPR）
- 表6  高置信切分扫描（Error/Warning 在 TP/FP 上的分配）
- 表7  主要指标 95% 置信区间（Wilson + Clopper-Pearson）
- 表9  误报案例（FP 列表，含 doc_type）
- 附   分语种 / 分文献类型 / 分学科 的分组指标（答审稿③⑤）

用法：
    python scripts/make_paper_tables.py \
        --report eval_report_final/eval_report.json \
        --dataset data/citation_dataset_final_v4.json \
        --out paper_tables.md
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


# ---------- 统计工具 ----------
def _confusion(rows):
    tp = sum(1 for r in rows if r["gt"] and r["pred"])
    tn = sum(1 for r in rows if not r["gt"] and not r["pred"])
    fp = sum(1 for r in rows if not r["gt"] and r["pred"])
    fn = sum(1 for r in rows if r["gt"] and not r["pred"])
    return tp, tn, fp, fn


def _metrics(tp, tn, fp, fn):
    n = tp + tn + fp + fn
    acc = (tp + tn) / n if n else 0.0
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return acc, prec, rec, f1, fpr


def wilson(k, n, z=1.96):
    """Wilson 得分区间。"""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    center = (p + z * z / (2 * n)) / d
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d
    return (max(0.0, center - half), min(1.0, center + half))


def _betacf(a, b, x, itmax=200, eps=3e-12):
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def betai(a, b, x):
    """正则化不完全 Beta 函数 I_x(a,b)。"""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    bt = math.exp(lbeta + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1 - x) / b


def _beta_quantile(p, a, b):
    """用二分在 [0,1] 上求 Beta(a,b) 的 p 分位数。"""
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if betai(a, b, mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def clopper_pearson(k, n, alpha=0.05):
    """Clopper-Pearson 精确区间。"""
    if n == 0:
        return (0.0, 0.0)
    lower = 0.0 if k == 0 else _beta_quantile(alpha / 2, k, n - k + 1)
    upper = 1.0 if k == n else _beta_quantile(1 - alpha / 2, k + 1, n - k)
    return (lower, upper)


# ---------- 主流程 ----------
def main() -> None:
    ap = argparse.ArgumentParser(description="从评测报告离线生成论文图表数据")
    ap.add_argument("--report", required=True, help="eval_report.json 路径")
    ap.add_argument("--dataset", default="data/citation_dataset_final_v4.json")
    ap.add_argument("--out", default="paper_tables.md")
    args = ap.parse_args()

    rep = json.loads(Path(args.report).read_text(encoding="utf-8"))
    results = rep["results"]
    byid = {r["id"]: r for r in json.loads(Path(args.dataset).read_text(encoding="utf-8"))}

    rows = []
    for r in results:
        meta = byid.get(r.get("paper_id"), {})
        rows.append({
            "id": r.get("paper_id"),
            "gt": bool(r["ground_truth_hallucinated"]),
            "pred": bool(r["predicted_hallucinated"]),
            "prob": float(r.get("match_probability", 0.0)),
            "status": r.get("refguard_status", ""),
            "doc_type": meta.get("doc_type", "?"),
            "language": meta.get("language", "?"),
            "discipline": (meta.get("discipline") or "?")[:1],
            "doi": meta.get("doi"),
            "title": meta.get("title", ""),
            "halluc_type": meta.get("hallucination_type"),
        })

    md = []
    A = md.append

    # 表1 幻觉类型分布（数据集全集）
    A("## 表1 幻觉引用类型分布（数据集全集）\n")
    hal = [r for r in byid.values()
           if r.get("label") == "hallucination" or (r.get("ground_truth") or {}).get("is_hallucinated")]
    ht = Counter(r.get("hallucination_type") or "未标注" for r in hal)
    A("| 幻觉类型 | 数量 | 百分比 |")
    A("|--|--:|--:|")
    for k, v in ht.most_common():
        A(f"| {k} | {v} | {v/len(hal)*100:.1f}% |")
    A(f"| **合计** | **{len(hal)}** | 100% |\n")

    # 表2 主实验混淆矩阵
    tp, tn, fp, fn = _confusion(rows)
    acc, prec, rec, f1, fpr = _metrics(tp, tn, fp, fn)
    A("## 表2 主实验混淆矩阵与指标（正类=幻觉）\n")
    A("| | 预测幻觉 | 预测真实 | 合计 |")
    A("|--|--:|--:|--:|")
    A(f"| **实际幻觉** | TP={tp} | FN={fn} | {tp+fn} |")
    A(f"| **实际真实** | FP={fp} | TN={tn} | {fp+tn} |")
    A(f"\n准确率 {acc:.4f} | 精确率 {prec:.4f} | 召回率 {rec:.4f} | F1 {f1:.4f} | FPR {fpr:.4f}\n")

    # 表5 判定阈值扫描
    A("## 表5 判定阈值扫描（pred_halluc = prob < thr）\n")
    A("| 阈值 | TP | FP | TN | FN | 召回率 | 精确率 | 准确率 | F1 | FPR |")
    A("|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    for thr in (0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.95):
        srows = [{"gt": r["gt"], "pred": (r["prob"] < thr)} for r in rows]
        t = _confusion(srows)
        m = _metrics(*t)
        A(f"| {thr:.2f} | {t[0]} | {t[2]} | {t[1]} | {t[3]} | "
          f"{m[2]*100:.1f}% | {m[1]*100:.1f}% | {m[0]*100:.1f}% | {m[3]:.3f} | {m[4]*100:.1f}% |")
    A("")

    # 表6 高置信切分（Error/Warning 分配）
    A("## 表6 高置信切分扫描（预测幻觉中 prob<c 记 Error，否则 Warning）\n")
    A("| 切分c | Error(TP) | Warning(TP) | Error(FP) | Warning(FP) | Error总数 | Warning总数 |")
    A("|--:|--:|--:|--:|--:|--:|--:|")
    pred_h = [r for r in rows if r["pred"]]
    for c in (0.10, 0.20, 0.30, 0.40, 0.50):
        e_tp = sum(1 for r in pred_h if r["gt"] and r["prob"] < c)
        w_tp = sum(1 for r in pred_h if r["gt"] and r["prob"] >= c)
        e_fp = sum(1 for r in pred_h if not r["gt"] and r["prob"] < c)
        w_fp = sum(1 for r in pred_h if not r["gt"] and r["prob"] >= c)
        A(f"| {c:.2f} | {e_tp} | {w_tp} | {e_fp} | {w_fp} | {e_tp+e_fp} | {w_tp+w_fp} |")
    A("")

    # 表7 置信区间
    A("## 表7 主要指标 95% 置信区间\n")
    A("| 指标 | 点估计 | Wilson | Clopper-Pearson |")
    A("|--|--:|--|--|")
    for name, k, n in [("召回率", tp, tp + fn), ("精确率", tp, tp + fp), ("准确率", tp + tn, len(rows))]:
        pt = k / n if n else 0.0
        wl, wh = wilson(k, n)
        cl, ch = clopper_pearson(k, n)
        A(f"| {name} | {pt*100:.1f}% | [{wl*100:.1f}%, {wh*100:.1f}%] | [{cl*100:.1f}%, {ch*100:.1f}%] |")
    A("")

    # 表9 误报案例
    A("## 表9 误报案例（FP：真实文献被判幻觉）\n")
    fps = [r for r in rows if not r["gt"] and r["pred"]]
    A(f"FP 共 {len(fps)} 条。按 doc_type：{dict(Counter(r['doc_type'] for r in fps))}")
    A(f"按语种：{dict(Counter(r['language'] for r in fps))}\n")
    A("| 案例ID | doc_type | 语种 | prob | DOI |")
    A("|--|--|--|--:|--|")
    for r in sorted(fps, key=lambda x: x["prob"])[:15]:
        A(f"| {r['id']} | {r['doc_type']} | {r['language']} | {r['prob']:.3f} | {r['doi']} |")
    A("")

    # 附表 分组指标
    def group_table(title, keyfn):
        A(f"## {title}\n")
        A("| 分组 | 样本数 | 幻觉数 | 召回率 | 精确率 | 准确率 | F1 |")
        A("|--|--:|--:|--:|--:|--:|--:|")
        groups = defaultdict(list)
        for r in rows:
            groups[keyfn(r)].append(r)
        for g, grows in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            t = _confusion(grows)
            m = _metrics(*t)
            nh = sum(1 for r in grows if r["gt"])
            A(f"| {g} | {len(grows)} | {nh} | {m[2]*100:.1f}% | {m[1]*100:.1f}% | {m[0]*100:.1f}% | {m[3]:.3f} |")
        A("")

    group_table("附表A 分语种指标（答审稿③中文支持）", lambda r: r["language"])
    group_table("附表B 分文献类型指标（答审稿⑤多类型）", lambda r: r["doc_type"])
    group_table("附表C 分学科指标（CLC 大类，答审稿⑤跨学科）", lambda r: r["discipline"])

    Path(args.out).write_text("\n".join(md), encoding="utf-8")
    print(f"已写入 {args.out}（{len(rows)} 条评测记录）")
    print(f"头条：N={len(rows)} Acc={acc:.4f} P={prec:.4f} R={rec:.4f} F1={f1:.4f} | FP={fp} FN={fn}")


if __name__ == "__main__":
    main()
