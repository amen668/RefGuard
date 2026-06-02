"""DBLP 元数据源。"""
import time
from typing import Any

import requests

from refguard.models import SourceHit
from refguard.core import settings
from .base import BaseFetcher


class DBLPFetcher(BaseFetcher):
    BASE_URL = "https://dblp.org/search/publ/api"
    source_name = "dblp"

    def __init__(self) -> None:
        super().__init__(
            rate_limit_delay=settings.dblp_rate_limit_delay,
            timeout=getattr(settings, "request_timeout", 30),
        )

    def search_by_title(self, title: str) -> list[SourceHit]:
        self._wait()
        try:
            r = self._session.get(
                self.BASE_URL,
                params={"q": title, "format": "json", "h": 5},
                timeout=self._timeout,
                headers={"User-Agent": "RefGuard/1.0"},
            )
            if r.status_code == 429:
                retry_after = r.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    time.sleep(int(retry_after))
                return []
            r.raise_for_status()
            data = r.json()
            return self._parse_response(data)
        except requests.RequestException:
            return []

    def _parse_response(self, data: dict[str, Any]) -> list[SourceHit]:
        out: list[SourceHit] = []
        try:
            hits = data.get("result", {}).get("hits", {}).get("hit", [])
            if not isinstance(hits, list):
                hits = [hits] if hits else []
            for h in hits:
                info = h.get("info", {})
                title = info.get("title", "")
                if title.endswith("."):
                    title = title[:-1]
                authors_data = info.get("authors", {}).get("author", [])
                if isinstance(authors_data, dict):
                    authors_data = [authors_data]
                authors = [a.get("text", "") for a in authors_data if a.get("text")]
                year = str(info.get("year", ""))
                url = info.get("url", "")
                doi = info.get("doi")
                out.append(
                    SourceHit(
                        source=self.source_name,
                        confidence_raw=0.85,
                        retrieval_method="",
                        query="",
                        rank=0,
                        fetched_title=title,
                        fetched_authors=authors,
                        fetched_year=year,
                        fetched_doi=doi if doi else None,
                        fetched_url=url,
                        fetched_bibtex="",
                    )
                )
        except (KeyError, TypeError):
            pass
        return out
