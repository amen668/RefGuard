"""Semantic Scholar fetcher: search(entry) -> List[SourceHit]."""
import time
from typing import List, Optional

import requests

from refguard.models import BibEntry, SourceHit
from refguard.core import settings
from refguard.core.cache import cache_manager
from .base import BaseFetcher


class SemanticScholarFetcher(BaseFetcher):
    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    source_name = "semanticscholar"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.semantic_scholar_api_key
        self._last = 0.0
        self._session = requests.Session()
        if self.api_key:
            self._session.headers["x-api-key"] = self.api_key
        self._session.headers["User-Agent"] = "RefGuard/1.0"
        self._timeout = getattr(settings, "request_timeout", 30)
        self._delay = settings.semantic_scholar_rate_limit_delay

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last
        if elapsed < self._delay:
            time.sleep(self._delay - elapsed)
        self._last = time.monotonic()

    def search(self, entry: BibEntry) -> List[SourceHit]:
        out: List[SourceHit] = []
        if entry.doi:
            hit = self._fetch_by_doi_cached(entry.doi)
            if hit:
                hit.rank = 1
                hit.retrieval_method = "doi"
                hit.query = entry.doi
                out.append(hit)
        if entry.arxiv_id and not out:
            hit = self._fetch_by_arxiv_cached(entry.arxiv_id)
            if hit:
                hit.rank = 1
                hit.retrieval_method = "arxiv_id"
                hit.query = entry.arxiv_id
                out.append(hit)
        if entry.title and len(out) < 5:
            hit = self._search_by_title(entry.title)
            if hit:
                hit.rank = len(out) + 1
                hit.retrieval_method = "title_search"
                hit.query = entry.title
                out.append(hit)
        return out[:10]

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

    def _search_by_title(self, title: str) -> Optional[SourceHit]:
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
                return None
            return self._parse_paper(papers[0])
        except requests.RequestException:
            return None

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
