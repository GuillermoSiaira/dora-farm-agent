# SPEC-48: question generator with exact answers and clean splits (for the LLM mechanic)

**Status:** ready (7/11), approved by Guillermo ("dale, avanzá"). Implement on branch `spec-48-question-generator`, created from `claude/keen-wilson-695e01` (it has the E9 harness and E12). Do not merge, do not push. Commit with messages starting `SPEC-48 implementation:`; write the handoff and Claude reviews. **No model is called anywhere in this spec**: no LLM, no GPU, no API key. Everything runs offline with the engine (`DORA_OFFLINE=1`).

Touch only: a new `eval/gen/` package (`templates.py`, `generate.py`, `split.py`, `__init__.py`), the generated files under `eval/gen/data/`, two new flags in `eval/run_e9.py` (`--questions`, `--answers`), a new `tests/test_spec48.py` and the handoff. Do not edit `eval/questions.jsonl`, `eval/answers.jsonl` or the agent.

**Why.** The bench has 36 hand-written questions, most of them variants of one farm ("500 ha y 50 lucas"). E12 (`docs/experimentos/2026-11-07-e12-mecanico.md`) showed that even two few-shot examples contaminate 12 of the 34 remaining questions. No knob that touches weights (LoRA, RL with the bench as reward) can be measured honestly on that. We need hundreds of questions, each with its exact answer computed by the engine, split so that what a knob is tuned on is never what it is tested on.

## 1. Templates (`eval/gen/templates.py`)
One template family per question type that exists today (see `type` in `eval/questions.jsonl`): `formulation` (min/max area, forward sale, payment terms, rented land), `plan`, `credit_capital`, `sensitivity`, `constraints`, `storage_prices`, `logistics`, and the refusals (`coherence_missing_data`, `unsupported_crop`, `impossible_scenario`). Each template has:
- **Parameter sampler.** Draws a scenario from ranges valid for the region (read them from the engine's region data, never hard-code prices or yields):
  - regions `southeast_buenos_aires`, `pampas_core`, `iowa`, `mato_grosso`;
  - area 100 to 3,000 ha, rounded the way a farmer says it (150, 400, 1.200);
  - own capital 10 to 800 thousand USD; credit line and rate; payment delay 2 to 8 fortnights with a 1 to 6 % surcharge;
  - min/max area per crop, forward sales (crop, month, tonnes, price near the region's price), storage, monthly price rise, a stated yield.
  - Only the parameters the template's text will mention go into the scenario: the rest stay at the engine defaults, as in the hand-written questions.
- **Check.** `{tool, field}` exactly like `eval/questions.jsonl` (`npv_usd`, `hectares.<crop>`, `max_credit_usd`, `capital_shadow_price`, `credit_line_shadow_price`, `storage_shadow_price_usd_t`, `capital_stretches.0.rate_for_stretch_pct`, `freight_share_pct`, and `compare_regions` fields).
- **Text renderers.** At least **4 phrasings per template in Spanish (Rioplatense) and 3 in English**. They vary:
  - word order;
  - units ("50 lucas", "50.000 dólares", "USD 50k", "$50,000");
  - how the question is asked;
  - whether the region is named or implied by a town (Balcarce, Pergamino, Ames, Sorriso).

  Each renderer has an id (`<template>.<lang>.<n>`).
- **Refusal templates** produce `expect: "refuse"` (or `"confirm"` for an implausible yield) and no check, like q13, q17, q18 and q30.

## 2. Generation (`eval/gen/generate.py`)
`python -m eval.gen.generate --n 600 --seed 48 --out eval/gen/data`:
1. Draw scenarios, render a text, compute the answer through the same path as `eval/build_answers.py` (`run_tool`, `DEFAULT_PRICE_SOURCE = "magyp_june"`). Never type an answer by hand.
2. **Drop** a question when any of these holds (count each reason in the manifest):
   - the solve fails or is infeasible;
   - the expected value appears as a number in the question text (the q19 echo: the strict rule would not count it);
   - the answer equals an input number;
   - the same scenario (canonical JSON) was already drawn.
3. **Mark, don't drop:** `binding: false` when the template's constraint does not bind (the answer equals the plan without it, like q05). The analysis needs both kinds, but must be able to separate them.
4. About 10 % refusals and confirmations, spread over regions and languages.
5. Write `questions_<split>.jsonl` and `answers_<split>.jsonl` with the same schema as `eval/questions.jsonl` and `eval/answers.jsonl`, plus `template`, `renderer`, `binding` and `split`, and an `id` like `g0001`.

## 3. Splits (`eval/gen/split.py`)
Deterministic from the seed. Default sizes: **train 400, dev 100, test 100**.
- **`test` is held out by template phrasing.** Half of `test` (`test_iid`) uses renderers also used in train, with new parameters. The other half (`test_ood`) uses renderers that never appear in train or dev, and at least one whole template family per language held out. This is what tells "learned the procedure" from "learned the wording".
- **Contamination guard against everything a model has already seen:**
  - the 36 bench questions;
  - the few-shot examples of E12 (q01 and q09, `eval/run_e9.py FEWSHOT_IDS`);
  - any question whose scenario canonical JSON, or whose expected value, matches one of those, is removed from dev and test (it may stay in train).
- `manifest.json`: seed, git commit, counts per split × template × region × language × binding, drop counts by reason, and the sha256 of each file.

## 4. Harness flags (`eval/run_e9.py`)
`--questions <path> --answers <path>`, passed to `run_evaluation(questions_path=..., answers_path=...)` (it already accepts them). Default: the current 36 questions, so every existing command behaves the same. `eval/e12_mechanic.py` is not changed in this spec.

## 5. Handoff
- The manifest numbers.
- 12 generated questions picked at random from `test_ood`, with their scenario and expected value, so Guillermo can read them and say whether a farmer would ask that way.
- The time a full generation takes.

## Tests (`tests/test_spec48.py`, offline, no LLM)
1. Same seed, same files (byte-identical); a different seed changes them.
2. Every non-refusal question's expected value equals a fresh `run_tool` of its scenario and check (tolerance 1e-6).
3. No question text contains its own expected value (any of the usual Spanish and English number formats).
4. No dev or test question matches a bench question or a few-shot example by scenario or by expected value.
5. No `test_ood` renderer id appears in train or dev; at least one template family per language is absent from train.
6. Split sizes as requested; refusals between 7 and 13 % of each split.
7. Every generated `questions_*.jsonl` loads with `eval.run_eval._read_jsonl` and passes the same schema checks the 36 questions pass.
8. `run_e9.py --questions/--answers` reaches `run_evaluation` with those paths (monkeypatch `run_evaluation`, no network).

## Not in this spec
- Paraphrasing with an LLM. It would add variety, but a paraphrase can change the meaning, and then the exact answer would be wrong. If it is ever added, every paraphrase must be checked by rebuilding its scenario from the text with the engine's own parser, or by a person.
- Running any model on the new questions, LoRA training, or the localisation pilot (activation patching). Those come after this, with their own approval of cost.
