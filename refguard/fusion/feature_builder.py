"""将参考文献条目和候选结果转换为融合特征。"""
from refguard.models import BibEntry, SourceHit, MatchFeatures
from refguard.utils.normalizer import TextNormalizer

# 强标识查询的先验高于题名检索。
SOURCE_PRIOR = {
    ("crossref", "doi"): 0.95,
    ("crossref", "title_search"): 0.7,
    ("openalex", "doi"): 0.9,
    ("openalex", "title_search"): 0.65,
    ("arxiv", "arxiv_id"): 0.9,
    ("arxiv", "title_search"): 0.6,
    ("semanticscholar", "doi"): 0.9,
    ("semanticscholar", "arxiv_id"): 0.85,
    ("semanticscholar", "title_search"): 0.6,
    ("dblp", "title_search"): 0.6,
}


def _default_prior(source: str, method: str) -> float:
    return SOURCE_PRIOR.get((source, method), 0.5)


class FeatureBuilder:
    """构造融合模型输入特征和解释字段。"""

    @staticmethod
    def build(entry: BibEntry, hit: SourceHit, rank: int, total_candidates: int) -> MatchFeatures:
        title_sim = 0.0
        if entry.title and hit.fetched_title:
            n1 = TextNormalizer.normalize_for_comparison(entry.title)
            n2 = TextNormalizer.normalize_for_comparison(hit.fetched_title)
            title_sim = TextNormalizer.similarity_ratio(n1, n2)
            if len(n1) < 100:
                lev = TextNormalizer.levenshtein_similarity(n1, n2)
                title_sim = max(title_sim, lev)

        bib_authors = entry.authors if entry.authors else TextNormalizer.normalize_author_list(entry.author)
        hit_authors = hit.fetched_authors or []
        author_sim = _author_similarity(bib_authors, hit_authors)

        year_match = 1.0 if (entry.year and hit.fetched_year and entry.year.strip() == hit.fetched_year.strip()) else 0.0
        if not entry.year or not hit.fetched_year:
            year_match = 0.5

        doi_match = 1.0 if (entry.doi and hit.fetched_doi and _norm_doi(entry.doi) == _norm_doi(hit.fetched_doi)) else 0.0
        id_match = 1.0 if (entry.arxiv_id and hit.source == "arxiv" and entry.arxiv_id.strip() in (hit.extra.get("arxiv_id") or hit.fetched_url or "")) else 0.0
        if entry.arxiv_id and hit.fetched_url and ("arxiv" in hit.fetched_url and entry.arxiv_id in hit.fetched_url):
            id_match = 1.0

        source_prior = _default_prior(hit.source, hit.retrieval_method)
        rank_feature = 1.0 - (rank / max(total_candidates, 1))
        title_length = min(len(entry.title or "") / 200.0, 1.0)
        author_count = min(len(bib_authors) / 20.0, 1.0)
        has_doi = 1.0 if entry.doi else 0.0
        has_arxiv_id = 1.0 if entry.arxiv_id else 0.0
        url_match = 0.0
        if entry.url and hit.fetched_url and _norm_doi(entry.url) == _norm_doi(hit.fetched_url):
            url_match = 1.0
        venue_sim = 0.0
        source_score = hit.confidence_raw

        return MatchFeatures(
            title_sim=title_sim,
            author_sim=author_sim,
            year_match=year_match,
            doi_match=doi_match,
            id_match=id_match,
            source_prior=source_prior,
            rank_feature=rank_feature,
            title_length=title_length,
            author_count=author_count,
            has_doi=has_doi,
            has_arxiv_id=has_arxiv_id,
            url_match=url_match,
            venue_sim=venue_sim,
            source_score=source_score,
        )


def _norm_doi(s: str) -> str:
    s = (s or "").strip().lower()
    for p in ("https://doi.org/", "http://doi.org/", "doi:"):
        if s.startswith(p):
            s = s[len(p):]
    return s


def _author_similarity(bib_list: list, hit_list: list) -> float:
    if not bib_list and not hit_list:
        return 1.0
    if not bib_list or not hit_list:
        return 0.0
    norm_bib = [TextNormalizer.normalize_author_name(a) for a in bib_list]
    norm_hit = [TextNormalizer.normalize_author_name(a) for a in hit_list]
    inter = sum(1 for a in norm_bib if a in norm_hit or any(a in h or h in a for h in norm_hit))
    union = len(set(norm_bib) | set(norm_hit))
    return inter / union if union else 0.0


FEATURE_NAMES = [
    "title_sim", "author_sim", "year_match", "doi_match", "id_match",
    "source_prior", "rank_feature", "title_length", "author_count",
    "has_doi", "has_arxiv_id", "url_match", "venue_sim", "source_score",
]
