# DORA Evaluation Report — muse-spark-1.3

| Metric | With Verifier | Without Verifier |
|---|---|---|
| Tool accuracy | 88.9% | 86.1% |
| Answer correctness | 86.1% | 86.1% |
| Formulation accuracy | 100.0% | 100.0% |
| Unsupported numbers (before correction) | 5.6% | 11.1% |
| Verified after correction | 100.0% | 88.9% |
| Calls per question | 2.2 | 2.3 |
| Prompt tokens / question | 27010 | 26434 |
| Completion tokens / question | 3506 | 3534 |

## Reading these numbers (2026-10-28, 36 questions)

- **One run of 36 questions per column** (30 earlier ones plus 6 from SPEC-15: scarce-capital stretch, region comparison, freight). One question is 2.8 points.
- **Verifier:** without it, 4 of 36 answers (11.1%) kept a number no tool returned; with it, none. Only 2 of 36 first drafts (5.6%) needed a correction.
- **A regression found and fixed the same night:** the first 36-question run gave 50.0% verified without the verifier. The modeling guide's example ("12% en esos 4 meses") taught the model to convert days to months by itself. The tool now returns `duration_months` and the guide forbids unit conversions (commit 6440b33).
- **Freight questions (q35, q36) fail for a real reason:** a single-farm evaluation does not include freight to port yet; only `compare_regions` does. The model says so instead of inventing a figure. To be fixed in the engine (and checked for double counting against MAGyP's marketing costs).
- **Tool accuracy misses q23, q29** remain scoring artifacts (right value through `sensitivity` with a different base scenario).
- **Cost:** about 27,000 input and 3,500 output tokens per question, roughly USD 0.05.
