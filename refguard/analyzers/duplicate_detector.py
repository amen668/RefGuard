"""重复参考文献条目检测。"""
from dataclasses import dataclass
from typing import List, Tuple

from refguard.models import BibEntry
from refguard.utils.normalizer import TextNormalizer


@dataclass
class DuplicateGroup:
    """疑似重复条目组。"""
    entries: List[BibEntry]
    similarity_score: float
    reason: str

    @property
    def entry_keys(self) -> List[str]:
        return [e.key for e in self.entries]


class DuplicateDetector:
    TITLE_SIMILARITY_THRESHOLD = 0.85
    COMBINED_SIMILARITY_THRESHOLD = 0.80

    def __init__(self, title_threshold: float | None = None, combined_threshold: float | None = None) -> None:
        if title_threshold is not None:
            self.TITLE_SIMILARITY_THRESHOLD = title_threshold
        if combined_threshold is not None:
            self.COMBINED_SIMILARITY_THRESHOLD = combined_threshold

    def find_duplicates(self, entries: List[BibEntry]) -> List[DuplicateGroup]:
        duplicates = []
        processed = set()
        for i, entry1 in enumerate(entries):
            if entry1.key in processed:
                continue
            similar_entries = [entry1]
            for entry2 in entries[i + 1 :]:
                if entry2.key in processed:
                    continue
                similarity, reason = self._calculate_similarity(entry1, entry2)
                if similarity >= self.COMBINED_SIMILARITY_THRESHOLD:
                    similar_entries.append(entry2)
                    processed.add(entry2.key)
            if len(similar_entries) > 1:
                processed.add(entry1.key)
                avg_sim = self._calculate_group_similarity(similar_entries)
                reason = self._generate_reason(similar_entries)
                duplicates.append(
                    DuplicateGroup(entries=similar_entries, similarity_score=avg_sim, reason=reason)
                )
        duplicates.sort(key=lambda g: g.similarity_score, reverse=True)
        return duplicates

    def _calculate_similarity(self, entry1: BibEntry, entry2: BibEntry) -> Tuple[float, str]:
        t1 = TextNormalizer.normalize_for_comparison(entry1.title)
        t2 = TextNormalizer.normalize_for_comparison(entry2.title)
        title_sim = TextNormalizer.similarity_ratio(t1, t2)
        if title_sim >= self.TITLE_SIMILARITY_THRESHOLD:
            return title_sim, "题名高度相似"
        author_sim = self._author_similarity(entry1, entry2)
        combined = 0.7 * title_sim + 0.3 * author_sim
        if combined >= self.COMBINED_SIMILARITY_THRESHOLD:
            return combined, f"题名相似度 {title_sim:.0%}，作者相似度 {author_sim:.0%}"
        return combined, ""

    def _author_similarity(self, entry1: BibEntry, entry2: BibEntry) -> float:
        a1 = entry1.authors or TextNormalizer.normalize_author_list(entry1.author)
        a2 = entry2.authors or TextNormalizer.normalize_author_list(entry2.author)
        if not a1 or not a2:
            return 0.0
        n1 = [TextNormalizer.normalize_for_comparison(a) for a in a1]
        n2 = [TextNormalizer.normalize_for_comparison(a) for a in a2]
        matches = sum(1 for x in n1 if any(TextNormalizer.similarity_ratio(x, y) >= 0.8 for y in n2))
        total = len(set(n1) | set(n2))
        return matches / total if total else 0.0

    def _calculate_group_similarity(self, entries: List[BibEntry]) -> float:
        if len(entries) < 2:
            return 1.0
        total, count = 0.0, 0
        for i, e1 in enumerate(entries):
            for e2 in entries[i + 1 :]:
                sim, _ = self._calculate_similarity(e1, e2)
                total += sim
                count += 1
        return total / count if count else 0.0

    def _generate_reason(self, entries: List[BibEntry]) -> str:
        titles = [TextNormalizer.normalize_for_comparison(e.title) for e in entries]
        sims = []
        for i, t1 in enumerate(titles):
            for t2 in titles[i + 1 :]:
                sims.append(TextNormalizer.similarity_ratio(t1, t2))
        avg = sum(sims) / len(sims) if sims else 0.0
        if avg >= 0.95:
            return "题名几乎相同"
        if avg >= 0.85:
            return "题名高度相似"
        return "题名和作者相似"
