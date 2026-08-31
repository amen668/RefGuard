import json
from pathlib import Path

from scripts.run_ablation import feature_ablation_rows

ROOT = Path(__file__).resolve().parents[1]


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_frozen_feature_ablation_matches_paper_result():
    test_rows = _jsonl(ROOT / "paper_results" / "ablation_cache_openalex_clean_v4.jsonl")
    dev_rows = _jsonl(ROOT / "paper_results" / "dev_features_v4.jsonl")

    actual = feature_ablation_rows(test_rows, dev_rows)
    compact = [
        (row["name"], row["confusion"], round(row["metrics"][2] * 100, 1),
         round(row["metrics"][1] * 100, 1), round(row["metrics"][3], 3))
        for row in actual
    ]

    assert compact == [
        ("仅 DOI 匹配", (110, 389, 1, 0), 100.0, 99.1, 0.995),
        ("DOI+标题", (110, 388, 2, 0), 100.0, 98.2, 0.991),
        ("仅标题相似度", (54, 390, 0, 56), 49.1, 100.0, 0.659),
        ("仅作者相似度", (56, 388, 2, 54), 50.9, 96.6, 0.667),
        ("标题+作者+年份", (62, 390, 0, 48), 56.4, 100.0, 0.721),
        ("全特征（同协议）", (98, 390, 0, 12), 89.1, 100.0, 0.942),
    ]
