# DORA Evaluation Report — muse-spark-1.3

| Metric | With Verifier | Without Verifier |
|---|---|---|
| Tool accuracy | 93.3% | 93.3% |
| Answer correctness | 96.7% | 100.0% |
| Formulation accuracy | 100.0% | 100.0% |
| Unsupported numbers (before correction) | 16.7% | 13.3% |
| Verified after correction | 100.0% | 86.7% |
| Calls per question | 2.2 | 2.3 |
| Prompt tokens / question | 22579 | 21831 |
| Completion tokens / question | 3331 | 3090 |

## Reading these numbers (2026-10-27)

- **One run of 30 questions per column.** Small sample: a difference of one question is 3.3 points.
- **The verifier's job is the last two rows.** Without it, 4 of 30 answers (13.3%) kept at least one number that no tool returned and the farmer did not write (q01, q16, q17, q21). With it, every answer ended with all its numbers backed by the engine: the model wrote unsupported numbers in 5 of 30 first drafts (16.7%) and fixed them when the verifier asked.
- **Answer correctness** checks that the expected value appears in the answer. 96.7% vs 100% is one question (q30, a refusal of −50 ha, phrased in a way the scorer does not recognize); it is not a wrong number.
- **Tool accuracy misses (q23, q29)** are scoring artifacts: the model answered with the right value through `sensitivity` with a base scenario different from the one the scorer expects. The value in the answer is correct.
- **Cost:** about 22,000 input and 3,300 output tokens per question, roughly USD 0.04 at USD 1.25 / 4.25 per million tokens (third-party price listing; Meta's pricing page was not reachable).
- **Earlier run, same day, before two fixes** (agent assumed it had to ask about land tenure; the scorer was stricter): answer correctness 83.3% / 80.0%, verified 100% / 70.0%. The fixes are in commit 2598ea5.
