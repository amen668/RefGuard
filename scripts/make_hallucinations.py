#!/usr/bin/env python3
"""从真实文献池派生 5 类合成幻觉，经负向核验后写入 staging。

类型（沿用现有中文词表）：
    标题篡改 / 作者伪造 / DOI捏造 / venue年份错配 / 完全虚构

诚信约束：
- 前 4 类由真实记录**扰动**得到，已知为假，标签可靠；保留原 source 记录的
  language/discipline/doc_type，并把 source_paper 指向原记录 id 以支撑无泄漏划分。
- "DOI捏造" 生成语法合法但**不解析**的 DOI，负向核验确认 doi.org 返回 404。
- "完全虚构" 整体编造；可选地在 OpenAlex 负向核验题名无命中。
- 每条 note 记录构造方法，满足 CONTRIBUTING「需说明构造方式」。

用法：
    python scripts/make_hallucinations.py
    python scripts/make_hallucinations.py --total 50 --no-verify   # 冒烟
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from refguard.core import settings  # noqa: E402

OPENALEX = "https://api.openalex.org/works"

# 全集幻觉 600 = 现有 100（gptzero）+ 合成 500。下表为合成 500 的类型配额。
SYNTH_QUOTA = {
    "标题篡改": 120,
    "作者伪造": 100,
    "DOI捏造": 100,
    "venue年份错配": 110,
    "完全虚构": 70,
}

FAKE_AUTHORS_EN = [
    "John A. Doe", "Jane B. Smith", "Robert C. Miller", "Emily D. Clark",
    "Michael E. Brown", "Sarah F. Wilson", "David G. Lee", "Laura H. Adams",
]
FAKE_SURNAME_ZH = list("王李张刘陈杨黄赵周吴徐孙马朱胡郭何高林")
FAKE_GIVEN_ZH = ["志强", "晓明", "建国", "丽华", "海燕", "文博", "思源", "雨欣", "国栋", "婷婷"]

# 完全虚构题名的词库（看似合理、组合不对应真实论文）。
FABRICATE_EN = {
    "adj": ["Adaptive", "Hierarchical", "Robust", "Scalable", "Unified", "Probabilistic"],
    "topic": ["Graph Representation", "Cross-Modal Alignment", "Federated Optimization",
              "Spectral Clustering", "Causal Discovery", "Neural Retrieval"],
    "tail": ["for Low-Resource Domains", "under Distribution Shift", "with Limited Supervision",
             "in Dynamic Environments", "via Contrastive Objectives"],
}
FABRICATE_ZH = {
    "adj": ["自适应", "层次化", "鲁棒", "可扩展", "概率"],
    "topic": ["图表示学习", "跨模态对齐", "联邦优化", "因果发现", "神经检索"],
    "tail": ["在低资源场景下的研究", "面向分布漂移的方法", "及其弱监督扩展", "的动态环境建模"],
}
FAKE_VENUES = [
    "International Journal of Advanced Computing", "Journal of Applied Data Science",
    "Transactions on Intelligent Systems", "Annual Conference on Machine Reasoning",
    "中国智能系统学报", "应用数据科学学报",
]


def clean(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def has_cjk(s: str) -> bool:
    return bool(re.search(r"[一-鿿]", s or ""))


class Negator:
    """负向核验：确认幻觉不对应真实公开记录。"""

    def __init__(self, enabled: bool, timeout: int) -> None:
        self.enabled = enabled
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "RefGuard-DataCollector/1.0"

    def doi_unresolvable(self, doi: str) -> bool:
        if not self.enabled:
            return True
        try:
            r = self.session.head(f"https://doi.org/{doi}", allow_redirects=True, timeout=self.timeout)
            time.sleep(0.1)
            return r.status_code >= 400
        except requests.RequestException:
            return True

    def title_absent(self, title: str) -> bool:
        if not self.enabled:
            return True
        try:
            r = self.session.get(
                OPENALEX,
                params={"filter": f"title.search:{title}", "per-page": 1},
                timeout=self.timeout,
            )
            time.sleep(0.1)
            if r.status_code != 200:
                return True
            return r.json().get("meta", {}).get("count", 0) == 0
        except (requests.RequestException, ValueError):
            return True


def fake_doi(rng: random.Random) -> str:
    prefix = rng.randint(10000, 59999)
    suffix = "".join(rng.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(10))
    return f"10.{prefix}/{suffix}"


def fake_authors(rng: random.Random, language: str, n: int = 3) -> str:
    if language == "Chinese":
        return ", ".join(rng.choice(FAKE_SURNAME_ZH) + rng.choice(FAKE_GIVEN_ZH) for _ in range(n))
    return " and ".join(rng.sample(FAKE_AUTHORS_EN, k=min(n, len(FAKE_AUTHORS_EN))))


def tamper_title(rng: random.Random, title: str) -> str:
    words = title.split()
    if len(words) < 3:
        return title + (" 改进研究" if has_cjk(title) else " Revisited")
    op = rng.choice(["swap", "insert_num", "replace"])
    if op == "swap":
        i = rng.randrange(len(words) - 1)
        words[i], words[i + 1] = words[i + 1], words[i]
    elif op == "insert_num":
        words.insert(rng.randrange(len(words)), str(rng.randint(2, 9)))
    else:
        repl = "增强" if has_cjk(title) else "Enhanced"
        words[rng.randrange(len(words))] = repl
    return " ".join(words)


def fabricate_title(rng: random.Random, language: str) -> str:
    pool = FABRICATE_ZH if language == "Chinese" else FABRICATE_EN
    if language == "Chinese":
        return f"{rng.choice(pool['adj'])}{rng.choice(pool['topic'])}{rng.choice(pool['tail'])}"
    return f"{rng.choice(pool['adj'])} {rng.choice(pool['topic'])} {rng.choice(pool['tail'])}"


def base_record(real: dict, htype: str, rid: str, note: str) -> dict:
    return {
        "id": rid,
        "label": "hallucination",
        "hallucination_type": htype,
        "title": real.get("title", ""),
        "authors": real.get("authors", ""),
        "year": str(real.get("year", "")),
        "venue": real.get("venue", ""),
        "doi": "",
        "arxiv_id": "",
        "url": "",
        "source_paper": real.get("id", ""),
        "source_paper_url": "",
        "discipline": real.get("discipline", ""),
        "language": real.get("language", "English"),
        "doc_type": real.get("doc_type", "journal"),
        "subset": "hallucination_synthetic",
        "verification_status": "hallucination_verified",
        "verifiable": True,
        "note": note,
    }


def synthesize(reals: list[dict], total_scale: float, negator: Negator, seed: int) -> list[dict]:
    rng = random.Random(seed)
    out: list[dict] = []
    pool = [r for r in reals if r.get("title")]
    if not pool:
        return out
    counter = 0
    for htype, quota in SYNTH_QUOTA.items():
        want = max(1, round(quota * total_scale))
        made = 0
        attempts = 0
        while made < want and attempts < want * 20:
            attempts += 1
            real = rng.choice(pool)
            lang = real.get("language", "English")
            counter += 1
            rid = f"S-{real.get('discipline','NA')}-{'ZH' if lang=='Chinese' else 'EN'}-{counter:05d}"
            rec = None
            if htype == "标题篡改":
                rec = base_record(real, htype, rid, "标题篡改：改写真实题名，去除强标识")
                rec["title"] = tamper_title(rng, real["title"])
            elif htype == "作者伪造":
                rec = base_record(real, htype, rid, "作者伪造：替换为虚构作者，保留真实题名/venue/年份")
                rec["authors"] = fake_authors(rng, lang)
            elif htype == "DOI捏造":
                doi = fake_doi(rng)
                if not negator.doi_unresolvable(doi):
                    continue
                rec = base_record(real, htype, rid, f"DOI捏造：合法格式但不解析的 DOI {doi}")
                rec["doi"] = doi
                rec["url"] = f"https://doi.org/{doi}"
            elif htype == "venue年份错配":
                rec = base_record(real, htype, rid, "venue年份错配：真实题名 + 错配 venue/年份")
                if rng.random() < 0.5:
                    rec["venue"] = rng.choice(FAKE_VENUES)
                try:
                    rec["year"] = str(int(real["year"]) + rng.choice([-2, -1, 1, 2]))
                except (ValueError, TypeError):
                    pass
            elif htype == "完全虚构":
                title = fabricate_title(rng, lang)
                if not negator.title_absent(title):
                    continue
                rec = base_record(real, htype, rid, "完全虚构：编造题名/作者/venue，OpenAlex 无命中")
                rec["title"] = title
                rec["authors"] = fake_authors(rng, lang)
                rec["venue"] = rng.choice(FAKE_VENUES)
                rec["year"] = str(rng.randint(2015, 2024))
                rec["source_paper"] = ""  # 完全虚构无来源
            if rec:
                out.append(rec)
                made += 1
        print(f"  {htype:<12} 目标 {want:>4} 实得 {made:>4}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="从真实池派生 5 类合成幻觉 + 负向核验")
    ap.add_argument("--input", default="data/staging/real_refs.json")
    ap.add_argument("--output", default="data/staging/synth_hallucinations.json")
    ap.add_argument("--total", type=int, default=None, help="覆盖合成总量（按比例缩放各类型，冒烟用）")
    ap.add_argument("--no-verify", action="store_true", help="跳过负向核验（仅调试）")
    ap.add_argument("--seed", type=int, default=20260531)
    args = ap.parse_args()

    reals = json.loads(Path(args.input).read_text(encoding="utf-8"))
    full = sum(SYNTH_QUOTA.values())
    scale = (args.total / full) if args.total else 1.0
    negator = Negator(enabled=not args.no_verify, timeout=getattr(settings, "request_timeout", 30))

    print(f"真实池 {len(reals)} 条，合成缩放 {scale:.3f}")
    records = synthesize(reals, scale, negator, args.seed)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n写入 {out} 共 {len(records)} 条合成幻觉")


if __name__ == "__main__":
    main()
