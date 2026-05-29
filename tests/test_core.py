import unittest

from refguard.config import get_profile
from refguard.fusion.decision_engine import decide
from refguard.fusion.feature_builder import FeatureBuilder
from refguard.models import BibEntry, SourceHit
from refguard.parsers.bib_parser import BibParser


class BibParserTest(unittest.TestCase):
    def test_parse_basic_bibtex_entry(self):
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

    def test_extract_arxiv_id_from_url(self):
        entries = BibParser().parse_content(
            "@misc{demo,\n"
            "  title={An arXiv Paper},\n"
            "  author={Example Author},\n"
            "  year={2023},\n"
            "  url={https://arxiv.org/abs/2301.12345}\n"
            "}"
        )

        self.assertEqual(entries[0].arxiv_id, "2301.12345")


class FeatureBuilderTest(unittest.TestCase):
    def test_doi_and_year_matches_are_encoded(self):
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


class DecisionEngineTest(unittest.TestCase):
    def test_no_candidate_is_error(self):
        entry = BibEntry(key="demo", entry_type="article", title="Missing")
        result = decide(entry, [], [], get_profile("balanced"))

        self.assertFalse(result.is_match)
        self.assertIn("no_candidate_found", result.issues)

    def test_author_mismatch_overrides_probability(self):
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


if __name__ == "__main__":
    unittest.main()
