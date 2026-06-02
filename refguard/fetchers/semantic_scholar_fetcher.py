"""Semantic Scholar 元数据源。"""
from typing import Optional

import requests

from refguard.models import SourceHit
from refguard.core import settings
from refguard.core.cache import cache_manager
from .base import BaseFetcher


class SemanticScholarFetcher(BaseFetcher):
    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    source_name = "semanticscholar"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(
            rate_limit_delay=settings.semantic_scholar_rate_limit_delay,
            timeout=getattr(settings, "request_timeout", 30),
        )
        self.api_key = api_key or settings.semantic_scholar_api_key
        if self.api_key:
            self._session.headers["x-api-key"] = self.api_key
        self._session.headers["User-Agent"] = "RefGuard/1.0"

    def _query_plan(self, entry):
        plan = []
        if entry.doi:
            plan.append(("doi", entry.doi, self.lookup_by_doi))
        if entry.arxiv_id and not entry.doi:
            plan.append(("arxiv_id", entry.arxiv_id, self.lookup_by_arxiv_id))
        plan.append(("title_search", entry.title, self.search_by_title))
        return plan

    def lookup_by_doi(self, doi: str) -> list[SourceHit]:
        hit = self._fetch_by_doi_cached(doi)
        return [hit] if hit else []

    def lookup_by_arxiv_id(self, arxiv_id: str) -> list[SourceHit]:
        hit = self._fetch_by_arxiv_cached(arxiv_id)
        return [hit] if hit else []

    def _fetch_by_doi_cached(self, doi: str) -> Optional[SourceHit]:
        key = f"s2:doi:{doi}"
        cached = cache_manager.get(key)
        if cached is not None:
            return cached
        self._wait()
        try:
            r = self._session.get(
                f"{self.BASE_URL}/paper/DOI:{doi}",
                params={"fields": "title,authors,year,abstract,paperId,citationCount,url"},
                timeout=self._timeout,
            )
            r.raise_for_status()
            hit = self._parse_paper(r.json())
            if hit:
                cache_manager.set(key, hit)
            return hit
        except requests.RequestException:
            return None

    def _fetch_by_arxiv_cached(self, arxiv_id: str) -> Optional[SourceHit]:
        key = f"s2:arxiv:{arxiv_id}"
        cached = cache_manager.get(key)
        if cached is not None:
            return cached
        self._wait()
        try:
            r = self._session.get(
                f"{self.BASE_URL}/paper/ARXIV:{arxiv_id}",
                params={"fields": "title,authors,year,abstract,paperId,citationCount,url"},
                timeout=self._timeout,
            )
            r.raise_for_status()
            hit = self._parse_paper(r.json())
            if hit:
                cache_manager.set(key, hit)
            return hit
        except requests.RequestException:
            return None

    def search_by_title(self, title: str) -> list[SourceHit]:
        self._wait()
        try:
            r = self._session.get(
                f"{self.BASE_URL}/paper/search",
                params={"query": title, "limit": 1, "fields": "title,authors,year,abstract,paperId,citationCount,url"},
                timeout=self._timeout,
            )
            r.raise_for_status()
            data = r.json()
            papers = data.get("data", [])
            if not papers:
                return []
            hit = self._parse_paper(papers[0])
            return [hit] if hit else []
        except requests.RequestException:
            return []

    def _parse_paper(self, p: dict) -> Optional[SourceHit]:
        try:
            title = p.get("title", "")
            if not title:
                return None
            authors = [a.get("name", "") for a in p.get("authors", []) if a.get("name")]
            year = p.get("year")
            year_str = str(year) if year else ""
            url = p.get("url", "")
            return SourceHit(
                source=self.source_name,
                confidence_raw=0.9,
                retrieval_method="",
                query="",
                rank=0,
                fetched_title=title,
                fetched_authors=authors,
                fetched_year=year_str,
                fetched_doi=None,
                fetched_url=url,
                fetched_bibtex="",
            )
        except (KeyError, TypeError):
            return None
