"""参考文献身份核验决策规则。"""
from typing import Optional

from refguard.models import BibEntry, SourceHit, ComparisonResult
from refguard.config import ProfileConfig, get_profile

# 非标准文献类型（书籍/学位论文/技术报告等），公开元数据源覆盖较弱。
NONSTANDARD_TYPES = {
    "book", "inbook", "incollection", "booklet", "manual",
    "phdthesis", "mastersthesis", "thesis", "techreport", "report",
}


def _has_cjk(text: str) -> bool:
    """题名是否含中日韩文字，用于识别中文文献。"""
    return any("一" <= ch <= "鿿" for ch in (text or ""))


def adaptive_threshold(
    profile: ProfileConfig,
    entry: BibEntry,
    candidates: list[SourceHit],
    explanations: Optional[dict],
) -> float:
    """按可获得证据的强度动态计算判定阈值。

    设计原则：阈值随**证据强度**浮动，而非随字段是否存在浮动（后者会退化为
    has_doi 之类的构造捷径）。证据越强/越互相佐证，越容易判定为真实（降阈值）；
    作者严重不符则抬高门槛。非标准文献仅在题名强匹配时适度放宽，补偿其在公开
    源中的覆盖劣势，避免误伤真实但难检索的条目。
    """
    thr = profile.match_threshold
    ex = explanations or {}
    doi_match = ex.get("doi_match") or 0
    author_sim = ex.get("author_sim")
    title_sim = ex.get("title_sim") or 0.0
    year_match = ex.get("year_match") or 0.0

    # 1) 引用 DOI 解析到同一候选：最强证据，降阈值。
    if doi_match and doi_match >= 1.0:
        thr -= profile.w_doi_match
    # 2) 题名+年份+作者全面一致：降阈值。
    if title_sim >= 0.9 and year_match >= 1.0 and (author_sim or 0) >= 0.6:
        thr -= profile.w_full_agree
    # 3) 多个独立数据源同时返回候选（证据冗余/互补）：降阈值。
    distinct_sources = len({c.source for c in candidates if c.source})
    if distinct_sources >= profile.evidence_min_sources:
        thr -= profile.w_evidence
    # 4) 非标准文献且题名强匹配：补偿覆盖劣势，适度降阈值。
    if entry.entry_type and entry.entry_type.lower() in NONSTANDARD_TYPES and title_sim >= 0.85:
        thr -= profile.w_nonstd
    # 5) 作者严重不符且无 DOI 佐证：抬高门槛。
    if author_sim is not None and author_sim < 0.2 and not (doi_match and doi_match >= 1.0):
        thr += profile.w_author_penalty

    return max(profile.adapt_floor, min(profile.adapt_ceil, thr))


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
    # 自适应档按证据强度计算有效阈值，否则用配置档固定阈值。
    if profile.adaptive:
        eff_threshold = adaptive_threshold(profile, entry, candidates, explanations)
    else:
        eff_threshold = profile.match_threshold
    if p1 >= eff_threshold:
        is_match = True
        confidence = p1
    elif p1 < eff_threshold and gap < profile.gap_threshold:
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
        decision_profile=f"{eff_threshold:.3f}",
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
