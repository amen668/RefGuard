# Contributing

Thanks for helping improve RefGuard.

## Development Setup

```bash
pip install -e ".[dev]"
python -m unittest discover tests
```

## Pull Request Guidelines

- Keep reference identity verification independent from LLM output.
- Use only public, documented data sources.
- Do not add CNKI, Google Scholar scraping, browser automation, or credentials.
- Add tests for parser, feature, fusion, or API behavior when changing core logic.
- Avoid committing large generated reports, caches, local `.env` files, or private datasets.

## Data Contributions

Benchmark data should contain redistributable bibliographic metadata and explicit provenance. Synthetic hallucinated references are welcome when their construction method is documented.
