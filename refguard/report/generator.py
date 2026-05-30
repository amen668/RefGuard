"""生成 JSON、Markdown 和可选的 only_used.bib 报告。"""
import json
from pathlib import Path
from typing import Any, List, Optional

from refguard.models import (
    EntryReport,
    ProjectReport,
    RunMetadata,
    resolve_report_status,
)


def _as_serializable(obj: Any) -> Any:
    if hasattr(obj, "__dict__"):
        d = {}
        for k, v in obj.__dict__.items():
            if not k.startswith("_"):
                d[k] = _as_serializable(v)
        return d
    if isinstance(obj, list):
        return [_as_serializable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _as_serializable(v) for k, v in obj.items()}
    return obj


class ReportGenerator:
    """只负责报告序列化，不参与核验业务判断。"""

    def __init__(self) -> None:
        self.entry_reports: List[EntryReport] = []
        self.duplicate_groups: List[Any] = []
        self.missing_citations: List[str] = []
        self.unused_entries: List[str] = []
        self.run_metadata: Optional[RunMetadata] = None

    def set_run_metadata(self, meta: RunMetadata) -> None:
        self.run_metadata = meta

    def add_entry_report(self, report: EntryReport) -> None:
        self.entry_reports.append(report)

    def set_duplicate_groups(self, groups: List[Any]) -> None:
        self.duplicate_groups = groups

    def set_usage(self, missing: List[str], unused: List[str]) -> None:
        self.missing_citations = missing
        self.unused_entries = unused

    def _summary(self) -> dict:
        total = len(self.entry_reports)
        verified = warning = error = 0
        for r in self.entry_reports:
            status = resolve_report_status(r.comparison)
            if status == "verified":
                verified += 1
            elif status == "warning":
                warning += 1
            else:
                error += 1
        return {"total": total, "verified": verified, "warning": warning, "error": error}

    def to_project_report(self) -> ProjectReport:
        return ProjectReport(
            summary=self._summary(),
            entry_reports=self.entry_reports,
            duplicate_groups=self.duplicate_groups,
            missing_citations=self.missing_citations,
            unused_entries=self.unused_entries,
            run_metadata=self.run_metadata,
        )

    def to_json(self) -> dict:
        proj = self.to_project_report()
        entries_out = []
        for er in proj.entry_reports:
            comp = er.comparison
            best_hit = None
            if comp and comp.best_hit:
                best_hit = {
                    "doi": comp.best_hit.fetched_doi,
                    "url": comp.best_hit.fetched_url,
                    "title": comp.best_hit.fetched_title,
                    "authors": comp.best_hit.fetched_authors,
                    "year": comp.best_hit.fetched_year,
                }
            status = resolve_report_status(comp)
            entries_out.append({
                "key": er.entry.key,
                "status": status.value,
                "match_probability": comp.match_probability if comp else 0.0,
                "best_source": comp.source if comp else None,
                "best_hit": best_hit,
                "issues": comp.issues if comp else [],
                "explanations": comp.explanations if comp else None,
            })
        dup_out = []
        for g in proj.duplicate_groups:
            keys = g.entry_keys if hasattr(g, "entry_keys") else [e.key for e in getattr(g, "entries", [])]
            dup_out.append({"group_id": f"dup-{len(dup_out)+1}", "keys": keys, "similarity": getattr(g, "similarity_score", 0)})
        return {
            "summary": proj.summary,
            "run_metadata": _as_serializable(proj.run_metadata) if proj.run_metadata else None,
            "entries": entries_out,
            "duplicates": dup_out,
            "usage": {
                "missing_citations": proj.missing_citations,
                "unused_entries": proj.unused_entries,
            },
        }

    def write_json(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_json(), f, ensure_ascii=False, indent=2)

    def write_markdown(self, path: str | Path) -> None:
        proj = self.to_project_report()
        lines = [
            "## 摘要",
            f"- 总条目: {proj.summary['total']}",
            f"- 已核验: {proj.summary['verified']} | 需复核: {proj.summary['warning']} | 错误: {proj.summary['error']}",
        ]
        if proj.run_metadata:
            lines.append(f"- 配置档: {getattr(proj.run_metadata, 'profile', '')}")
            lines.append(f"- 数据源: {', '.join(getattr(proj.run_metadata, 'sources', []))}")
        lines.append("")
        if proj.duplicate_groups:
            lines.append("## 重复组")
            for g in proj.duplicate_groups:
                keys = g.entry_keys if hasattr(g, "entry_keys") else [e.key for e in getattr(g, "entries", [])]
                sim = getattr(g, "similarity_score", 0)
                lines.append(f"- {', '.join(keys)} (similarity={sim:.2f})")
            lines.append("")
        lines.append("## 有问题条目")
        for er in proj.entry_reports:
            status = resolve_report_status(er.comparison)
            if status == "verified":
                continue
            comp = er.comparison
            if comp is None:
                lines.append(f"### {er.entry.key} ({status.value})")
                lines.append("- 问题: 未生成核验结果")
                lines.append("")
                continue
            lines.append(f"### {er.entry.key} ({status.value})")
            lines.append(f"- 最佳候选: {comp.source} (P={comp.match_probability:.2f})")
            lines.append(f"- 问题: {', '.join(comp.issues)}")
            if comp.best_hit and comp.best_hit.fetched_bibtex:
                lines.append(f"- 建议修复 BibTeX: {comp.best_hit.fetched_bibtex[:200]}...")
            lines.append("")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def write_only_used_bib(self, path: str | Path, entries: List[Any], used_keys: set) -> None:
        """写出仅包含已引用条目的 .bib 文件。"""
        # 解析器不会保留完整原文时，退回到最小 BibTeX。
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for e in entries:
                if e.key not in used_keys:
                    continue
                bib = getattr(e, "raw_bibtex", None) or _entry_to_bibtex(e)
                f.write(bib)
                f.write("\n")


def _entry_to_bibtex(entry: Any) -> str:
    t = entry.entry_type or "misc"
    lines = [f"@{t}{{{entry.key},"]
    if entry.title:
        lines.append(f"  title = {{{entry.title}}},")
    if entry.author:
        lines.append(f"  author = {{{entry.author}}},")
    if entry.year:
        lines.append(f"  year = {{{entry.year}}},")
    if entry.doi:
        lines.append(f"  doi = {{{entry.doi}}},")
    if entry.url:
        lines.append(f"  url = {{{entry.url}}},")
    s = "\n".join(lines)
    if s.endswith(","):
        s = s[:-1]
    return s + "\n}"
