# Paper reproducibility package

This directory contains the smallest data package needed to audit the principal
results reported for RefGuard. It does not contain API credentials, cookies,
full-text papers, raw API responses, or private user data.

## Files

- `../data/citation_dataset_public_v4.json`: public release of the 2,537-record
  benchmark (1,937 real and 600 hallucinated citations; dev 500/test 2,037).
  The top-level `_meta` object documents ethics and third-party attribution.
- `eval_report_v4.json`: per-record predictions for the 2,037-record test set.
  The confusion matrix is TP=472, FP=6, TN=1,559, FN=0, yielding accuracy
  0.9971, hallucination precision 0.9874, recall 1.0000, and F1 0.9937.
- `ablation_cache_openalex_clean_v4.jsonl`: deduplicated 500-record cache used
  for the final six-source ablation, including OpenAlex evidence.

## Ablation version note

An earlier 500-record run was completed while the OpenAlex endpoint returned no
hits. That degraded run produced TP=110, FP=11, TN=379, FN=0 (precision 90.9%,
F1 0.952). OpenAlex was then rerun for exactly the same 500 IDs. All labels and
all non-OpenAlex hits remained unchanged; the final clean cache produced
TP=110, FP=1, TN=389, FN=0 (precision 99.1%, F1 0.995). Ten real citations that
were false positives in the degraded run were correctly resolved after adding
OpenAlex evidence.

The manuscript's description of the six-source system corresponds to the final
clean cache. The full-test result in `eval_report_v4.json` is unaffected by this
table-version note.

## Recompute the ablation table

From the repository root:

```bash
python scripts/build_refguard_input.py \
  --input data/citation_dataset_public_v4.json \
  --output refguard_input_public_v4.jsonl \
  --summary refguard_input_public_v4_summary.json

python scripts/run_ablation.py \
  --offline-only \
  --cache paper_results/ablation_cache_openalex_clean_v4.jsonl \
  --out paper_tables_ablation_reproduced.md
```

The benchmark evaluation uses live public scholarly-metadata endpoints. Exact
online results may change as those services update their records; the included
per-record report and feature cache preserve the paper-time evidence.

## SHA-256

```text
f7c2b8a3d980ee1bfc35bf8966f8cdd5d4d758a77db2942843edb8e57e59378f  data/citation_dataset_public_v4.json
19716f225c83dbcfac48cf94d478f0267b42585dac330cd035e4a310b7ef76e7  paper_results/eval_report_v4.json
fadce748a23b2029b374bbb9a64b33cb4d2f2e06b6f03c813fad46807e70bb4b  paper_results/ablation_cache_openalex_clean_v4.jsonl
```
