"""OpenAlex fetcher: search(entry) -> List[SourceHit]. API key required from 2026-02-13."""
import time
from typing import List, Optional
from urllib.parse import quote

import requests

from refguard.models import BibEntry, SourceHit
from refguard.core import settings
from refguard.core.cache import cache_manager
from .base import BaseFetcher


class OpenAlexFetcher(BaseFetcher):
    BASE_URL = "https://api.openalex.org"
    source_name = "openalex"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.openalex_api_key
        self._last = 0.0
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "RefGuard/1.0 (mailto:refguard@localhost)"
        if self.api_key:
            self._session.headers["Authorization"] = f"Bearer {self.api_key}"
        self._timeout = getattr(settings, "request_timeout", 30)
        self._delay = settings.openalex_rate_limit_delay

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
        if entry.title and len(out) < 5:
            hits = self._search_by_title(entry.title, max_results=5)
            for i, h in enumerate(hits):
                h.rank = len(out) + i + 1
                h.retrieval_method = "title_search"
                h.query = entry.title
                out.append(h)
        return out[:10]

    def _fetch_by_doi_cached(self, doi: str) -> Optional[SourceHit]:
        key = f"openalex:doi:{doi}"
        cached = cache_manager.get(key)
        if cached is not None:
            return cached
        self._wait()
        doi_url = f"https://doi.org/{doi.replace('https://doi.org/', '').strip()}"
        try:
            r = self._session.get(f"{self.BASE_URL}/works/{quote(doi_url, safe='')}", timeout=self._timeout)
            r.raise_for_status()
            hit = self._parse_work(r.json())
            if hit:
                cache_manager.set(key, hit)
            return hit
        except requests.RequestException:
            return None

    def _search_by_title(self, title: str, max_results: int = 5) -> List[SourceHit]:
        self._wait()
        try:
            r = self._session.get(
                f"{self.BASE_URL}/works",
                params={"search": title, "per-page": max_results},
                timeout=self._timeout,
            )
            r.raise_for_status()
            data = r.json()
            results = data.get("results", [])
            hits = []
            for w in results:
                h = self._parse_work(w)
                if h:
                    hits.append(h)
            return hits
        except requests.RequestException:
            return []

    def _parse_work(self, w: dict) -> Optional[SourceHit]:
        try:
            title = w.get("title", "")
            if not title:
                return None
            authors = []
            for a in w.get("authorships", []):
                name = a.get("author", {}).get("display_name", "")
                if name:
                    authors.append(name)
            year = w.get("publication_year")
            year_str = str(year) if year else ""
            doi = w.get("doi", "")
            if doi and doi.startswith("https://doi.org/"):
                doi = doi.replace("https://doi.org/", "")
            url = w.get("id", "")
            return SourceHit(
                source=self.source_name,
                confidence_raw=0.9,
                retrieval_method="",
                query="",
                rank=0,
                fetched_title=title,
                fetched_authors=authors,
                fetched_year=year_str,
                fetched_doi=doi or None,
                fetched_url=url,
                fetched_bibtex="",
                extra={"abstract_inverted_index": w.get("abstract_inverted_index")},
            )
        except (KeyError, TypeError):
            return None
