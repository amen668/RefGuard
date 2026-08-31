"""OpenAlex 元数据源。"""
import html
import re
from urllib.parse import quote

import requests

from refguard.core import settings
from refguard.core.cache import cache_manager
from refguard.models import SourceHit

from .base import BaseFetcher, FetcherUnavailableError


class OpenAlexFetcher(BaseFetcher):
    BASE_URL = "https://api.openalex.org"
    source_name = "openalex"
    # OpenAlex 的 DOI/ID singleton lookup 免费，而题名全文搜索按次计费。
    # 强标识命中后停止，可避免每条 DOI 引用再产生一次不必要的付费搜索。
    stop_after_identifier_hit = True

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(
            rate_limit_delay=settings.openalex_rate_limit_delay,
            timeout=getattr(settings, "request_timeout", 30),
        )
        self.api_key = api_key or settings.openalex_api_key
        self._session.headers["User-Agent"] = "RefGuard/1.0 (https://github.com/refguard/refguard)"
        if self.api_key:
            self._session.headers["Authorization"] = f"Bearer {self.api_key}"

    def lookup_by_doi(self, doi: str) -> list[SourceHit]:
        hit = self._fetch_by_doi_cached(doi)
        return [hit] if hit else []

    def _fetch_by_doi_cached(self, doi: str) -> SourceHit | None:
        key = f"openalex:doi:{doi}"
        cached = cache_manager.get(key)
        if cached is not None:
            return cached
        self._wait()
        doi_url = f"https://doi.org/{doi.replace('https://doi.org/', '').strip()}"
        try:
            r = self._session.get(f"{self.BASE_URL}/works/{quote(doi_url, safe='')}", timeout=self._timeout)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            hit = self._parse_work(r.json())
            if hit:
                cache_manager.set(key, hit)
            return hit
        except requests.RequestException as exc:
            raise self._unavailable_error(exc) from exc

    def search_by_title(self, title: str) -> list[SourceHit]:
        title = self._clean_search_title(title)
        if not title:
            return []
        self._wait()
        try:
            r = self._session.get(
                f"{self.BASE_URL}/works",
                params={"search": title, "per-page": 5},
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
        except requests.RequestException as exc:
            raise self._unavailable_error(exc) from exc

    @staticmethod
    def _clean_search_title(title: str) -> str:
        """Remove markup and wildcard punctuation that OpenAlex rejects."""
        # Some imported records contain doubly escaped fragments such as
        # ``&amp;lt;sup&amp;gt;*&amp;lt;/sup&amp;gt;``.
        for _ in range(3):
            decoded = html.unescape(title)
            if decoded == title:
                break
            title = decoded
        title = re.sub(r"<[^>]+>", " ", title)
        title = title.translate(str.maketrans({"*": " ", "?": " "}))
        return " ".join(title.split())

    @staticmethod
    def _unavailable_error(exc: requests.RequestException) -> FetcherUnavailableError:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
        retry_after = response.headers.get("Retry-After") if response is not None else None
        detail = f"HTTP {status}" if status is not None else type(exc).__name__
        if retry_after:
            detail += f", retry_after={retry_after}s"
        return FetcherUnavailableError(f"OpenAlex unavailable: {detail}")

    def _parse_work(self, w: dict) -> SourceHit | None:
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
