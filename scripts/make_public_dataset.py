#!/usr/bin/env python3
"""生成可公开发布的数据集版本（排除未获许可的第三方子集）。

处理：
- 默认完整排除 GPTZero 第三方子集，不再分发其完整引文或结构化条目。
- 输出对象含顶层 `_meta` 伦理声明与许可提示，明确合成负样本的使用限制。
- 仅保留书目与标注字段，剔除任何非必要字段。

输出默认写入 data/staging/（按 .gitignore 不入库）；正式公开前请配合
data/DATASET_CARD.md 的 release checklist 逐项核查许可。

用法：
    python scripts/make_public_dataset.py
"""
from __future__ import annotations

import json
import argparse
from pathlib import Path

SRC = Path("data/citation_dataset_final_v4.json")
OUT = Path("data/staging/citation_dataset_public.json")

GPTZERO_REPORT = "https://gptzero.me/news/neurips/"

# 公开版保留的字段白名单（仅书目 + 标注）
KEEP = {
    "id", "label", "subset", "hallucination_type",
    "title", "authors", "year", "venue", "doi", "arxiv_id", "url",
    "citation_text", "discipline", "language", "doc_type",
    "verification_status", "verifiable", "note",
    "source_paper", "source_paper_url", "split", "source",
}

META = {
    "name": "RefGuard citation-verification benchmark (public release)",
    "ethics": (
        "本数据集含人工合成的虚假（幻觉）参考文献作为检测负样本。带 "
        "label=hallucination 的条目均为刻意构造或第三方确认的不存在/错误引用，"
        "严禁当作真实文献引用或写入任何论文参考文献表。合成假作者名不影射真实个人。"
    ),
    "labels": "real = 经独立身份元数据确认；hallucination = 本项目受控合成负例",
    "third_party": {
        "hallucination_gptzero": (
            f"源自 GPTZero NeurIPS 2025 报告（{GPTZERO_REPORT}）；"
            "因尚未取得再分发许可，公开数据不包含该子集；如需研究请访问原报告。"
        )
    },
    "license_note": (
        "合成部分可按 CC-BY/CC0 使用；真实样本为公开书目事实（来源 Crossref/"
        "OpenAlex/arXiv/DBLP，多为 CC0）；第三方条目须遵循其来源条款。"
    ),
}


def build_public_dataset(data) -> tuple[dict, int]:
    rows = data.get("records", []) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("input must be a record list or an object containing records")
    excluded = 0
    out_records = []
    for r in rows:
        if r.get("subset") == "hallucination_gptzero":
            excluded += 1
            continue
        rec = {k: v for k, v in r.items() if k in KEEP}
        out_records.append(rec)
    meta = dict(META)
    meta["excluded_third_party_records"] = excluded
    return {"_meta": meta, "records": out_records}, excluded


def main():
    parser = argparse.ArgumentParser(description="生成不含未许可第三方子集的公开数据")
    parser.add_argument("--input", type=Path, default=SRC)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    payload, excluded = build_public_dataset(data)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"公开版已写入 {args.output}")
    print(f"  记录数 {len(payload['records'])}；排除未许可第三方记录 {excluded} 条")


if __name__ == "__main__":
    main()
