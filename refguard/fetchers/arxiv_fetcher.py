"""arXiv 元数据源。"""
import re
import xml.etree.ElementTree as ET
from typing import Optional

import requests

from refguard.models import SourceHit
from refguard.core import settings
from refguard.core.cache import cache_manager
from .base import BaseFetcher


class ArxivFetcher(BaseFetcher):
    API_BASE = "http://export.arxiv.org/api/query"
    source_name = "arxiv"

    def __init__(self) -> None:
        super().__init__(
            rate_limit_delay=settings.arxiv_rate_limit_delay,
            timeout=getattr(settings, "request_timeout", 30),
        )

    def lookup_by_arxiv_id(self, arxiv_id: str) -> list[SourceHit]:
        aid = re.sub(r"^arXiv:", "", arxiv_id, flags=re.IGNORECASE).strip()
        hit = self._fetch_by_id_cached(aid)
        return [hit] if hit else []

    def _fetch_by_id_cached(self, arxiv_id: str) -> Optional[SourceHit]:
        key = f"arxiv:id:{arxiv_id}"
        cached = cache_manager.get(key)
        if cached is not None:
            return cached
        self._wait()
        try:
            r = self._session.get(
                self.API_BASE,
                params={"id_list": arxiv_id, "max_results": 1},
                timeout=self._timeout,
                headers={"User-Agent": "RefGuard/1.0 (https://github.com/refguard/refguard)"},
            )
            r.raise_for_status()
            results = self._parse_response(r.text)
            if not results:
                return None
            hit = self._meta_to_hit(results[0])
            cache_manager.set(key, hit)
            return hit
        except requests.RequestException:
            return None

    def search_by_title(self, title: str) -> list[SourceHit]:
        self._wait()
        clean = re.sub(r"[^\w\s]", " ", title)
        clean = re.sub(r"\s+", " ", clean).strip()
        q = f'ti:"{clean}"'
        try:
            r = self._session.get(
                self.API_BASE,
                params={"search_query": q, "max_results": 5, "sortBy": "relevance", "sortOrder": "descending"},
                timeout=self._timeout,
                headers={"User-Agent": "RefGuard/1.0 (https://github.com/refguard/refguard)"},
            )
            r.raise_for_status()
            results = self._parse_response(r.text)
            return [self._meta_to_hit(m) for m in results]
        except requests.RequestException:
            return []

    def _parse_response(self, xml_content: str) -> list:
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError:
            return []
        entries = root.findall("atom:entry", ns)
        result = []
        for entry in entries:
            meta = self._parse_entry(entry, ns)
            if meta:
                result.append(meta)
        return result

    def _parse_entry(self, entry: ET.Element, ns: dict) -> Optional[dict]:
        id_elem = entry.find("atom:id", ns)
        if id_elem is None or id_elem.text is None:
            return None
        abs_url = id_elem.text.strip()
        m = re.search(r"arxiv\.org/abs/(.+)$", abs_url)
        arxiv_id = m.group(1) if m else ""
        title_elem = entry.find("atom:title", ns)
        title = self._clean(title_elem.text) if title_elem is not None and title_elem.text else ""
        summary_elem = entry.find("atom:summary", ns)
        abstract = self._clean(summary_elem.text) if summary_elem is not None and summary_elem.text else ""
        authors = []
        for author_elem in entry.findall("atom:author", ns):
            name_elem = author_elem.find("atom:name", ns)
            if name_elem is not None and name_elem.text:
                authors.append(name_elem.text.strip())
        published_elem = entry.find("atom:published", ns)
        published = published_elem.text.strip() if published_elem is not None and published_elem.text else ""
        year = str(published[:4]) if len(published) >= 4 else ""
        doi_elem = entry.find("arxiv:doi", ns)
        doi = doi_elem.text.strip() if doi_elem is not None and doi_elem.text else ""
        return {
            "arxiv_id": arxiv_id,
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "year": year,
            "doi": doi,
            "abs_url": abs_url,
        }

    def _clean(self, text: str) -> str:
        if not text:
            return ""
        return re.sub(r"\s+", " ", text).strip()

    def _meta_to_hit(self, m: dict) -> SourceHit:
        return SourceHit(
            source=self.source_name,
            confidence_raw=0.9,
            retrieval_method="",
            query="",
            rank=0,
            fetched_title=m.get("title", ""),
            fetched_authors=m.get("authors", []),
            fetched_year=m.get("year", ""),
            fetched_doi=m.get("doi") or None,
            fetched_url=m.get("abs_url", ""),
            fetched_bibtex="",
        )
