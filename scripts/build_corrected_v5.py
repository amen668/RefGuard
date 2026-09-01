#!/usr/bin/env python3
"""从论文冻结数据和审计清单生成录用后的校正公开数据 V5。

本脚本不修改 V4，不改变标签或划分，也不改 RefGuard 的检索、融合与决策
算法。由于尚未取得 GPTZero 第三方数据的再分发许可，公开 V5 默认且固定
排除该 100 条子集，只发布 1,937 条真实记录和 500 条自建合成负例。
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "citation_dataset_public_v4.json"
DEFAULT_CORRECTIONS = ROOT / "data" / "corrections_v5.json"
DEFAULT_PROVENANCE = ROOT / "data" / "verification_provenance_v5.json"
DEFAULT_OUTPUT = ROOT / "data" / "citation_dataset_public_v5_core.json"
DEFAULT_REPORT = ROOT / "data" / "correction_report_v5.json"

FROZEN_V4_SHA256 = "c43319ccbaee863db87b250f3a3249234ee500ffb58ff2236a3bd12e2da738a7"
CORRECTIONS_SHA256 = "7cfea1250379fbca9f06b6ce94252677aff7c70618644a2d3c71cb12c41cc3ec"
PROVENANCE_SHA256 = "7004917179e39ba0f8f51f40ecc0f1ddd578306130dc07309ea1902ddba19ee9"
GPTZERO_SUBSET = "hallucination_gptzero"
GPTZERO_REPORT = "https://gptzero.me/news/neurips/"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _records(payload: Any) -> list[dict[str, Any]]:
    rows = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("数据必须是记录列表或包含 records 列表的对象")
    return rows


def apply_corrections(
    frozen_payload: Any, correction_payload: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    """严格核对 before 值后应用修正，防止清单误用于其他数据版本。"""
    rows = copy.deepcopy(_records(frozen_payload))
    by_id = {row.get("id"): row for row in rows}
    if len(by_id) != len(rows) or None in by_id:
        raise ValueError("V4 数据存在缺失或重复 ID")

    changes = correction_payload.get("changes")
    expected = correction_payload.get("records_changed")
    if not isinstance(changes, list) or expected != 28 or len(changes) != expected:
        raise ValueError("修正清单必须包含恰好 28 条记录")

    changed_ids: list[str] = []
    for item in changes:
        record_id = item.get("id")
        if record_id not in by_id:
            raise ValueError(f"修正清单中的 ID 不存在：{record_id}")
        row = by_id[record_id]
        for field, values in (item.get("changes") or {}).items():
            before = values.get("before")
            after = values.get("after")
            if row.get(field) != before:
                raise ValueError(
                    f"{record_id}.{field} 的冻结值不匹配："
                    f"期望 {before!r}，实际 {row.get(field)!r}"
                )
            row[field] = after
        changed_ids.append(record_id)

    if len(changed_ids) != len(set(changed_ids)):
        raise ValueError("修正清单包含重复 ID")
    return rows, changed_ids


def apply_verification_provenance(
    rows: list[dict[str, Any]], provenance_payload: dict[str, Any]
) -> int:
    """写入逐条身份审计状态；不接触标签、划分或书目核心字段。"""
    by_id = {row.get("id"): row for row in rows}
    items = provenance_payload.get("records")
    if not isinstance(items, list) or len(items) != 2437:
        raise ValueError("身份审计清单必须包含 2,437 条非 GPTZero 记录")
    ids = [item.get("id") for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("身份审计清单包含重复 ID")

    expected_ids = {
        row["id"] for row in rows if row.get("subset") != GPTZERO_SUBSET
    }
    if set(ids) != expected_ids:
        raise ValueError("身份审计清单与 V4 的非 GPTZero 记录范围不一致")

    allowed_statuses = {
        "doi_metadata_identity_confirmed",
        "openalex_identity_confirmed",
        "official_source_identity_confirmed",
        "synthetic_by_construction",
    }
    for item in items:
        status = item.get("verification_status")
        if status not in allowed_statuses:
            raise ValueError(f"{item.get('id')} 使用了未允许的核验状态：{status}")
        row = by_id[item["id"]]
        row["subset"] = item.get("subset")
        row["verification_status"] = status
        row["note"] = item.get("note")
    return len(items)


def _normalize(value: str) -> str:
    return re.sub(r"[^\w]+", "", (value or "").casefold())


def _cross_split_groups(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> int:
    groups: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for row in rows:
        key = tuple(_normalize(str(row.get(field) or "")) for field in fields)
        if all(key):
            groups[key].add(str(row.get("split") or ""))
    return sum(len(splits) > 1 for splits in groups.values())


def validate_full_dataset(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [row.get("id") for row in rows]
    if len(rows) != 2537 or len(ids) != len(set(ids)):
        raise ValueError("校正完整数据的总量或 ID 唯一性异常")
    labels = Counter(row.get("label") for row in rows)
    splits = Counter(row.get("split") for row in rows)
    if labels != Counter({"real": 1937, "hallucination": 600}):
        raise ValueError(f"校正过程意外改变标签分布：{dict(labels)}")
    if splits != Counter({"test": 2037, "dev": 500}):
        raise ValueError(f"校正过程意外改变划分分布：{dict(splits)}")

    dois = [str(row.get("doi") or "").strip().lower() for row in rows]
    dois = [doi for doi in dois if doi]
    if len(dois) != len(set(dois)):
        raise ValueError("校正数据存在重复 DOI")
    return {
        "total": len(rows),
        "labels": dict(labels),
        "splits": dict(splits),
        "nonempty_doi": len(dois),
        "cross_split_normalized_title_groups": _cross_split_groups(rows, ("title",)),
        "cross_split_normalized_title_author_groups": _cross_split_groups(
            rows, ("title", "authors")
        ),
    }


def build_public_core(rows: list[dict[str, Any]], *, source_hash: str) -> dict[str, Any]:
    public_rows = [copy.deepcopy(row) for row in rows if row.get("subset") != GPTZERO_SUBSET]
    if any(row.get("subset") == GPTZERO_SUBSET for row in public_rows):
        raise AssertionError("公开 V5 仍含 GPTZero 第三方记录")
    if len(public_rows) != 2437:
        raise ValueError(f"公开 V5 核心集应为 2437 条，实际 {len(public_rows)}")

    labels = Counter(row.get("label") for row in public_rows)
    if labels != Counter({"real": 1937, "hallucination": 500}):
        raise ValueError(f"公开 V5 标签分布异常：{dict(labels)}")

    return {
        "_meta": {
            "name": "RefGuard citation-verification benchmark V5 corrected core",
            "version": "v5-corrected-core-20260901",
            "based_on": {
                "dataset": "citation_dataset_public_v4.json",
                "sha256": source_hash,
                "git_tag": "paper-v5-frozen-20260901",
            },
            "scope": (
                "录用后数据质量校正版；不替代论文冻结数据，不能直接用于复现录用稿指标。"
            ),
            "labels": (
                "real = 经 DOI 元数据身份比对或出版方/官方来源确认；"
                "hallucination = 本项目受控合成负例"
            ),
            "third_party_exclusion": {
                "subset": GPTZERO_SUBSET,
                "count": 100,
                "source": GPTZERO_REPORT,
                "reason": "尚未取得第三方数据再分发许可，故不随公开 V5 发布。",
            },
            "known_split_limit": (
                "按 source_paper 分组无跨划分；仍存在少量规范化题名或题名+作者跨划分重复，"
                "不宣称严格实体级零泄漏。"
            ),
        },
        "records": public_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="生成录用后校正公开数据 V5 核心集")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--corrections", type=Path, default=DEFAULT_CORRECTIONS)
    parser.add_argument("--provenance", type=Path, default=DEFAULT_PROVENANCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    input_hash = sha256(args.input)
    correction_hash = sha256(args.corrections)
    provenance_hash = sha256(args.provenance)
    if args.input.resolve() == DEFAULT_INPUT.resolve() and input_hash != FROZEN_V4_SHA256:
        raise ValueError("冻结 V4 的 SHA-256 已变化，拒绝继续")
    if (
        args.corrections.resolve() == DEFAULT_CORRECTIONS.resolve()
        and correction_hash != CORRECTIONS_SHA256
    ):
        raise ValueError("28 条审计修正清单的 SHA-256 已变化，拒绝继续")
    if args.provenance.resolve() == DEFAULT_PROVENANCE.resolve() and provenance_hash != PROVENANCE_SHA256:
        raise ValueError("身份审计清单的 SHA-256 已变化，拒绝继续")

    frozen_payload = json.loads(args.input.read_text(encoding="utf-8"))
    correction_payload = json.loads(args.corrections.read_text(encoding="utf-8"))
    provenance_payload = json.loads(args.provenance.read_text(encoding="utf-8"))
    corrected_rows, changed_ids = apply_corrections(frozen_payload, correction_payload)
    provenance_records = apply_verification_provenance(corrected_rows, provenance_payload)
    full_summary = validate_full_dataset(corrected_rows)
    public_payload = build_public_core(corrected_rows, source_hash=input_hash)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(public_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    output_hash = sha256(args.output)
    try:
        output_display = args.output.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        output_display = args.output.as_posix()
    report = {
        "status": "post_acceptance_data_correction",
        "paper_results_replaced": False,
        "frozen_v4_sha256": input_hash,
        "corrections_sha256": correction_hash,
        "verification_provenance_sha256": provenance_hash,
        "corrected_records": len(changed_ids),
        "verification_provenance_records": provenance_records,
        "corrected_record_ids": changed_ids,
        "full_corrected_internal_summary": full_summary,
        "public_v5_core": {
            "path": output_display,
            "sha256": output_hash,
            "total": len(public_payload["records"]),
            "labels": dict(Counter(row["label"] for row in public_payload["records"])),
            "gptzero_records_distributed": 0,
        },
        "result_boundary": (
            "V5 数据未用于录用稿冻结指标；如报告 V5 指标，必须另行完成并标记复评。"
        ),
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
