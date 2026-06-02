#!/usr/bin/env python3
"""按中图法 CLC 大类分层采集真实文献，做独立存在性核验后写入 staging。

设计要点（见数据整理方案）：
- 来源：OpenAlex（公开 API，支持 concept/语种/类型过滤与游标分页），**不抓 Google Scholar**。
- 真实标签由**独立证据**确立——每条记录的 DOI 经 doi.org 解析确认存在，
  与被评测的 RefGuard 判定解耦，避免循环标注。
- 学科用 CLC 大类标识（TP/O/R/...），由桶定义直接赋值。
- 输出为 build_refguard_input.py 可消费的源 schema（label=real）。

用法：
    python scripts/collect_real_refs.py                 # 全量（受 API 限速，耗时长）
    python scripts/collect_real_refs.py --scale 0.01    # 小样本冒烟
    python scripts/collect_real_refs.py --limit-buckets 2 --no-verify-doi  # 离线/快速调试
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Iterable

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from refguard.core import settings  # noqa: E402

OPENALEX = "https://api.openalex.org/works"

# (CLC 大类, OpenAlex level-0 concept, 概念名, 全集配额) —— 配额对应 3000 全集，
# 真实目标 = 配额 * (2400/3000)，再按语种切分。
CLC_CONCEPTS: list[tuple[str, str, str, int]] = [
    ("TP", "C41008148", "Computer science", 540),
    ("O", "C121332964", "Physics", 130),
    ("O", "C185592680", "Chemistry", 120),
    ("O", "C33923547", "Mathematics", 80),
    ("R", "C71924100", "Medicine", 330),
    ("Q", "C86803240", "Biology", 240),
    ("T", "C127413603", "Engineering", 180),
    ("T", "C192562407", "Materials science", 120),
    ("F", "C162324750", "Economics", 120),
    ("F", "C144133560", "Business", 90),
    ("P", "C127313418", "Geology", 110),
    ("P", "C205649164", "Geography", 100),
    ("X", "C39432304", "Environmental science", 150),
    ("G", "C144024400", "Sociology", 90),
    ("G", "C17744445", "Political science", 90),
    ("S", "C6557445", "Agronomy", 120),
    ("B", "C15744967", "Psychology", 90),
    ("B", "C138885662", "Philosophy", 60),
    ("K", "C95457728", "History", 90),
    ("N", "C127413603", "Engineering", 60),  # 综合理工占位，回退到工程概念
]

REAL_RATIO = 2400 / 3000  # 真实占全集比例
# 多数语种以英文为主；部分学科中文公开元数据较丰富，给更高中文配比。
ZH_SHARE = {
    "R": 0.45, "F": 0.40, "G": 0.45, "K": 0.45, "B": 0.40, "S": 0.45,
    "X": 0.35, "P": 0.30, "Q": 0.25, "O": 0.25, "T": 0.30, "TP": 0.20, "N": 0.30,
}

# OpenAlex type -> 数据集 doc_type
DOC_TYPE_MAP = {
    "article": "journal",
    "journal-article": "journal",
    "proceedings-article": "conference",
    "proceedings": "conference",
    "posted-content": "preprint",
    "preprint": "preprint",
    "book": "book",
    "book-chapter": "book",
    "monograph": "book",
    "reference-book": "book",
    "dissertation": "thesis",
    "report": "technical_report",
    "report-series": "technical_report",
    "standard": "technical_report",
    "dataset": "technical_report",
}


# 补采计划：定向捞带 DOI 的非期刊类型 + 回补稀疏 CLC/中文桶。
# 每项 = (CLC, concept, 概念名, OpenAlex 附加过滤片段, 数据集 doc_type, 语种, 目标数)。
# 注意 OpenAlex 当前 work type 词表与 Crossref 不同：会议用
# `primary_location.source.type:conference`（无独立 proceedings 类型），
# 预印本 `type:preprint`，学位论文 `type:dissertation`，报告 `type:report`，
# 图书章节 `type:book-chapter`。has_doi:true 仍生效，保证独立 DOI 可核验。
CONF = "primary_location.source.type:conference"
TOPUP_BUCKETS: list[tuple[str, str, str, str, str, str, int]] = [
    # 会议
    ("TP", "C41008148", "Computer science", CONF, "conference", "English", 110),
    ("TP", "C41008148", "Computer science", CONF, "conference", "Chinese", 30),
    ("T", "C127413603", "Engineering", CONF, "conference", "English", 50),
    ("O", "C121332964", "Physics", CONF, "conference", "English", 35),
    ("R", "C71924100", "Medicine", CONF, "conference", "English", 30),
    ("Q", "C86803240", "Biology", CONF, "conference", "English", 25),
    ("F", "C162324750", "Economics", CONF, "conference", "English", 25),
    ("X", "C39432304", "Environmental science", CONF, "conference", "English", 20),
    # 预印本
    ("TP", "C41008148", "Computer science", "type:preprint", "preprint", "English", 80),
    ("O", "C121332964", "Physics", "type:preprint", "preprint", "English", 45),
    ("Q", "C86803240", "Biology", "type:preprint", "preprint", "English", 35),
    ("R", "C71924100", "Medicine", "type:preprint", "preprint", "English", 35),
    ("T", "C192562407", "Materials science", "type:preprint", "preprint", "English", 20),
    ("X", "C39432304", "Environmental science", "type:preprint", "preprint", "English", 20),
    # 学位论文
    ("TP", "C41008148", "Computer science", "type:dissertation", "thesis", "English", 30),
    ("R", "C71924100", "Medicine", "type:dissertation", "thesis", "English", 25),
    ("F", "C162324750", "Economics", "type:dissertation", "thesis", "English", 20),
    ("G", "C144024400", "Sociology", "type:dissertation", "thesis", "English", 20),
    ("Q", "C86803240", "Biology", "type:dissertation", "thesis", "English", 20),
    # 技术报告
    ("X", "C39432304", "Environmental science", "type:report", "technical_report", "English", 25),
    ("TP", "C41008148", "Computer science", "type:report", "technical_report", "English", 25),
    ("R", "C71924100", "Medicine", "type:report", "technical_report", "English", 25),
    ("O", "C121332964", "Physics", "type:report", "technical_report", "English", 20),
    # 图书章节回补
    ("K", "C95457728", "History", "type:book-chapter", "book", "English", 25),
    ("B", "C138885662", "Philosophy", "type:book-chapter", "book", "English", 20),
    # 稀疏 CLC / 中文期刊回补
    ("N", "C127413603", "Engineering", "", "journal", "English", 25),
    ("N", "C127413603", "Engineering", "", "journal", "Chinese", 15),
    ("G", "C17744445", "Political science", "", "journal", "Chinese", 30),
    ("B", "C15744967", "Psychology", "", "journal", "Chinese", 25),
    ("K", "C95457728", "History", "", "journal", "Chinese", 30),
    ("R", "C71924100", "Medicine", "", "journal", "Chinese", 40),
    ("F", "C162324750", "Economics", "", "journal", "Chinese", 30),
    ("S", "C6557445", "Agronomy", "", "journal", "Chinese", 30),
    ("X", "C39432304", "Environmental science", "", "journal", "Chinese", 25),
    ("Q", "C86803240", "Biology", "", "journal", "Chinese", 25),
    ("P", "C205649164", "Geography", "", "journal", "Chinese", 25),
    ("O", "C185592680", "Chemistry", "", "journal", "Chinese", 25),
    ("T", "C192562407", "Materials science", "", "journal", "Chinese", 25),
]


def clean(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def norm_doi(doi: str | None) -> str:
    s = clean(doi).lower()
    for p in ("https://doi.org/", "http://doi.org/", "doi:"):
        if s.startswith(p):
            s = s[len(p):]
    return s


def map_doc_type(work: dict) -> str:
    t = clean(work.get("type") or work.get("type_crossref")).lower()
    return DOC_TYPE_MAP.get(t, "journal")


class Collector:
    def __init__(self, mailto: str, verify_doi: bool, timeout: int) -> None:
        self.verify_doi = verify_doi
        self.timeout = timeout
        self.session = requests.Session()
        ua = f"RefGuard-DataCollector/1.0 (mailto:{mailto})" if mailto else "RefGuard-DataCollector/1.0"
        self.session.headers["User-Agent"] = ua
        self.mailto = mailto
        self._doi_cache: dict[str, bool] = {}

    # --- OpenAlex 采集 ---
    def harvest(self, concept_id: str, language: str, target: int, per_page: int,
                extra_filter: str | None = None, force_doc_type: str | None = None) -> Iterable[dict]:
        """按 concept + 语种 + has_doi（+ 可选附加过滤）翻页产出 works。

        extra_filter: 追加到 OpenAlex filter 的片段（如 `type:dissertation` 或
        `primary_location.source.type:conference`），用于定向补采带 DOI 的
        非期刊类型；命中后用 force_doc_type 覆写数据集 doc_type，保证类型配额精确。
        """
        lang_code = "zh" if language == "Chinese" else "en"
        filt = f"concepts.id:{concept_id},language:{lang_code},has_doi:true"
        if extra_filter:
            filt += f",{extra_filter}"
        cursor = "*"
        yielded = 0
        while yielded < target and cursor:
            params = {
                "filter": filt,
                "per-page": min(per_page, max(1, target - yielded)),
                "cursor": cursor,
                "select": "id,doi,title,publication_year,authorships,type,type_crossref,"
                          "primary_location,language",
            }
            if self.mailto:
                params["mailto"] = self.mailto
            try:
                r = self.session.get(OPENALEX, params=params, timeout=self.timeout)
                r.raise_for_status()
                data = r.json()
            except (requests.RequestException, ValueError) as exc:
                print(f"  [warn] OpenAlex 查询失败 ({concept_id}/{language}): {exc}", file=sys.stderr)
                return
            results = data.get("results", [])
            if not results:
                return
            for w in results:
                rec = self._work_to_record(w, language)
                if rec is None:
                    continue
                if force_doc_type:
                    rec["doc_type"] = force_doc_type
                if self.verify_doi and not self._doi_resolves(rec["doi"]):
                    continue
                yield rec
                yielded += 1
                if yielded >= target:
                    return
            cursor = data.get("meta", {}).get("next_cursor")
            time.sleep(settings.openalex_rate_limit_delay)

    def _work_to_record(self, w: dict, language: str) -> dict | None:
        title = clean(w.get("title"))
        doi = norm_doi(w.get("doi"))
        if not title or not doi:
            return None
        authors = [clean(a.get("author", {}).get("display_name"))
                   for a in w.get("authorships", []) if a.get("author")]
        authors = [a for a in authors if a]
        if not authors:
            return None
        year = w.get("publication_year")
        if not year:
            return None
        venue = ""
        loc = w.get("primary_location") or {}
        src = loc.get("source") or {}
        venue = clean(src.get("display_name"))
        return {
            "title": title,
            "authors": " and ".join(authors),
            "year": str(year),
            "venue": venue,
            "doi": doi,
            "arxiv_id": "",
            "url": f"https://doi.org/{doi}",
            "language": language,
            "doc_type": map_doc_type(w),
            "openalex_id": clean(w.get("id")),
        }

    # --- 独立存在性核验：DOI 经 doi.org 解析 ---
    def _doi_resolves(self, doi: str) -> bool:
        if doi in self._doi_cache:
            return self._doi_cache[doi]
        ok = False
        try:
            r = self.session.head(
                f"https://doi.org/{doi}", allow_redirects=True, timeout=self.timeout
            )
            ok = r.status_code < 400
        except requests.RequestException:
            ok = False
        self._doi_cache[doi] = ok
        time.sleep(0.1)
        return ok


def build_targets(scale: float) -> list[dict]:
    """展开 CLC_CONCEPTS 为 (clc, concept, language, target) 桶。"""
    buckets = []
    for clc, cid, name, full_quota in CLC_CONCEPTS:
        real_total = full_quota * REAL_RATIO * scale
        zh = ZH_SHARE.get(clc, 0.3)
        zh_n = round(real_total * zh)
        en_n = round(real_total * (1 - zh))
        for lang, n in (("English", en_n), ("Chinese", zh_n)):
            if n >= 1:
                buckets.append({"clc": clc, "concept": cid, "name": name, "language": lang, "target": n})
    return buckets


def build_topup_targets(scale: float) -> list[dict]:
    """展开 TOPUP_BUCKETS 为带 type 定向的桶。"""
    buckets = []
    for clc, cid, name, ofilter, doc_type, lang, n in TOPUP_BUCKETS:
        t = round(n * scale)
        if t >= 1:
            buckets.append({"clc": clc, "concept": cid, "name": name, "language": lang,
                            "ofilter": ofilter, "doc_type": doc_type, "target": t})
    return buckets


def main() -> None:
    ap = argparse.ArgumentParser(description="CLC 分层采集真实文献 + 独立 DOI 核验")
    ap.add_argument("--output", default="data/staging/real_refs.json")
    ap.add_argument("--scale", type=float, default=1.0, help="配额缩放（冒烟用 0.01）")
    ap.add_argument("--per-page", type=int, default=200, help="OpenAlex 每页数量")
    ap.add_argument("--limit-buckets", type=int, default=None, help="只跑前 N 个桶（调试）")
    ap.add_argument("--no-verify-doi", action="store_true", help="跳过 doi.org 解析核验（仅调试）")
    ap.add_argument("--mailto", default=settings.crossref_mailto or "", help="polite pool 邮箱")
    ap.add_argument("--mode", choices=["full", "topup"], default="full",
                    help="full=初采全集；topup=按 TOPUP_BUCKETS 定向补采非期刊类型/稀疏桶")
    ap.add_argument("--append", action="store_true",
                    help="续采：载入已有 --output，按 DOI 去重并接着编号，不冲掉已采数据")
    ap.add_argument("--skip-buckets", type=int, default=0,
                    help="跳过前 N 个桶（断点续跑：前 N 桶已采完时避免重复查询）")
    args = ap.parse_args()

    # 行缓冲：让重定向到文件时 tail -f 能实时看到每行进度。
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass

    buckets = build_topup_targets(args.scale) if args.mode == "topup" else build_targets(args.scale)
    if args.skip_buckets:
        buckets = buckets[args.skip_buckets:]
    if args.limit_buckets:
        buckets = buckets[: args.limit_buckets]

    collector = Collector(
        mailto=args.mailto,
        verify_doi=not args.no_verify_doi,
        timeout=getattr(settings, "request_timeout", 30),
    )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    def checkpoint(recs: list[dict]) -> None:
        """每个桶采完落盘，断点也不丢已采数据。"""
        out.write_text(json.dumps(recs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    records: list[dict] = []
    seen_doi: set[str] = set()
    if args.append and out.exists():
        records = json.loads(out.read_text(encoding="utf-8"))
        seen_doi = {norm_doi(r.get("doi")) for r in records if r.get("doi")}
        print(f"续采：载入已有 {len(records)} 条，去重基准 DOI {len(seen_doi)} 个", flush=True)
    per_clc: dict[str, int] = {}
    for i, b in enumerate(buckets):
        got = 0
        for rec in collector.harvest(b["concept"], b["language"], b["target"], args.per_page,
                                     extra_filter=b.get("ofilter") or None,
                                     force_doc_type=b.get("doc_type")):
            if rec["doi"] in seen_doi:
                continue
            seen_doi.add(rec["doi"])
            rec_id = f"R-{b['clc']}-{'EN' if b['language']=='English' else 'ZH'}-{len(records)+1:05d}"
            records.append({
                "id": rec_id,
                "label": "real",
                "title": rec["title"],
                "authors": rec["authors"],
                "year": rec["year"],
                "venue": rec["venue"],
                "doi": rec["doi"],
                "arxiv_id": rec["arxiv_id"],
                "url": rec["url"],
                "source_paper": "",
                "source_paper_url": "",
                "discipline": b["clc"],
                "language": rec["language"],
                "doc_type": rec["doc_type"],
                "verification_status": "verifiable_via_public_metadata",
                "verifiable": True,
                "note": f"openalex:{rec['openalex_id']}; doi-resolved={not args.no_verify_doi}",
            })
            got += 1
            if len(records) % 25 == 0:
                checkpoint(records)
                print(f"    ... {b['clc']} {b['language']} 进行中，累计 {len(records)}", flush=True)
        per_clc[b["clc"]] = per_clc.get(b["clc"], 0) + got
        checkpoint(records)
        print(f"[{i+1}/{len(buckets)}] {b['clc']:>3} {b['language']:<7} "
              f"目标 {b['target']:>4} 实得 {got:>4} | 累计 {len(records)}", flush=True)

    checkpoint(records)
    print(f"\n写入 {out} 共 {len(records)} 条真实文献", flush=True)
    print("各 CLC 大类计数：", json.dumps(per_clc, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
