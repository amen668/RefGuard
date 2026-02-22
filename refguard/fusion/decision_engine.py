"""DecisionEngine: apply profile (match_threshold, gap_threshold), set status."""
from typing import List, Optional, Tuple

from refguard.models import BibEntry, SourceHit, ComparisonResult
from refguard.config import ProfileConfig, get_profile


def decide(
    entry: BibEntry,
    candidates: List[SourceHit],
    probabilities: List[float],
    profile: ProfileConfig,
    explanations: Optional[dict] = None,
    best_hit: Optional[SourceHit] = None,
    best_idx: int = 0,
) -> ComparisonResult:
    """
    Apply profile thresholds and top-2 gap rule; return ComparisonResult.
    """
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
        status = "verified"
        is_match = True
        confidence = p1
    elif p1 < profile.match_threshold and gap < profile.gap_threshold:
        status = "warning"
        is_match = False
        confidence = p1
        issues.append("top2_gap_small")
    else:
        status = "warning" if p1 > 0.3 else "error"
        is_match = False
        confidence = p1
        if p1 <= 0.3:
            issues.append("low_confidence")
    # Field-level for report
    title_match = getattr(best_hit, "_title_match", None)
    author_match = getattr(best_hit, "_author_match", None)
    year_match = getattr(best_hit, "_year_match", None)
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
    """Thin wrapper: get profile and call decide()."""

    def __init__(self, profile_name: str = "balanced") -> None:
        self.profile = get_profile(profile_name)

    def run(
        self,
        entry: BibEntry,
        candidates: List[SourceHit],
        probabilities: List[float],
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
