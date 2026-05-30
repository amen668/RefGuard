"""参考文献身份核验决策规则。"""
from typing import Optional

from refguard.models import BibEntry, SourceHit, ComparisonResult
from refguard.config import ProfileConfig, get_profile


def decide(
    entry: BibEntry,
    candidates: list[SourceHit],
    probabilities: list[float],
    profile: ProfileConfig,
    explanations: Optional[dict] = None,
    best_hit: Optional[SourceHit] = None,
    best_idx: int = 0,
) -> ComparisonResult:
    """应用阈值和 Top-2 差距规则，返回比较结果。"""
    if not candidates:
        return ComparisonResult(
            entry_key=entry.key,
            is_match=False,
            confidence=0.0,
            issues=["no_candidate_found"],
            source="none",
            match_probability=0.0,
            decision_profile=profile.match_threshold,
            best_hit=None,
            top_hits=[],
            explanations=explanations or {},
        )
    if best_hit is None and candidates:
        best_idx = 0
        best_hit = candidates[0]
    p1 = probabilities[best_idx] if best_idx < len(probabilities) else 0.0
    p2 = 0.0
    if len(probabilities) > 1:
        others = [probabilities[i] for i in range(len(probabilities)) if i != best_idx]
        p2 = max(others) if others else 0.0
    gap = p1 - p2
    issues = []
    if p1 >= profile.match_threshold:
        is_match = True
        confidence = p1
    elif p1 < profile.match_threshold and gap < profile.gap_threshold:
        is_match = False
        confidence = p1
        issues.append("top2_gap_small")
    else:
        is_match = False
        confidence = p1
        if p1 <= 0.3:
            issues.append("low_confidence")
    # 作者完全不匹配且没有 DOI 支撑时，优先按高风险处理。
    if explanations:
        author_sim = explanations.get("author_sim")
        doi_match = explanations.get("doi_match")
        if author_sim is not None and (author_sim < 0.2) and (doi_match == 0 or doi_match is None):
            is_match = False
            if "author_mismatch" not in issues:
                issues.append("author_mismatch")
    return ComparisonResult(
        entry_key=entry.key,
        is_match=is_match,
        confidence=confidence,
        issues=issues,
        source=best_hit.source if best_hit else "none",
        match_probability=p1,
        decision_profile=str(profile.match_threshold),
        best_hit=best_hit,
        top_hits=candidates[:5],
        explanations=explanations or {},
        fetched_title=best_hit.fetched_title if best_hit else "",
        fetched_authors=best_hit.fetched_authors if best_hit else [],
        fetched_year=best_hit.fetched_year if best_hit else "",
        fetched_doi=best_hit.fetched_doi if best_hit else None,
        fetched_url=best_hit.fetched_url if best_hit else "",
        fetched_bibtex=best_hit.fetched_bibtex if best_hit else "",
    )


class DecisionEngine:
    """按配置档封装决策规则。"""

    def __init__(self, profile_name: str = "balanced") -> None:
        self.profile = get_profile(profile_name)

    def run(
        self,
        entry: BibEntry,
        candidates: list[SourceHit],
        probabilities: list[float],
        best_idx: int = 0,
        explanations: Optional[dict] = None,
    ) -> ComparisonResult:
        best = candidates[best_idx] if best_idx < len(candidates) else (candidates[0] if candidates else None)
        return decide(
            entry=entry,
            candidates=candidates,
            probabilities=probabilities,
            profile=self.profile,
            explanations=explanations,
            best_hit=best,
            best_idx=best_idx,
        )
