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
