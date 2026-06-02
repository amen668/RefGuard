#!/usr/bin/env python3
"""核算真实文献 DOI 的注册商(Registration Agency)分布（论文 2.2/5.1/图2 的数据来源）。

向 doi.org 的权威接口 https://doi.org/ra/{doi} 查询每个真实文献 DOI 的注册机构，
缓存可断点续跑，最终输出注册商分布与“非 Crossref 占比”，供论文与配图引用。
此脚本使核心论断（跨注册商覆盖的必要性）可复现，替代此前硬编码的估计值。

用法：
    python scripts/compute_doi_ra.py            # 全量 1937 条真实 DOI
    python scripts/compute_doi_ra.py --limit 400
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

DATA = Path("data/citation_dataset_final_v4.json")
CACHE = Path("data/staging/doi_ra_cache.jsonl")
OUT = Path("data/doi_ra_distribution.json")


def query_ra(doi: str, retries: int = 3) -> str:
    url = "https://doi.org/ra/" + urllib.parse.quote(doi)
    for _ in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "refguard-doi-ra-audit"})
            payload = json.loads(urllib.request.urlopen(req, timeout=10).read())
            if isinstance(payload, list) and payload:
                return payload[0].get("RA") or payload[0].get("status") or "unknown"
            return "unknown"
        except Exception:
            time.sleep(1.0)
    return "error"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0.15)
    args = ap.parse_args()

    data = json.loads(DATA.read_text(encoding="utf-8"))
    reals = [r for r in data if r.get("label") == "real" and r.get("doi")]
    if args.limit:
        reals = reals[: args.limit]

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    done: dict[str, str] = {}
    if CACHE.exists():
        for line in CACHE.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                done[rec["doi"]] = rec["ra"]

    fh = CACHE.open("a", encoding="utf-8")
    for i, r in enumerate(reals):
        doi = r["doi"].strip()
        if doi in done:
            continue
        ra = query_ra(doi)
        done[doi] = ra
        fh.write(json.dumps({"doi": doi, "ra": ra}) + "\n")
        if (i + 1) % 50 == 0:
            fh.flush()
            print(f"  [{i + 1}/{len(reals)}] 已查询", flush=True)
        time.sleep(args.sleep)
    fh.close()

    vals = [done[r["doi"].strip()] for r in reals]
    counted = [v for v in vals if v not in ("error",)]
    dist = Counter(counted)
    n = len(counted)
    non_cross = sum(c for k, c in dist.items() if k not in ("Crossref",))
    summary = {
        "n_real_doi": len(reals),
        "n_resolved": n,
        "n_error": sum(1 for v in vals if v == "error"),
        "distribution": dict(dist.most_common()),
        "distribution_pct": {k: round(c / n * 100, 2) for k, c in dist.most_common()} if n else {},
        "non_crossref_pct": round(non_cross / n * 100, 2) if n else None,
    }
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n已写入 {OUT}")


if __name__ == "__main__":
    main()
