# RefGuard

RefGuard is an open-source toolkit for checking whether bibliography entries are supported by public scholarly metadata sources.

It focuses on reference identity verification: title, author, year, DOI, arXiv ID, and source evidence. Optional LLM-based relevance checks are kept separate and are disabled by default.

## Features

- Verify BibTeX references against Crossref, OpenAlex, arXiv, DBLP, and Semantic Scholar.
- Fuse multi-source evidence into a match probability and a clear status.
- Detect duplicate bibliography entries.
- Check BibTeX usage against LaTeX citation keys.
- Produce JSON and Markdown reports.
- Run as a CLI tool or a FastAPI service.

## What RefGuard Does Not Do

- It does not use CNKI or any closed academic database.
- It does not scrape Google Scholar.
- It does not depend on private LLMs for reference identity decisions.
- It does not include user-uploaded papers or private project data.

## Installation

```bash
pip install -e .
```

For development:

```bash
pip install -e ".[dev]"
```

## CLI Usage

Verify a BibTeX file:

```bash
refguard verify bib --input tests/test_bib.bib --profile balanced --out ./report
```

The legacy command name is also available:

```bash
refcheck verify bib --input tests/test_bib.bib
```

Verify a BibTeX file and LaTeX citation usage:

```bash
refguard verify project --bib paper/references.bib --tex paper/main.tex --check-usage on --out ./report
```

## API Usage

Start the API server:

```bash
uvicorn main:app --reload
```

Open:

- http://127.0.0.1:8000/docs
- http://127.0.0.1:8000/api/v1/sources/status

Example request:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/verify/bib" \
  -H "Content-Type: application/json" \
  -d '{"bibtex_content":"@article{demo,title={Attention Is All You Need},author={Vaswani, Ashish and Shazeer, Noam},year={2017}}","profile":"balanced"}'
```

## Configuration

Copy `.env.example` to `.env` only if you need local overrides.

All API keys are optional and should stay out of version control:

- `SEMANTIC_SCHOLAR_API_KEY`: optional higher rate limit.
- `OPENALEX_API_KEY`: optional.
- `CROSSREF_MAILTO`: optional polite-pool email.
- `OPENAI_API_KEY` / `DASHSCOPE_API_KEY`: optional relevance checks only, not used by identity verification.

## Benchmark Data

Small sample and benchmark files live under `data/`. Treat them as research artifacts: keep only bibliographic metadata, labels, and provenance that can be redistributed. Do not commit raw papers, private uploads, proprietary database exports, or API keys.

Run the benchmark helper:

```bash
python eval/run_benchmark.py --input data/refguard_input.jsonl --out eval_report
```

## Development Checks

```bash
python -m unittest discover tests
python -m py_compile refguard
```

If `pytest` is installed:

```bash
pytest tests -q
```

## License

Code is released under the MIT License. See [LICENSE](LICENSE).
