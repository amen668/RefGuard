import unittest
from unittest.mock import Mock, patch

from refguard.config import get_profile
from refguard.fetchers import OpenAlexFetcher
from refguard.fetchers.base import FetcherUnavailableError
from refguard.fusion.decision_engine import decide
from refguard.fusion.feature_builder import FeatureBuilder
from refguard.models import BibEntry, EntryReport, SourceHit, resolve_report_status
from refguard.parsers.bib_parser import BibParser
from refguard.report import ReportGenerator
from refguard.retrieval import CandidateGenerator
from refguard.services import VerificationService


class Bib解析测试(unittest.TestCase):
    def test_解析标准_bibtex_条目(self):
        entries = BibParser().parse_content(
            "@article{demo2024,\n"
            "  title={A Small Test Paper},\n"
            "  author={Zhang, San and Li, Si},\n"
            "  year={2024},\n"
            "  journal={Journal of Tests},\n"
            "  doi={10.1234/demo}\n"
            "}"
        )

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].key, "demo2024")
        self.assertEqual(entries[0].title, "A Small Test Paper")
        self.assertEqual(entries[0].year, "2024")
        self.assertEqual(entries[0].doi, "10.1234/demo")
        self.assertEqual(entries[0].venue, "Journal of Tests")

    def test_从_url_提取_arxiv_编号(self):
        entries = BibParser().parse_content(
            "@misc{demo,\n"
            "  title={An arXiv Paper},\n"
            "  author={Example Author},\n"
            "  year={2023},\n"
            "  url={https://arxiv.org/abs/2301.12345}\n"
            "}"
        )

        self.assertEqual(entries[0].arxiv_id, "2301.12345")


class 特征构建测试(unittest.TestCase):
    def test_doi_和年份匹配会进入特征(self):
        entry = BibEntry(
            key="demo",
            entry_type="article",
            title="A Small Test Paper",
            author="Zhang, San",
            authors=["Zhang, San"],
            year="2024",
            doi="10.1234/demo",
        )
        hit = SourceHit(
            source="crossref",
            confidence_raw=0.95,
            retrieval_method="doi",
            query="10.1234/demo",
            rank=1,
            fetched_title="A Small Test Paper",
            fetched_authors=["Zhang, San"],
            fetched_year="2024",
            fetched_doi="https://doi.org/10.1234/demo",
        )

        features = FeatureBuilder.build(entry, hit, rank=1, total_candidates=1)

        self.assertGreaterEqual(features.title_sim, 0.95)
        self.assertEqual(features.year_match, 1.0)
        self.assertEqual(features.doi_match, 1.0)


class 决策规则测试(unittest.TestCase):
    def test_无候选时返回错误状态(self):
        entry = BibEntry(key="demo", entry_type="article", title="Missing")
        result = decide(entry, [], [], get_profile("balanced"))

        self.assertFalse(result.is_match)
        self.assertIn("no_candidate_found", result.issues)
        self.assertEqual(resolve_report_status(result), "error")

    def test_作者严重不匹配会覆盖高概率(self):
        entry = BibEntry(key="demo", entry_type="article", title="A Paper")
        hit = SourceHit(
            source="openalex",
            confidence_raw=0.9,
            retrieval_method="title_search",
            query="A Paper",
            rank=1,
            fetched_title="A Paper",
            fetched_authors=["Different Author"],
            fetched_year="2024",
        )
        result = decide(
            entry,
            [hit],
            [0.99],
            get_profile("balanced"),
            explanations={"author_sim": 0.0, "doi_match": 0.0},
        )

        self.assertFalse(result.is_match)
        self.assertIn("author_mismatch", result.issues)
        self.assertEqual(resolve_report_status(result), "error")

    def test_报告层和决策层状态一致(self):
        entry = BibEntry(key="demo", entry_type="article", title="Missing")
        comparison = decide(entry, [], [], get_profile("balanced"))
        report = ReportGenerator()
        report.add_entry_report(EntryReport(entry=entry, comparison=comparison))

        self.assertEqual(report.to_json()["entries"][0]["status"], resolve_report_status(comparison))
        self.assertEqual(report.to_json()["summary"]["error"], 1)


class 服务编排测试(unittest.TestCase):
    def test_连续核验不会复用上一次报告条目(self):
        svc = VerificationService(sources=["unknown"], profile_name="balanced")
        first = svc.verify_bib("@article{a,title={A},author={A},year={2024}}")
        second = svc.verify_bib("@article{b,title={B},author={B},year={2024}}")

        self.assertEqual([r.entry.key for r in first.entry_reports], ["a"])
        self.assertEqual([r.entry.key for r in second.entry_reports], ["b"])

    def test_未知数据源会跳过且不抛异常(self):
        entry = BibEntry(key="demo", entry_type="article", title="A Paper")
        candidates, per_source = CandidateGenerator(["unknown"], top_k=3).generate(entry)

        self.assertEqual(candidates, [])
        self.assertEqual(per_source["unknown"], 0)


class OpenAlex费用控制测试(unittest.TestCase):
    @staticmethod
    def _entry(doi: str = "10.1234/demo") -> BibEntry:
        return BibEntry(
            key="demo",
            entry_type="article",
            title="A Small Test Paper",
            author="Zhang, San",
            authors=["Zhang, San"],
            year="2024",
            doi=doi,
        )

    @staticmethod
    def _hit(doi: str = "10.1234/demo") -> SourceHit:
        return SourceHit(
            source="openalex",
            confidence_raw=0.9,
            retrieval_method="",
            query="",
            rank=0,
            fetched_title="A Small Test Paper",
            fetched_authors=["Zhang, San"],
            fetched_year="2024",
            fetched_doi=doi,
        )

    def test_doi_命中后不再执行收费题名搜索(self):
        fetcher = OpenAlexFetcher(api_key="")
        with (
            patch.object(fetcher, "lookup_by_doi", return_value=[self._hit()]) as doi_lookup,
            patch.object(fetcher, "search_by_title", return_value=[self._hit()]) as title_search,
        ):
            hits = fetcher.search(self._entry())

        doi_lookup.assert_called_once_with("10.1234/demo")
        title_search.assert_not_called()
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].retrieval_method, "doi")

    def test_doi_无命中时仍回退到题名搜索(self):
        fetcher = OpenAlexFetcher(api_key="")
        with (
            patch.object(fetcher, "lookup_by_doi", return_value=[]) as doi_lookup,
            patch.object(fetcher, "search_by_title", return_value=[self._hit(doi="")]) as title_search,
        ):
            hits = fetcher.search(self._entry())

        doi_lookup.assert_called_once_with("10.1234/demo")
        title_search.assert_called_once_with("A Small Test Paper")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].retrieval_method, "title_search")

    def test_openalex_不可用时不会被静默转换为空候选(self):
        fetcher = OpenAlexFetcher(api_key="")
        with patch.object(
            fetcher,
            "lookup_by_doi",
            side_effect=FetcherUnavailableError("OpenAlex unavailable: HTTP 429"),
        ), self.assertRaises(FetcherUnavailableError):
            fetcher.search(self._entry())

    def test_题名含问号时在请求前移除通配符(self):
        fetcher = OpenAlexFetcher(api_key="")
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"results": []}
        with (
            patch.object(fetcher, "_wait"),
            patch.object(fetcher._session, "get", return_value=response) as request,
        ):
            fetcher.search_by_title("Can machine learning improve delta hedging?")

        self.assertEqual(
            request.call_args.kwargs["params"],
            {"search": "Can machine learning improve delta hedging", "per-page": 5},
        )

    def test_题名中的双重转义_html_和孤立星号会被清理(self):
        title = "追踪研究 &amp;lt;sup&amp;gt;*&amp;lt;/sup&amp;gt;"
        self.assertEqual(OpenAlexFetcher._clean_search_title(title), "追踪研究")

    def test_清理后为空的题名不发起收费请求(self):
        fetcher = OpenAlexFetcher(api_key="")
        with patch.object(fetcher._session, "get") as request:
            self.assertEqual(fetcher.search_by_title("<sup>*?</sup>"), [])
        request.assert_not_called()

    def test_候选生成器遇到数据源不可用时中止(self):
        generator = CandidateGenerator(["openalex"], top_k=3)
        fetcher = OpenAlexFetcher(api_key="")
        generator._fetchers["openalex"] = fetcher
        with patch.object(
            fetcher,
            "lookup_by_doi",
            side_effect=FetcherUnavailableError("OpenAlex unavailable: HTTP 429"),
        ), self.assertRaises(FetcherUnavailableError):
            generator.generate(self._entry())


if __name__ == "__main__":
    unittest.main()
