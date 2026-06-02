"""参考文献核验服务门面。"""
from typing import Callable, Optional

from refguard.parsers import BibParser, TexParser
from refguard.models import BibEntry, EntryReport, RunMetadata
from refguard.config import get_profile, WorkflowConfig
from refguard.retrieval import CandidateGenerator
from refguard.fusion import FusionModel, DecisionEngine
from refguard.analyzers import DuplicateDetector, UsageChecker
from refguard.report import ReportGenerator
from refguard.core import get_logger

logger = get_logger(__name__)


class VerificationService:
    """编排解析、候选召回、融合判断、重复检测和报告构建。"""

    def __init__(
        self,
        sources: Optional[list[str]] = None,
        profile_name: str = "balanced",
        top_k: int = 8,
        model_dir: Optional[str] = None,
    ) -> None:
        workflow = WorkflowConfig(sources=sources or [])
        self.sources = workflow.get_enabled_sources()
        self.profile = get_profile(profile_name)
        self.top_k = top_k if top_k is not None else self.profile.top_k
        self.candidate_generator = CandidateGenerator(
            sources=self.sources,
            top_k=self.top_k,
        )
        self.fusion_model = FusionModel(model_dir=model_dir)
        self.profile_name = profile_name
        self.decision_engine = DecisionEngine(profile_name=profile_name)
        self.bib_parser = BibParser()
        self.tex_parser = TexParser()
        self.duplicate_detector = DuplicateDetector()

    def _new_report(self) -> ReportGenerator:
        report = ReportGenerator()
        report.set_run_metadata(
            RunMetadata(
                profile=self.profile_name,
                sources=self.sources,
                top_k_candidates=self.top_k,
                match_threshold=self.profile.match_threshold,
                gap_threshold=self.profile.gap_threshold,
            )
        )
        return report

    def _verify_entries(
        self,
        report: ReportGenerator,
        entries: list[BibEntry],
        check_duplicates: bool,
        progress_callback: Optional[Callable[[float, str], None]],
        usage_checker: Optional[UsageChecker],
    ) -> None:
        duplicate_groups = self.duplicate_detector.find_duplicates(entries) if check_duplicates else []
        report.set_duplicate_groups(duplicate_groups)
        for i, entry in enumerate(entries):
            if progress_callback:
                progress_callback((i + 1) / len(entries), f"正在核验 {entry.key}...")
            candidates, _ = self.candidate_generator.generate(entry)
            if not candidates:
                comp = self.decision_engine.run(entry, [], [], 0, None)
                rep = EntryReport(entry=entry, comparison=comp)
            else:
                probs, explanations, top_feat = self.fusion_model.predict_and_explain(entry, candidates)
                best_idx = int(max(range(len(probs)), key=lambda j: probs[j]))
                comp = self.decision_engine.run(
                    entry, candidates, probs, best_idx,
                    explanations={**(explanations[best_idx] if explanations else {}), **(top_feat or {})},
                )
                rep = EntryReport(entry=entry, comparison=comp)
            if usage_checker:
                rep.usage = usage_checker.check_usage(entry)
            report.add_entry_report(rep)

    def _run_verification(
        self,
        bib_content: str,
        check_duplicates: bool,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        usage_checker: Optional[UsageChecker] = None,
    ) -> ReportGenerator:
        report = self._new_report()
        entries = self.bib_parser.parse_content(bib_content)
        if not entries:
            logger.warning("未解析到 BibTeX 条目")
            return report
        self._verify_entries(report, entries, check_duplicates, progress_callback, usage_checker)
        return report

    def verify_bib(
        self,
        bib_content: str,
        check_duplicates: bool = True,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> ReportGenerator:
        """模式 A：只核验 BibTeX。"""
        return self._run_verification(bib_content, check_duplicates, progress_callback)

    def verify_project(
        self,
        bib_content: str,
        tex_content: Optional[str] = None,
        tex_paths: Optional[list[str]] = None,
        check_usage: bool = True,
        check_duplicates: bool = True,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> ReportGenerator:
        """模式 B：核验 BibTeX，并可检查 LaTeX 引用使用情况。"""
        report = self._new_report()
        entries = self.bib_parser.parse_content(bib_content)
        if not entries:
            return report
        usage_checker = None
        if check_usage and (tex_content or tex_paths):
            if tex_paths:
                for p in tex_paths:
                    self.tex_parser.parse_file(p)
            elif tex_content:
                self.tex_parser.parse_content(tex_content)
            usage_checker = UsageChecker(self.tex_parser)
            missing = usage_checker.get_missing_citations(entries)
            unused = [e.key for e in usage_checker.get_unused_entries(entries)]
            report.set_usage(missing, unused)
        self._verify_entries(report, entries, check_duplicates, progress_callback, usage_checker)
        return report
