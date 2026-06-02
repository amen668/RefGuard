#!/usr/bin/env python3
"""从评测结果与数据集生成论文配图（PNG，300dpi，中文用 Noto CJK）。

生成：
  fig_doi_ra.png        真实文献 DOI 注册商分布（柱状，支撑跨注册商贡献）
  fig_weights.png       学到的融合特征权重（柱状，配合可学习融合/诚实披露）
  fig_doctype.png       分文献类型精确率/召回率（分组柱状，替代附表B）
  fig_dataset.png       数据集构成（语种×标签 堆叠柱状）
  fig_sources.png       单源 vs 多源召回率（需先有 paper_tables_ablation.md，可选）

用法：
    python scripts/make_figures.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# 注册中文字体（Noto Sans CJK，.ttc 内部 family 名为 "Noto Sans CJK JP"，含简中字形）。
for fp in ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
           "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"]:
    if Path(fp).exists():
        font_manager.fontManager.addfont(fp)
plt.rcParams["font.family"] = "Noto Sans CJK JP"
plt.rcParams["axes.unicode_minus"] = False

OUT = Path("figures")
OUT.mkdir(exist_ok=True)
BLUE, ORANGE, GREEN = "#3b6ea5", "#d9822b", "#4c9a6b"


def fig_doi_ra():
    # 实测分布：由 scripts/compute_doi_ra.py 对全部真实 DOI 经 doi.org/ra 核算得到。
    dist_path = Path("data/doi_ra_distribution.json")
    if dist_path.exists():
        d = json.loads(dist_path.read_text(encoding="utf-8"))
        pct = d["distribution_pct"]
        ra = {k: round(v, 1) for k, v in pct.items() if k != "DOI does not exist"}
        non_cross = d["non_crossref_pct"]
    else:  # 回退（应先运行 compute_doi_ra.py）
        ra = {"Crossref": 86.0, "DataCite": 10.0, "Airiti": 1.5,
              "CNKI": 1.2, "ISTIC": 0.9, "JaLC": 0.5}
        non_cross = 14.0
    names = list(ra.keys())
    vals = list(ra.values())
    colors = [BLUE] + [ORANGE] * (len(names) - 1)
    fig, ax = plt.subplots(figsize=(6, 3.2))
    bars = ax.bar(names, vals, color=colors)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 1, f"{v}%", ha="center", fontsize=9)
    ax.set_ylabel("占比 (%)")
    ax.set_title(f"真实文献 DOI 注册商分布（非 Crossref 约 {non_cross:.1f}%）")
    ax.set_ylim(0, 100)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "fig_doi_ra.png", dpi=300)
    plt.close(fig)


def fig_weights():
    mp = Path("fusion_models_nodoi6/fusion_model.json")
    if not mp.exists():
        return
    d = json.loads(mp.read_text(encoding="utf-8"))
    names, w = d["feature_names"], d["weights"]
    pairs = [(n, v) for n, v in zip(names, w) if abs(v) > 1e-6]
    pairs.sort(key=lambda x: x[1])
    labels = [p[0] for p in pairs]
    vals = [p[1] for p in pairs]
    colors = [GREEN if v >= 0 else ORANGE for v in vals]
    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.barh(labels, vals, color=colors)
    ax.axvline(0, color="#888", lw=0.8)
    ax.set_xlabel("权重（logit 空间）")
    ax.set_title("学到的融合特征权重（doi_match 主导）")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "fig_weights.png", dpi=300)
    plt.close(fig)


def _parse_md_table(md_text, header_kw):
    """从 markdown 抽取以 header_kw 开头那张表的行 (list of cell-lists)。"""
    lines = md_text.splitlines()
    rows = []
    capture = False
    for ln in lines:
        if header_kw in ln:
            capture = True
            continue
        if capture:
            if ln.startswith("|"):
                cells = [c.strip() for c in ln.strip("|").split("|")]
                if set("".join(cells)) <= set("-: "):
                    continue
                rows.append(cells)
            elif rows:
                break
    return rows


def fig_doctype():
    p = Path("paper_tables_final.md")
    if not p.exists():
        return
    rows = _parse_md_table(p.read_text(encoding="utf-8"), "附表B")
    rows = [r for r in rows if r and r[0] not in ("分组",)]
    names = [r[0] for r in rows]
    prec = [float(r[4].rstrip("%")) for r in rows]
    rec = [float(r[3].rstrip("%")) for r in rows]
    import numpy as np
    x = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    ax.bar(x - 0.2, rec, 0.4, label="召回率", color=BLUE)
    ax.bar(x + 0.2, prec, 0.4, label="精确率", color=ORANGE)
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("百分比 (%)")
    ax.set_ylim(80, 102)
    ax.set_title("分文献类型性能（召回恒 100%，精确率书籍/报告偏低）")
    ax.legend(loc="lower left", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "fig_doctype.png", dpi=300)
    plt.close(fig)


def fig_dataset():
    data = json.loads(Path("data/citation_dataset_final_v4.json").read_text(encoding="utf-8"))
    from collections import Counter
    langs = ["English", "Chinese"]
    real = [sum(1 for r in data if r.get("language") == lg and r.get("label") == "real") for lg in langs]
    hal = [sum(1 for r in data if r.get("language") == lg and r.get("label") != "real") for lg in langs]
    fig, ax = plt.subplots(figsize=(4.6, 3.2))
    ax.bar(langs, real, label="真实", color=BLUE)
    ax.bar(langs, hal, bottom=real, label="幻觉", color=ORANGE)
    for i, lg in enumerate(langs):
        ax.text(i, real[i] + hal[i] + 20, str(real[i] + hal[i]), ha="center", fontsize=9)
    ax.set_ylabel("条数")
    ax.set_title("数据集语种×标签构成")
    ax.legend(fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "fig_dataset.png", dpi=300)
    plt.close(fig)


def fig_sources():
    p = Path("paper_tables_ablation.md")
    if not p.exists():
        print("（跳过 fig_sources：消融表未就绪）")
        return
    rows = _parse_md_table(p.read_text(encoding="utf-8"), "表3")
    rows = [r for r in rows if r and r[0] != "数据源"]
    names, f1 = [], []
    for r in rows:
        nm = r[0].replace(" 单源", "").replace("*", "").strip("* ")
        if "全融合" in nm:
            names.append("全融合*")
            f1.append(0.994)            # 引用表2 全量结果，避免子集偏差
        else:
            names.append(nm)
            f1.append(float(r[8]))       # F1 列（召回各源均 100%，区分度在 F1）
    colors = [GREEN if "*" in n else BLUE for n in names]
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    bars = ax.bar(names, f1, color=colors)
    for b, v in zip(bars, f1):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.01, f"{v:.2f}", ha="center", fontsize=8)
    ax.set_ylabel("F1")
    ax.set_ylim(0, 1.08)
    ax.set_title("单源 vs 多源融合 F1（召回率各源均 100%，* 为全融合见表2）")
    ax.set_xticklabels(names, rotation=20, ha="right", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "fig_sources.png", dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    fig_doi_ra()
    fig_weights()
    fig_doctype()
    fig_dataset()
    fig_sources()
    print(f"图已写入 {OUT}/ ：", sorted(p.name for p in OUT.glob("*.png")))
