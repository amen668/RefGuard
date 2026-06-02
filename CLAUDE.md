# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

RefGuard verifies whether BibTeX reference entries can be supported by public academic metadata sources (Crossref, OpenAlex, arXiv, DBLP, Semantic Scholar). It fuses multi-source evidence into a match probability and a stable report status. The goal is detecting hallucinated / unverifiable citations — **not** LLM-based judgment.

Hard project constraints (enforced in `CONTRIBUTING.md`, do not violate):
- Reference verification must **never** depend on LLM output.
- Only public, documentable metadata sources. No Google Scholar scraping, no browser automation, no credentialed/private data sources.
- Do not commit large generated reports, caches, `.env`, or private datasets.
- Source comments, docstrings, and test method names are written in **Chinese** — match this convention when editing.

## Commands

```bash
pip install -e ".[dev]"          # dev install (pytest, ruff)

# Tests — both work; tests are unittest-based
python -m pytest tests -q
python -m unittest discover tests
python -m pytest tests/test_core.py -q                 # single file
python -m pytest tests/test_core.py -q -k 解析          # single test (names are Chinese)

ruff check refguard eval scripts # lint (line-length 100, target py311)
python -m compileall -q refguard eval scripts

refguard verify bib --input tests/test_bib.bib --profile balanced --out ./report
refguard verify project --bib paper/references.bib --tex paper/main.tex --check-usage on --out ./report
uvicorn main:app --reload        # API at http://127.0.0.1:8000/docs
```

Benchmark (data files are gitignored / regenerated, not in the repo):
```bash
python scripts/build_refguard_input.py
python eval/run_benchmark.py --input data/refguard_input.jsonl --out eval_report
```

## Architecture

The verification pipeline is orchestrated by `refguard/services/verification_service.py` (`VerificationService`), the single facade used by both the CLI (`refguard/cli.py`) and the API (`refguard/api/app.py`). Flow per BibTeX entry:

1. **Parse** — `parsers/bib_parser.py` parses BibTeX into `BibEntry`; `parsers/tex_parser.py` extracts `\cite{}` keys for usage checking.
2. **Retrieve candidates** — `retrieval/candidate_generator.py` calls each enabled fetcher, merges and dedupes hits (by source + DOI/URL/title), keeps Top-K → list of `SourceHit`.
3. **Build features + score** — `fusion/feature_builder.py` turns each `(BibEntry, SourceHit)` pair into a `MatchFeatures` vector (title/author similarity, year/DOI/arXiv match, source prior, rank, etc.). `fusion/fusion_model.py` scores each candidate with a **linear logistic model** (default heuristic weights in `DEFAULT_WEIGHTS`, operating in logit space → sigmoid). Optional trained weights load from `fusion_model.json` in `model_dir`.
4. **Decide** — `fusion/decision_engine.py` (`decide`) applies the profile's `match_threshold` and a Top-2 gap rule, plus a hard override: author similarity < 0.2 with no DOI match forces a non-match (`author_mismatch`). Produces a `ComparisonResult`.
5. **Report** — `report/generator.py` (`ReportGenerator`) serializes everything to JSON/Markdown (and optional `only_used.bib`). It is serialization-only and must not contain verification logic.

`models/status.py::resolve_report_status` maps a `ComparisonResult` to the stable external status (`verified` / `warning` / `error`) — `author_mismatch` always → `error`.

### Key extension points

- **Add a metadata source**: subclass `fetchers/base.py::BaseFetcher`, implement `lookup_by_doi` / `lookup_by_arxiv_id` / `search_by_title` (base class drives the query plan, rate limiting, and hit normalization), then register it in `fetchers/__init__.py::FETCHER_REGISTRY`. Add its source priors in `fusion/feature_builder.py::SOURCE_PRIOR`.
- **Add a fusion feature**: extend `MatchFeatures` (`models/match_features.py`), build it in `FeatureBuilder.build`, and append its name to `FEATURE_NAMES`. The model zero-pads missing dims for backward compatibility, so keep `FEATURE_NAMES` order stable.
- **Tune decision behavior**: edit `config/profiles.py` (`strict`/`balanced`/`lenient` thresholds and `top_k`). Source enablement and default order live in `config/workflow.py::DEFAULT_SOURCES`.

### Config

`core/config.py::settings` is a pydantic-settings singleton read from env / `.env` (rate-limit delays per source, cache TTL, timeouts, optional API keys). All API keys are optional and only raise public-source rate limits. Logging is set up via `core/logging.py::setup_logging`.
