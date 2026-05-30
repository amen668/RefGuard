"""Crossref 元数据源。"""

import requests

from refguard.models import SourceHit
from refguard.core import settings
from refguard.core.cache import cache_manager
from .base import BaseFetcher


class CrossrefFetcher(BaseFetcher):
    BASE_URL = "https://api.crossref.org/works"
    source_name = "crossref"

    def __init__(self, mailto: str | None = None) -> None:
        super().__init__(
            rate_limit_delay=settings.crossref_rate_limit_delay,
            timeout=getattr(settings, "request_timeout", 30),
        )
        self.mailto = mailto or settings.crossref_mailto

    def _headers(self) -> dict:
        return {
            "User-Agent": (
                f"RefGuard/1.0 (mailto:{self.mailto})"
                if self.mailto
                else "RefGuard/1.0 (https://github.com/refguard/refguard)"
            ),
            "Accept": "application/json",
        }

    def lookup_by_doi(self, doi: str) -> list[SourceHit]:
        hit = self._fetch_by_doi_cached(doi)
        return [hit] if hit else []

    def _fetch_by_doi_cached(self, doi: str) -> SourceHit | None:
        key = f"crossref:doi:{doi}"
        cached = cache_manager.get(key)
        if cached is not None:
            return cached
        self._wait()
        doi_clean = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
        try:
            r = self._session.get(
                f"{self.BASE_URL}/{doi_clean}",
                headers=self._headers(),
                timeout=self._timeout,
            )
            r.raise_for_status()
            data = r.json()
            if data.get("status") != "ok":
                return None
            hit = self._parse_item(data.get("message", {}), 1.0)
            if hit:
                cache_manager.set(key, hit)
            return hit
        except requests.RequestException:
            return None

    def search_by_title(self, title: str) -> list[SourceHit]:
        self._wait()
        try:
            r = self._session.get(
                self.BASE_URL,
                params={
                    "query.title": title,
                    "rows": 5,
                    "select": "title,author,published-print,published-online,DOI,publisher,container-title,abstract",
                },
                headers=self._headers(),
                timeout=self._timeout,
            )
            r.raise_for_status()
            data = r.json()
            items = data.get("message", {}).get("items", [])
            hits = []
            for i, it in enumerate(items):
                h = self._parse_item(it, 0.9 - i * 0.1)
                if h:
                    hits.append(h)
            return hits
        except requests.RequestException:
            return []

    def _parse_item(self, item: dict, confidence: float) -> SourceHit | None:
        try:
            titles = item.get("title", [])
            title = titles[0] if titles else ""
            if not title:
                return None
            authors = []
            for a in item.get("author", []):
                fam = a.get("family", "")
                given = a.get("given", "")
                if fam:
                    authors.append(f"{given} {fam}".strip() if given else fam)
            year = ""
            for field in ("published-print", "published-online", "created"):
                parts = item.get(field, {}).get("date-parts", [[]])
                if parts and parts[0]:
                    year = str(parts[0][0])
                    break
            doi = item.get("DOI", "")
            url = f"https://doi.org/{doi}" if doi else ""
            return SourceHit(
                source=self.source_name,
                confidence_raw=confidence,
                retrieval_method="",
                query="",
                rank=0,
                fetched_title=title,
                fetched_authors=authors,
                fetched_year=year,
                fetched_doi=doi or None,
                fetched_url=url,
                fetched_bibtex="",
            )
        except (KeyError, IndexError, TypeError):
            return None
