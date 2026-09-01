import hashlib
import json
from collections import Counter
from pathlib import Path

from scripts.build_corrected_v5 import (
    apply_corrections,
    apply_verification_provenance,
    build_public_core,
)
from scripts.make_public_dataset import build_public_dataset


ROOT = Path(__file__).resolve().parents[1]


def test_corrected_v5_changes_exactly_28_records_and_excludes_gptzero():
    frozen_path = ROOT / "data" / "citation_dataset_public_v4.json"
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    corrections = json.loads((ROOT / "data" / "corrections_v5.json").read_text(encoding="utf-8"))
    provenance = json.loads(
        (ROOT / "data" / "verification_provenance_v5.json").read_text(encoding="utf-8")
    )

    corrected, changed_ids = apply_corrections(frozen, corrections)
    assert apply_verification_provenance(corrected, provenance) == 2437
    public = build_public_core(
        corrected,
        source_hash=hashlib.sha256(frozen_path.read_bytes()).hexdigest(),
    )

    assert len(changed_ids) == len(set(changed_ids)) == 28
    assert len(public["records"]) == 2437
    assert Counter(row["label"] for row in public["records"]) == {
        "real": 1937,
        "hallucination": 500,
    }
    assert all(row.get("subset") != "hallucination_gptzero" for row in public["records"])
    assert all(
        row["verification_status"]
        in {
            "doi_metadata_identity_confirmed",
            "openalex_identity_confirmed",
            "official_source_identity_confirmed",
            "synthetic_by_construction",
        }
        for row in public["records"]
    )
    fixed = next(row for row in public["records"] if row["id"] == "R-TP-EN-01559")
    assert fixed["title"] == "LLM-Supported Manufacturing Mapping Generation"


def test_generic_public_export_fails_closed_for_unlicensed_third_party_subset():
    payload = {
        "records": [
            {"id": "R1", "label": "real", "title": "Public metadata"},
            {
                "id": "H1",
                "label": "hallucination",
                "subset": "hallucination_gptzero",
                "citation_text": "third-party text",
            },
        ]
    }

    public, excluded = build_public_dataset(payload)

    assert excluded == 1
    assert [row["id"] for row in public["records"]] == ["R1"]
    assert "third-party text" not in json.dumps(public, ensure_ascii=False)
