# SPEC-24: What a verified answer costs

**Status:** draft (29/10), to implement on branch `spec-24-economics`, created from `main` **after** the E1 merge (`565a358`), which rewrote `eval/run_eval.py`. Do not merge into `main`; it gets reviewed first. It touches `eval/` (new files and `run_eval.py`, `report.py`), a counter in `dora/agent.py` and tests. **It must not change the engine, the tools' numbers, the prompts or the agent's behavior:** this spec only measures. Every results file already records the model version it ran on (`commit`, marked `-dirty` with uncommitted changes); results are compared only when they share the commit, the data snapshot and the questions.

## Why

### The question nobody in the room is measuring
There is an open argument, in the industry and in the developer groups we talk to: "open models can do the same as the big closed ones, and cheaper". Each side gives benchmark scores. Neither gives the number that decides a purchase: **how much it costs to get one correct answer you can act on**. A model that is 40% cheaper per token but gets one answer in three wrong is not cheaper; a model that is right but needs 30 seconds and a dedicated GPU idling all night may not be either.

DORA can measure this better than almost anyone, for one reason: **its answers are graded by an exact engine and a verifier, not by another language model**. We know, for each question, whether the number is right and whether every number is backed. So "cost per verified correct answer" is a hard number here, not an opinion.

### Why it matters for DORA itself
1. **The vision says a small open model can do the job** (`docs/vision.md`, step 3: fine-tune a small model to formulate scenarios and run it on a cooperative's server). That is a claim about costs and accuracy. Without a cost metric, E6 (`docs/plan-de-pruebas.md`) can show that a small model does not invent numbers, but not whether it is worth using.
2. **Our users are businesses that think in margins.** A cooperative or a consultancy does not buy "94.4% answer correctness"; it buys "USD 0.0X per verified recommendation, answered in Y seconds". That is the sentence for the jury and for a client.
3. **It is operations research applied to the AI itself.** Choosing which model answers which question, and whether to pay per token or rent a GPU, is an allocation problem with costs and capacities, the same kind of problem DORA solves for a farm. This is the research line we want to fund after the hackathon.

### Three things the current evaluation hides
- **The cost of being wrong is not counted.** `run_eval.py` records tokens per question (about 28,000 in, 3,600 out, roughly USD 0.05 with Muse Spark 1.3), but nothing divides cost by *correct* answers, and nothing records latency.
- **Paying per token and renting a GPU are different economics.** In Baseten, a dedicated deployment is billed per GPU-minute, whether it is answering or idle. Generating text one token at a time leaves most of a GPU's arithmetic idle, waiting on memory; serving many requests at once fills it. So the cost per answer of a dedicated GPU depends on **how busy it is**, and there is a break-even volume above which it beats a per-token API. Below it, renting the GPU is paying for idle time.
- **The fixed part of the prompt dominates the bill.** About 28,000 input tokens per question, most of them the system prompt, the modeling guide and the tool schemas, sent again on every call. That is the main cost driver, and it hurts small models most, since they lose accuracy on long contexts. We should know exactly how big it is before deciding anything about it.

### And the statistics are thin
With 36 questions and one run, one question moves a rate by 2.8 points: the 91.7% vs 94.4% tool accuracy with and without the verifier (`eval/REPORT.md`) is noise. Comparing models on cost per correct answer only means something with an interval and with a **paired** comparison: the same questions, in both conditions.

### Prices: list price, not our credits
We run on free credits (Meta, Baseten, Modal). Our cash cost is zero, but that tells a client nothing. Every cost in this spec uses the **provider's list price**: what the same run would cost anyone paying for it, which is the opportunity cost of the credits. Prices are read from the provider's page or console and stored with their date and source; **no price is ever guessed**.

## 1. Per-question telemetry (`eval/run_eval.py`, `dora/agent.py`, `eval/baseline.py`)
What E1 already gives (do not redo it): `run_eval.py` builds one record per question in `_agent_record` (conditions B and C) and `_baseline_record` (condition A, `--baseline`), each with `prompt_tokens` and `completion_tokens`; the results file has `condition`, `commit`, `question_ids` and `per_question` (spread across runs). `--ids` picks questions; `--questions` and `--answers` take several files.

Add:
- `Agent` counts API requests: `self.usage["requests"] += 1` in `_complete`. If the response's usage reports cached input tokens (`prompt_tokens_details.cached_tokens` in the OpenAI format), add them to `self.usage["cached_prompt_tokens"]`; otherwise leave it absent. Nothing else in the agent changes. `ask_baseline` (condition A) reads the same fields from its single request.
- Each record adds `cached_prompt_tokens` (if any), `requests`, and `latency_s` (wall clock of `agent.ask` or `ask_baseline`, with `time.perf_counter`).
- The results file adds at top level: `provider` (from a new `--provider` argument, e.g. `meta`, `baseten`, `modal`) and `api_host` (the host of `DORA_API_BASE`, never the key).
- Old results files, without these fields, must still load in `report.py`.

## 2. Prices (`eval/pricing.json`)
One entry per model and provider, filled by hand from the provider's pricing page or console:

```json
{
  "muse-spark-1.3@meta": {
    "billing": "per_token",
    "usd_per_m_input": null,
    "usd_per_m_cached_input": null,
    "usd_per_m_output": null,
    "source": "<pricing page URL or 'console'>",
    "read_on": "2026-10-29"
  },
  "<model>@modal": {
    "billing": "serverless_gpu",
    "gpu": "<GPU type>",
    "gpus": 1,
    "usd_per_gpu_second": null,
    "source": "<URL>",
    "read_on": "<date>"
  },
  "<model>@baseten-dedicated": {
    "billing": "dedicated",
    "gpu": "<GPU type>",
    "gpus": 1,
    "usd_per_gpu_hour": null,
    "source": "<URL>",
    "read_on": "<date>"
  }
}
```

- Commit the file with `null` values. **Do not fill in prices from memory or from another provider.** If the implementer cannot read a price, it stays `null` and is written in the handoff for Guillermo to fill.
- Every calculation with a `null` price shows "price unknown" and reports tokens only. It never fails and never assumes zero.

## 3. Economics (`eval/economics.py`)
A module with pure functions (no network) and a command line that reads one or more results files plus `pricing.json`.

**Per run and condition:**
- `usd_per_question`: per-token billing = (input − cached) × input price + cached × cached price + output × output price, per question, averaged.
- `usd_per_correct_answer` = total cost / number of correct answers (`answer_correctness`).
- `usd_per_verified_correct_answer` = total cost / number of answers that are correct **and** verified. This is the headline metric. In condition A (no tools) "verified" means the answer has no number missing from the data it was given or the question (`has_unsupported_before_correction` is false), the same check the verifier makes.
- `latency_p50_s`, `latency_p95_s`.
- If no answer is correct, the cost per correct answer is "∞ (no correct answers)", not an error.

**Uncertainty:**
- 95% interval for answer correctness and for cost per verified correct answer, by bootstrap over **questions** (2,000 resamples, fixed seed `20261029`, `numpy`).
- Paired comparison between two conditions run on the same questions: exact McNemar test on the discordant pairs (`scipy.stats.binomtest(b, b + c, 0.5)`). Report b, c and the p-value. With several runs, compare question by question using each question's majority result.

**Dedicated GPU (Baseten) and the break-even volume:**
- For a `dedicated` entry, the cost per question measured at concurrency 1 is `usd_per_gpu_hour × gpus × latency_s / 3600`. Label it **"upper bound, one request at a time"**: it is what an idle-most-of-the-time deployment costs, since serving several requests at once lowers it.
- For a `serverless_gpu` entry (Modal), the container is billed per second while it runs and scales to zero when idle: the cost per question at concurrency 1 is `usd_per_gpu_second × gpus × latency_s`, plus the cold start, which is measured and reported apart (first request after an idle container) and not spread over the questions.
- Break-even monthly volume against a per-token model with known `usd_per_question`:
  `Q* = usd_per_gpu_hour × gpus × hours_on_per_month / usd_per_question_per_token`.
  `hours_on_per_month` is an argument (default 730, always on; also report 220, business hours). Below Q* questions a month, paying per token is cheaper.
- Optional, only if there is time: a `--concurrency N` flag in `run_eval.py` (threads, one `Agent` each) to measure throughput (questions per GPU-hour) at N = 1, 4, 8, and the cost per question at each. If it is not done, say so in the handoff.

**Fixed prompt overhead:**
- A function that sends one minimal request ("Hola", the full system prompt and the tool schemas, `max_tokens=1`) and reads `prompt_tokens`: that is the fixed overhead per API request, measured by each provider's own tokenizer. One call per model; a negligible cost.
- Report: fixed overhead, average prompt tokens per question, and the share of input tokens that is fixed overhead (overhead × requests / prompt tokens).
- Do not change the prompt in this spec. This number decides whether a later spec shortens it or uses prompt caching.

## 4. Cost–accuracy frontier (`eval/frontier.py`)
- One point per model and condition: x = USD per question (log scale), y = share of verified correct answers, with the bootstrap interval as error bars.
- Mark the efficient points: no other point is both cheaper and more accurate.
- Output: `eval/results/frontier.html` (plotly, already in `requirements.txt`) and the same data as a Markdown table. No new dependencies.

## 5. Report (`eval/report.py`)
Add a section "Economics" to `REPORT.md`, after the current table:

| Model @ provider | Condition | Verified correct (95% CI) | USD / question | USD / verified correct answer (95% CI) | Latency p50 / p95 | Prices read on |
|---|---|---|---|---|---|---|

Below it: the paired comparisons (b, c, p), the fixed overhead line, and, if there is a dedicated entry, the break-even volume at 730 and 220 hours. Every number comes from results files; none is typed by hand.

## 6. How it is used in the test plan (`docs/plan-de-pruebas.md`)
- **E1** (LLM alone vs tools vs DORA): add the economics row for each condition. The point to show: the LLM alone looks cheaper per question, and DORA is cheaper per *verified correct* answer.
- **E6** (Meta's open models on Baseten and Modal): run conditions B and C with `--provider baseten` and `--provider modal`, and fill in their prices. This is where the frontier and the break-even volume matter: the same weights on two kinds of infrastructure (a dedicated deployment and a serverless GPU) separate the model from where it runs.
- **Cost control:** always a pilot with `--limit 5` first; check `usd_per_question` before the full run. Stop and write in the handoff if a full run would use more than 20% of a provider's remaining credit.

## Not in this spec
- Fine-tuning a small model (Modal) on examples generated by the engine and graded by the verifier (`docs/vision.md`, step 2–3). That is the next spec; this one gives the yardstick it will be measured with.
- Shortening the prompt, prompt caching, or routing questions between models.

## Acceptance tests (`tests/test_economics.py`, no network)
1. `run_eval.py` with the scripted model from `tests/test_agent.py` (conditions B and C) and with the fake model of `tests/test_e1_baseline.py` (condition A) writes `latency_s`, `requests`, `prompt_tokens` and `completion_tokens` for every question, and `provider`, `api_host`, `commit` at top level. No API key appears anywhere in the file.
2. Cost per question on a hand-built results file with known tokens and prices equals the hand calculation (to 1e-12), with and without cached tokens.
3. A `null` price gives "price unknown" and tokens only; no exception, no zero cost.
4. Cost per verified correct answer counts only answers that are correct and verified; with zero such answers it reports "∞ (no correct answers)".
5. Bootstrap with the fixed seed gives the same interval twice; with all answers correct, the interval for correctness is [1, 1].
6. McNemar: for b = 8, c = 1 the p-value equals `scipy.stats.binomtest(1, 9, 0.5).pvalue`.
7. Break-even: for 1.00 USD/GPU-hour, 1 GPU, 730 h and 0.05 USD/question, Q* = 14,600.
8. Frontier: in a set of 4 points, the dominated point is not marked efficient.
9. `report.py` still renders the old results files (without the new fields) and adds the Economics section when they exist.
10. The engine's numbers do not change: `evaluate_season` and `shadow_prices` for the default scenario equal `main` (to 1e-9).

The existing tests must pass unchanged.

## Handoff (`docs/handoff/spec-24-economics.md`)
What was done, every price read (value, page, date) or left `null`, the fixed overhead measured for each model, whether `--concurrency` was done, and anything in this spec that turned out to be wrong.
