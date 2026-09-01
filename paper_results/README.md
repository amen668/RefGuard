# Paper reproducibility package

> Version boundary: every result in this directory belongs to the frozen V4
> manuscript snapshot. The post-acceptance corrected V5 core dataset does not
> replace these files, and no V5 metric is claimed here. See
> `../data/VERSION_HISTORY.md` and `../data/correction_report_v5.json`.

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
- `dev_features_v4.jsonl`: frozen best-candidate feature vectors for the 500
  development records used to fit and threshold each feature subset.
- `feature_ablation_retrained_v5.json`: structured output of the corrected
  feature-ablation protocol and the six reported rows.

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

The original feature-ablation implementation masked columns only at inference
time while retaining the full model's intercept, threshold, and some unmasked
decision rules. That protocol made several feature combinations collapse to
identical predictions. The corrected protocol independently fits each feature
subset on the frozen development vectors, selects its threshold on that
development set only, and then scores the frozen 500-record test cache once.
The row named `全特征（同协议）` is the full feature set under this controlled
ablation protocol; it is not a replacement for the deployed RefGuard result in
the 2,037-record main test.

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
  --dev-features paper_results/dev_features_v4.jsonl \
  --out paper_tables_ablation_reproduced.md \
  --ablation-json feature_ablation_reproduced.json
```

The benchmark evaluation uses live public scholarly-metadata endpoints. Exact
online results may change as those services update their records; the included
per-record report and feature cache preserve the paper-time evidence.

## SHA-256

```text
c43319ccbaee863db87b250f3a3249234ee500ffb58ff2236a3bd12e2da738a7  data/citation_dataset_public_v4.json
179cd59284c42e37a686a7cff045c6ead1b7fb0b188ff7d5b5683e0d3f6f66c4  paper_results/eval_report_v4.json
1ffe0b4c8c1c81f1286e1ddd9b9e431b6d07dc864f872e597bdd87b11508bfed  paper_results/ablation_cache_openalex_clean_v4.jsonl
f5e5112c6cb55bf1f30ee481d73b4993fc513f728fc1ab637d4f03a02cdde0be  paper_results/dev_features_v4.jsonl
b65e578c83732e66579ab0cf10a3dfa90696decf7af4ce55f0b0a6732053dce7  paper_results/feature_ablation_retrained_v5.json
```
