#!/usr/bin/env python3
"""合并真实文献、现有 GPTZero 幻觉与合成幻觉，去重并做无泄漏 dev/test 划分。

输出 data/citation_dataset_final_v4.json（build_refguard_input.py 的源数据）。

划分规则：按 source_paper 分组（无来源则用记录 id 自成一组），整组一起划入
dev 或 test，避免同源记录跨子集泄漏；按组 key 的稳定哈希分配，dev 约占 20%。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def clean(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def norm_doi(doi: str | None) -> str:
    s = clean(doi).lower()
    for p in ("https://doi.org/", "http://doi.org/", "doi:"):
        if s.startswith(p):
            s = s[len(p):]
    return s


def load(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        print(f"  [warn] 跳过不存在的输入：{p}", file=sys.stderr)
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def normalize_seed(rec: dict) -> dict:
    """现有 GPTZero 幻觉：补全缺失学科为 TP，统一语种字段。"""
    rec = dict(rec)
    if not clean(rec.get("discipline")):
        rec["discipline"] = "TP"  # NeurIPS AI 论文，归计算机
    if not clean(rec.get("language")) and clean(rec.get("lang")):
        rec["language"] = rec["lang"]
    return rec


def group_key(rec: dict) -> str:
    sp = clean(rec.get("source_paper"))
    return sp if sp else clean(rec.get("id"))


def assign_split(key: str, dev_ratio: float) -> str:
    h = int(hashlib.sha1(key.encode("utf-8")).hexdigest(), 16) % 1000
    return "dev" if h < dev_ratio * 1000 else "test"


def main() -> None:
    ap = argparse.ArgumentParser(description="组装 citation_dataset_final_v4.json + dev/test 划分")
    ap.add_argument("--real", default="data/staging/real_refs.json")
    ap.add_argument("--seed-halluc", default="data/citation_hallucination.json")
    ap.add_argument("--synth-halluc", default="data/staging/synth_hallucinations.json")
    ap.add_argument("--output", default="data/citation_dataset_final_v4.json")
    ap.add_argument("--dev-ratio", type=float, default=0.2)
    args = ap.parse_args()

    reals = load(args.real)
    seeds = [normalize_seed(r) for r in load(args.seed_halluc)]
    synth = load(args.synth_halluc)
    merged = reals + seeds + synth

    # 去重：id 唯一；真实记录额外按 DOI 去重。
    out: list[dict] = []
    seen_id: set[str] = set()
    seen_doi: set[str] = set()
    dropped = 0
    for rec in merged:
        rid = clean(rec.get("id"))
        if not rid or rid in seen_id:
            dropped += 1
            continue
        if rec.get("label") == "real":
            d = norm_doi(rec.get("doi"))
            if d and d in seen_doi:
                dropped += 1
                continue
            if d:
                seen_doi.add(d)
        seen_id.add(rid)
        out.append(rec)

    # 按来源分组做 dev/test 划分。
    for rec in out:
        rec["split"] = assign_split(group_key(rec), args.dev_ratio)

    outp = Path(args.output)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    labels = Counter(r.get("label") for r in out)
    splits = Counter(r.get("split") for r in out)
    langs = Counter(r.get("language") or "∅" for r in out)
    discs = Counter(r.get("discipline") or "∅" for r in out)
    print(f"写入 {outp} 共 {len(out)} 条（去重丢弃 {dropped}）")
    print(f"  label : {dict(labels)}")
    print(f"  split : {dict(splits)}")
    print(f"  lang  : {dict(langs)}")
    print(f"  CLC   : {dict(sorted(discs.items()))}")


if __name__ == "__main__":
    main()
