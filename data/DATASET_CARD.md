# RefGuard Benchmark Dataset Card

## Status

The benchmark data in this directory should be treated as a research artifact, not as an automatically redistributable dataset.

Before publishing a release, verify:

- Every source record is redistributable.
- Labels and notes are authored by the project or licensed for redistribution.
- No private manuscripts, API responses, cookies, credentials, or proprietary database exports are included.
- No CNKI-derived data or scraper output is included.

## Recommended Public Release Shape

For the repository:

- Keep a small sample JSONL file for smoke tests and examples.
- Keep full benchmark data out of the default package until its license is clear.

For the paper artifact:

- Publish a frozen benchmark archive with a dataset version, license, provenance, and evaluation script.
- Include enough metadata for reproducibility without distributing copyrighted full text.

## JSONL Fields

Expected fields:

- `paper_id`
- `paper_title`
- `paper_url`
- `reference.raw`
- `reference.parsed.title`
- `reference.parsed.authors`
- `reference.parsed.year`
- `reference.parsed.venue`
- `reference.parsed.doi`
- `reference.parsed.arxiv`
- `reference.parsed.url`
- `ground_truth.is_hallucinated`
- `ground_truth.notes`
- `source`
