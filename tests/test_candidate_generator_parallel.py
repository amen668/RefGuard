import threading
from unittest.mock import patch

from refguard.models import BibEntry, SourceHit
from refguard.retrieval.candidate_generator import CandidateGenerator


def test_sources_are_queried_in_parallel_and_merged_in_configured_order():
    barrier = threading.Barrier(2)

    class Fetcher:
        def __init__(self, source: str) -> None:
            self.source = source

        def search(self, entry: BibEntry) -> list[SourceHit]:
            barrier.wait(timeout=1)
            return [
                SourceHit(
                    source=self.source,
                    confidence_raw=1.0,
                    retrieval_method="title",
                    query=entry.title,
                    rank=1,
                    fetched_title=entry.title,
                )
            ]

    fetchers = {name: Fetcher(name) for name in ("second", "first")}
    with patch(
        "refguard.retrieval.candidate_generator.get_fetcher",
        side_effect=lambda name: fetchers[name],
    ):
        hits, counts = CandidateGenerator(["second", "first"]).generate(
            BibEntry(key="demo", entry_type="article", title="Example")
        )

    assert [hit.source for hit in hits] == ["second", "first"]
    assert counts == {"second": 1, "first": 1}
