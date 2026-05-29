"""MatchFeatures: feature vector for evidence fusion."""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MatchFeatures:
    """Features for fusion model input and explainability."""
    title_sim: float = 0.0
    author_sim: float = 0.0
    year_match: float = 0.0  # 0/1/unknown
    doi_match: float = 0.0
    id_match: float = 0.0  # arxiv_id match
    source_prior: float = 0.0
    rank_feature: float = 0.0
    title_length: float = 0.0
    author_count: float = 0.0
    has_doi: float = 0.0
    has_arxiv_id: float = 0.0
    url_match: float = 0.0
    # Optional / extended
    venue_sim: float = 0.0
    source_score: float = 0.0  # API relevance if available
    extra: dict[str, Any] = field(default_factory=dict)

    def to_vector(self) -> list[float]:
        """Ordered list for sklearn / fusion model (same order as FEATURE_NAMES)."""
        return [
            self.title_sim,
            self.author_sim,
            self.year_match,
            self.doi_match,
            self.id_match,
            self.source_prior,
            self.rank_feature,
            self.title_length,
            self.author_count,
            self.has_doi,
            self.has_arxiv_id,
            self.url_match,
            self.venue_sim,
            self.source_score,
        ]


FEATURE_NAMES = [
    "title_sim", "author_sim", "year_match", "doi_match", "id_match",
    "source_prior", "rank_feature", "title_length", "author_count",
    "has_doi", "has_arxiv_id", "url_match", "venue_sim", "source_score",
]
