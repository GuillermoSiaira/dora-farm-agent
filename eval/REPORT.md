# DORA Evaluation Report — muse-spark-1.3

Latest run: 2026-10-28, after SPEC-17 (freight and rent counted once), SPEC-18 (aerial photos with SAM 3.1) and the evaluator fix below. One run of 36 questions per column.

| Metric | With Verifier | Without Verifier |
|---|---|---|
| Tool accuracy | 91.7% | 94.4% |
| Answer correctness | 94.4% | 94.4% |
| Formulation accuracy | 100.0% | 100.0% |
| Unsupported numbers (before correction) | 5.6% | 5.6% |
| Verified after correction | 100.0% | 94.4% |
| Calls per question | 2.2 | 2.3 |
| Prompt tokens / question | 28401 | 28405 |
| Completion tokens / question | 3613 | 3535 |

Results: `results/muse-spark-1_3_with_verifier_20261028_055513.json`, `results/muse-spark-1_3_no_verifier_20261028_055501.json`.

## Reading these numbers

- **One question is 2.8 points.** One run per column: the next step is three runs for a spread.
- **Verifier:** without it, 2 of 36 answers (q04, q18) kept a number no tool returned; with it, none.
- **Remaining misses, with the verifier:**
  - q13: the farmer claims a soybean yield three times the regional one. The agent stops and asks to confirm it before computing, as the modeling guide says for deviations over 50%. Counted as a miss; it is the behavior we want.
  - q33: asked where to farm, the agent compared present values per hectare instead of the season margin per sown hectare the question was scored on. Both come from `compare_regions`.
  - Tool accuracy q23, q29: right value, reached through `sensitivity` or a different base scenario.
- **Evaluator bug fixed (commit bdcd93a):** the answer matcher divided "19,5%" by 100 and compared it with fields already in percent (`rate_for_stretch_pct` = 19.5). q31 and q32 were right and scored wrong. It now accepts both readings, as the verifier does.
- **Freight questions:** after SPEC-17, `evaluate_season` reports the freight to port and its share of the price (`freight_share_pct`): q35 (Pergamino, 5.95%) passes. In Iowa the price is the local elevator's and the trip to the export port is inside the basis; q36 now asks it through the region comparison (22.6%) and passes.
- **History:** the first 36-question run (27/10) gave 50.0% verified without the verifier because the modeling guide's example taught the model to convert days to months; fixed with `duration_months` (commit 6440b33). Runs of 28/10 before the fixes: 100% / 88.9% verified, 86.1% correct.
- **Cost:** about 28,000 input and 3,600 output tokens per question, roughly USD 0.05.
