"""DOI 内容协商元数据源，跨注册商解析任意 DOI。

Crossref/arXiv/DBLP 等以期刊与会议论文为主，而学位论文、技术报告、数据集、
中文文献等大量使用非 Crossref 注册商的 DOI（DataCite、Airiti、mEDRA 等），
这些 DOI 在以 Crossref 为主的检索中解析不到，导致真实文献因 doi_match=0 被
误判为幻觉。本源通过 doi.org 内容协商（Accept: CSL-JSON）按 DOI 精确解析，
不区分注册商，一次覆盖 DataCite/Airiti 等多家机构，补充非标准与中文文献。

已知盲区：ISTIC（中信所/万方）注册的中文 DOI 不提供 CSL 元数据，内容协商
返回 404，需另接万方 API，记为局限。
"""
import time
import urllib.parse
from typing import Any

import requests

from refguard.models import SourceHit
from refguard.core import settings
from .base import BaseFetcher


class DOIContentNegotiationFetcher(BaseFetcher):
    BASE_URL = "https://doi.org"
    ACCEPT = "application/vnd.citationstyles.csl+json"
    source_name = "doicn"

    def __init__(self) -> None:
        super().__init__(
            rate_limit_delay=getattr(settings, "doicn_rate_limit_delay", 1.0),
            timeout=getattr(settings, "request_timeout", 30),
        )

    def lookup_by_doi(self, doi: str) -> list[SourceHit]:
        doi = self._clean_doi(doi)
        if not doi:
            return []
        url = f"{self.BASE_URL}/{urllib.parse.quote(doi)}"
        # 持续负载下 doi.org 内容协商易限流/超时；对瞬时失败重试，避免真实
        # 文献因偶发解析失败被误判（404/406 是确定性不存在，不重试）。
        for attempt in range(3):
            self._wait()
            try:
                r = self._session.get(
                    url,
                    timeout=self._timeout,
                    headers={"Accept": self.ACCEPT, "User-Agent": "RefGuard/1.0"},
                )
                if r.status_code in (404, 406):
                    return []
                if r.status_code == 429:
                    retry_after = r.headers.get("Retry-After")
                    delay = int(retry_after) if (retry_after and retry_after.isdigit()) else 2 * (attempt + 1)
                    time.sleep(min(delay, 10))
                    continue
                if r.status_code >= 500:
                    time.sleep(2 * (attempt + 1))
                    continue
                r.raise_for_status()
                hit = self._parse_csl(r.json())
                return [hit] if hit else []
            except (requests.RequestException, ValueError):
                time.sleep(1.5 * (attempt + 1))
                continue
        return []

    @staticmethod
    def _clean_doi(doi: str) -> str:
        s = (doi or "").strip()
        for p in ("https://doi.org/", "http://doi.org/", "doi:"):
            if s.lower().startswith(p):
                s = s[len(p):]
        # 去掉出版商链接残留的 query/fragment（如 ?locatt=mode:legacy、#sec1），
        # 否则会导致本可解析的 DOI 解析失败。
        for sep in ("?", "#"):
            if sep in s:
                s = s.split(sep, 1)[0]
        return s

    def _parse_csl(self, d: dict[str, Any]) -> SourceHit | None:
        try:
            title = d.get("title", "")
            if isinstance(title, list):
                title = title[0] if title else ""
            if not title:
                return None
            authors = []
            for a in d.get("author", []) or []:
                name = a.get("literal") or " ".join(
                    x for x in (a.get("given"), a.get("family")) if x
                )
                if name:
                    authors.append(name)
            issued = (d.get("issued", {}) or {}).get("date-parts", [[None]])
            year = ""
            if issued and issued[0] and issued[0][0]:
                year = str(issued[0][0])
            doi = d.get("DOI", "") or ""
            url = d.get("URL", "") or (f"https://doi.org/{doi}" if doi else "")
            return SourceHit(
                source=self.source_name,
                confidence_raw=0.85,
                retrieval_method="",
                query="",
                rank=0,
                fetched_title=str(title),
                fetched_authors=authors,
                fetched_year=year,
                fetched_doi=doi if doi else None,
                fetched_url=url,
                fetched_bibtex="",
                extra={"csl_type": d.get("type", "")},
            )
        except (KeyError, TypeError, IndexError):
            return None
