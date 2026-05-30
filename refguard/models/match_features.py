"""证据融合使用的特征向量。"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MatchFeatures:
    """融合模型输入和解释用特征。"""
    title_sim: float = 0.0
    author_sim: float = 0.0
    year_match: float = 0.0
    doi_match: float = 0.0
    id_match: float = 0.0
    source_prior: float = 0.0
    rank_feature: float = 0.0
    title_length: float = 0.0
    author_count: float = 0.0
    has_doi: float = 0.0
    has_arxiv_id: float = 0.0
    url_match: float = 0.0
    # 可选扩展特征。
    venue_sim: float = 0.0
    source_score: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    def to_vector(self) -> list[float]:
        """按固定顺序输出特征列表。"""
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
