#!/usr/bin/env python3
"""生成可公开发布的数据集版本（剥离第三方原始判定字段 + 注入伦理声明）。

处理：
- 剥离 GPTZero 条目的 `gptzero_comment`（GPTZero 的原始判定文字，属第三方内容），
  代之以 `source` 指针（指向其公开报告），保留 `citation_text`/书目字段。
- 输出对象含顶层 `_meta` 伦理声明与许可提示，明确合成负样本的使用限制。
- 仅保留书目与标注字段，剔除任何非必要字段。

输出默认写入 data/staging/（按 .gitignore 不入库）；正式公开前请配合
data/DATASET_CARD.md 的 release checklist 逐项核查许可。

用法：
    python scripts/make_public_dataset.py
"""
from __future__ import annotations

import json
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
    "labels": "real = 经 doi.org 独立解析确立；hallucination = 合成扰动或 GPTZero 人工确认",
    "third_party": {
        "hallucination_gptzero": (
            f"源自 GPTZero NeurIPS 2025 报告（{GPTZERO_REPORT}）；"
            "已剥离其原始判定文字 gptzero_comment，请在使用时署名 GPTZero。"
        )
    },
    "license_note": (
        "合成部分可按 CC-BY/CC0 使用；真实样本为公开书目事实（来源 Crossref/"
        "OpenAlex/arXiv/DBLP，多为 CC0）；第三方条目须遵循其来源条款。"
    ),
}


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    stripped = 0
    out_records = []
    for r in data:
        rec = {k: v for k, v in r.items() if k in KEEP}
        if r.get("subset") == "hallucination_gptzero":
            if "gptzero_comment" in r:
                stripped += 1
            rec["source"] = GPTZERO_REPORT  # 指针替代原始判定文字
        out_records.append(rec)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {"_meta": META, "records": out_records}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"公开版已写入 {OUT}")
    print(f"  记录数 {len(out_records)}；已剥离 gptzero_comment {stripped} 条")
    print("  提示：发布前请按 data/DATASET_CARD.md 的 release checklist 核查许可。")


if __name__ == "__main__":
    main()
