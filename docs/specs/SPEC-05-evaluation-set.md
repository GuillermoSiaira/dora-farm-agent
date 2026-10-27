# SPEC-05: Evaluation set with exact answers

**Status:** to implement. **Branch:** `spec-05-evaluation`. Do not merge into `main`; it gets reviewed first.

## Why
The claim "DORA never makes up a number" must be measured, not asserted. The engine gives the exact answer to every question, so the evaluation set is correct by construction. The same harness also runs the agent with and without the verifier, which is the key result for the video and the README.

## Deliverables
1. `eval/questions.jsonl`: 30 questions, one JSON object per line:
   ```json
   {"id": "q07", "lang": "es", "text": "Tengo 500 ha propias y 50.000 dólares. ¿Cuánto crédito voy a necesitar y en qué quincena?",
    "expected_tools": ["evaluate_season"],
    "scenario": {"area_ha": 500, "own_capital_usd": 50000},
    "check": {"tool": "evaluate_season", "field": "max_credit_usd"}}
   ```
   - `scenario` is the scenario a correct agent should build.
   - `check` points to the tool output field that holds the answer.
2. `eval/build_answers.py`: runs each question's scenario through `run_tool` and writes `eval/answers.jsonl` with the exact expected value of `check.field`. Re-running it regenerates the answers: they come from the engine, never typed by hand.
3. `eval/run_eval.py`: runs the agent over the questions and writes `eval/results/<model>_<date>.json`. It takes the arguments `--model`, `--runs 5`, `--no-verifier` (the agent answers without correction rounds) and `--limit` (to try a few questions).
4. `eval/report.py`: reads the results and prints a Markdown table to `eval/REPORT.md`.

## Question mix (30)
- 18 in Spanish, written like an Argentine farmer, with natural numbers ("50 lucas", "90 días", "500 hectáreas"); 12 in English, like an Iowa farmer. The Iowa ones can wait for SPEC-06: mark them `"region": "iowa"` and skip them until then.
- Topics:
  - 8 about the plan (hectares, NPV);
  - 6 about credit and capital (peak credit, capital shadow price, scarce fortnights);
  - 5 sensitivity (supplier term, credit amount);
  - 5 about constraints (a `min_area` contract, a forward sale and its opportunity cost);
  - 3 about storage and prices;
  - 3 that must be refused or answered with a clarifying question (missing data, an impossible scenario, a crop the engine does not support).

## Formulation questions (added; they count toward the 30)
Replace 6 of the "plan" questions above with **formulation** questions: real farmer phrases that the agent must translate into parameters and constraints. Each one's `scenario` holds the exact expected translation. Examples:

| Farmer says | Expected scenario |
|---|---|
| "Por el contrato con la cooperativa tengo que hacer mínimo 200 de soja." | `constraints: [{type: min_area, crop: soybean, ha: 200}]` |
| "Ya vendí 300 toneladas de soja para mayo a 320." | `constraints: [{type: forward_sale, crop: soybean, month: "2027-05", tonnes: 300, price_usd_t: 320}]` |
| "El de los agroquímicos me da a cosecha, pero me recarga un 4%." | `input_payment_delay_fortnights` = fortnights from purchase to harvest, `input_delay_surcharge: 0.04` |
| "Tengo 50 lucas propias y el banco me da hasta 100 al 10%." | `own_capital_usd: 50000, credit_line_usd: 100000, credit_rate_annual: 0.10` |
| "No quiero más de la mitad del campo en maíz." | `constraints: [{type: max_area, crop: corn, ha: 0.5 × area}]`, or `max_crop_share: 0.5` (both accepted) |
| "El campo es alquilado." | `rented_land: true` |

Add a metric: **Formulation accuracy**, the share of formulation questions where the agent's scenario matches the expected one (types and crops exact, numbers within 1%).

## Modeling guide for the agent (added)
Write `dora/modeling_guide.md` and append it to the agent's system prompt in `dora/agent.py` (load the file at startup). It teaches the agent to formulate like an expert analyst:
1. **How farmer phrases map to parameters and constraints**: the table above, plus months to fortnights ("90 días" = 6 fortnights), "lucas" = thousands, hectares versus acres for Iowa.
2. **Coherence of documents.** One invoice alone says very little. A document only **replaces specific coefficients** of a complete scenario built on the regional defaults:
   - A fertilizer invoice gives the fertilizer cost and its payment term, nothing else.
   - Turn invoice totals into USD per hectare only when the hectares are known; if they are not, ask.
   - Compare each replaced coefficient with the regional default. If it differs by more than 50%, ask the farmer to confirm before using it, since it may be a partial purchase, another crop, or a typo.
   - Always show which coefficients come from the farmer's documents and which are still defaults: the completeness of the scenario.
3. **When to ask instead of assuming**: anything that changes the plan a lot and has no sensible default (own versus rented land, the area, the crops allowed).
4. **What to analyze after the first run**: if capital is scarce, try supplier terms and credit with `sensitivity`. If storage has a shadow price, say what an extra tonne is worth. If a constraint is binding, report its opportunity cost.

Add 2 evaluation questions on coherence: an invoice total without hectares (expect a clarifying question), and a coefficient 3× the regional default (expect a confirmation question).

## Metrics (in `report.py`)
| Metric | Definition |
|---|---|
| Tool accuracy | share of answers where the right tool was called with the right scenario (numeric parameters within 1%) |
| Answer correctness | share where the final text contains the expected value (use the verifier's number reader; correctly rounded counts) |
| Unsupported numbers | share of answers with at least one number the verifier flags, **before** correction rounds |
| Verified after correction | share of answers that end verified |
| Calls per question | mean number of tool calls |
| Cost | input and output tokens per question, if the API returns usage |

Each metric is reported with and without the verifier, as the mean over runs with its min–max range.

## Acceptance tests (`tests/test_eval.py`), no network
1. `questions.jsonl` has 30 valid lines, and every `scenario` passes `build_scenario` without error (except the 3 must-refuse ones, which are marked `"expect": "refuse"`).
2. `build_answers.py` produces an answer for every non-refuse question, and the answers equal a direct `run_tool` call.
3. `run_eval.py` with the scripted model from `tests/test_agent.py` runs end to end on 3 questions and writes a results file.
4. `report.py` turns a small results file into a table with all metrics.
5. All existing tests still pass.
