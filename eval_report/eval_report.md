# RefGuard Benchmark Report

**Input:** `refguard_input.jsonl` | **Profile:** balanced | **N:** 10

## Metrics

| Metric | Value |
|--------|--------|
| Accuracy | 1.0000 |
| Precision (hallucination) | 1.0000 |
| Recall (hallucination) | 1.0000 |
| F1 (hallucination) | 1.0000 |

## Confusion Matrix (positive = hallucination)

| | Predicted Hallucination | Predicted Not Hallucination |
|--|--------------------------|-----------------------------|
| **GT Hallucination** | TP = 10 | FN = 0 |
| **GT Not Hallucination** | FP = 0 | TN = 0 |
