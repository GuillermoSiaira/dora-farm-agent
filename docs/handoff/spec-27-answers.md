# Handoff Report: SPEC-27 Answers and Checks

**Branch:** `spec-27-answers`  
**Status:** Completed, review amendments implemented, and fully verified offline (310 passed, 1 skipped)  
**Date:** 2026-10-31  

---

## 1. What was done, with file and line

### Review Amendments & Bug Fixes
1. **Bug 1: Rejected Scenario Not in `self.tool_results` (`dora/agent.py:141`)**:
   - Removed `self.tool_results.append(result)` for calls rejected by `check_scenario`. The rejection payload is sent to the LLM via `messages` as a tool error, but is excluded from `tool_results` so invented values (e.g. credit of 80,000 USD) cannot become valid tool evidence for the number verifier.
   - Verified by test: `tests/test_spec27.py:test_19_rejected_scenario_not_in_tool_results_and_unsupported_by_verify`.
2. **Bug 2: `self.scenario_rejections` Cleared per `ask()` (`dora/agent.py:171`)**:
   - Initialized `self.scenario_rejections = []` at the beginning of `Agent.ask()` to prevent accumulating rejections from previous conversation turns.
   - Verified by test: `tests/test_spec27.py:test_20_scenario_rejections_reset_at_start_of_ask`.
3. **Point 3: Default 500 ha Valid When Farmer Wrote 500 (`dora/verifier.py:223`)**:
   - When the farmer wrote 500 ha and the agent omitted `area_ha`, the engine's default of 500 ha matches the farmer's stated area, so no problem is generated (`if not _matches_any(500.0, area_nums): problems.append(...)`).
   - Verified by test: `tests/test_spec27.py:test_21_default_500_ha_omitted_by_agent_when_farmer_wrote_500`.
4. **Point 4: Jargon Identifier Filtering in Backticks (`dora/verifier.py:129, 306`)**:
   - Within backticks, `jargon()` matches only tokens formatted as identifiers (`snake_case` or hyphen-separated words matching `^[a-zA-Z0-9]+(?:[-_][a-zA-Z0-9]+)+$`), ignoring ordinary text or numbers such as `` `Iowa` `` or `` `432.584 USD` ``.
   - Verified by test: `tests/test_spec27.py:test_22_jargon_backticks_only_matches_identifiers`.
5. **Point 5: "soy" Removed from Soybean Names (`dora/verifier.py:43`)**:
   - Removed `soy` from `CROP_PATTERNS["soybean"]` so Spanish "yo soy" is not misinterpreted as referencing soybean.
   - Verified by test: `tests/test_spec27.py:test_23_spanish_verb_soy_not_treated_as_soybean`.
6. **Point 6: `SEASON_SOLVING_TOOLS` Single Source of Truth (`dora/verifier.py:52`, `dora/agent.py:22`)**:
   - Defined `SEASON_SOLVING_TOOLS` in `dora/verifier.py` and imported it in `dora/agent.py`, removing duplicate definition.
   - Verified by test: `tests/test_spec27.py:test_24_season_solving_tools_single_source_of_truth`.
7. **Point 7: Test 9 Enhancements (`dora/verifier.py:123, 178, 243`, `eval/questions_spec26.jsonl:1`)**:
   - **`q05`**: Added fraction parsing (`la mitad` $\to$ 0.5, `un tercio` $\to$ 1/3, `un cuarto` $\to$ 0.25) to `_extract_farmer_numbers()`, scaling every stated area by the fraction (`500 * 0.5 = 250 ha`). Verified by `test_25_fractions_la_mitad_un_tercio_un_cuarto_and_proportions`.
   - **`q40`**: Proportion parameters (`max_crop_share`, `min_crop_share`, `loss_share`, `*_share`) accept `0.0` and `1.0` as "sin tope" without requiring explicit numbers in the prompt. Verified by `test_26_share_parameters_accept_0_and_1_without_cap`.
   - **`q43`**: Removed `"crops": ["soybean"]` from `q43` in `eval/questions_spec26.jsonl`. Verified that the expected answer remains `carryover.tonnes_carried_total == 500.0` with empty answer diff. Verified by `test_27_q43_unrestricted_crops_expected_answer_unchanged`.
   - **`test_09_check_scenario_eval_set`**: Now asserts `failing_qids == set()` (0 failing questions across the entire eval set).

### `dora/tools.py`
- **Line 433–437 (`build_scenario`)**: When neither `area_ha` nor `owned_ha` is provided in the scenario arguments (`given`), the scenario report returns `"area_ha": {"value": None, "unit": "ha", "origin": "missing", "note": "ask the farmer"}` instead of reporting 500 as default. The underlying `Scenario` class maintains its 500 ha engine default for other tools.
- **Line 880–928 (`compare_regions`)**: Added calculation of `best_region` (the region with highest NPV), `npv_gap_to_next_usd` at the root result level, and `npv_gap_vs_best_usd` in each region's breakdown dict.
- **Line 988–994 (`sensitivity`)**: Added `npv_change_vs_first_usd` to each row of the sensitivity analysis, measuring the NPV delta against row 0 (which is 0.0).

### `dora/verifier.py`
- **Lines 20–25**: Added `ScenarioProblem` dataclass with `parameter`, `value`, and `reason`.
- **Lines 200–345 (`check_scenario`)**: Implemented pre-flight deterministic checks for season-solving tools (`evaluate_season`, `shadow_prices`, `sensitivity`, `compare_regions`, `climate_scenarios`, `assess_field_image`):
  - **Rule 1 (Farm size)**: Requires `area_ha` or `owned_ha` to be present in farmer texts or `screen_scenario`, except in `compare_regions` with `mode="same_budget"`.
  - **Rule 2 (Number grounding & scale)**: Checks all scenario numbers, yields, prices, constraints, and payment options against farmer text and previous tool outputs within 1% tolerance. Correctly parses negative signs (`-50`), percentage shares (`10%` -> 0.10), thousands (`mil`, `lucas`, `k`), days to fortnights (`60 días` -> 4), and acres to hectares (`200 acres` -> 80.94 ha).
  - **Rule 3 (Narrowing constraints)**: Restricting `crops` requires each crop to be accompanied by restriction keywords (`solo`, `sólo`, `únicamente`, `nada más`, `only`, `just`) or sowing verbs (`sembrar`, `siembro`, `hacer`, `plantar`, `plant`, `grow`) within 5 words preceding it. Rented land (`rented_land: true`) requires rental keywords (`alquil`, `arrend`, `rent`, `lease`).
- **Lines 348–360 (`jargon`)**: Identifies snake_case identifiers and back-ticked identifiers in generated responses.
- **Lines 362–385 (`correction_message`)**: Added formatting for style problems and appended the instruction: *"If you remove a number, rewrite the whole sentence so it still reads well; never leave an empty parenthesis or a sentence cut in the middle."*

### `dora/agent.py`
- **Lines 41–55 (`SYSTEM_PROMPT`)**: Removed the operations-research specialist referral; updated the carryover instruction to reference the modeling guide while retaining the "cannot evaluate" rule; updated `build_scenario` instruction to refer to section 0 of the modeling guide; added the rule never to change farmer values and that yields do not cap crop area.
- **Lines 65–70 (`Reply`)**: Added `scenario_rejections: list[ScenarioProblem]` and `style_problems: list[str]`.
- **Lines 130–151 (`_answer`)**: Before invoking season-solving tools, if `self.use_verifier` is enabled, calls `check_scenario`. If problems are found, intercepts before the engine, returns `{"error": "scenario_mismatch", "problems": [...], "hint": "..."}` as tool result, logs call with `"rejected": True`, and records problems in `self.scenario_rejections`.
- **Lines 220–247 (`ask`)**: Runs both `verify()` and `jargon()` in the correction loop and populates `style_problems`.

### `dora/modeling_guide.md`
- **Lines 3–30**: Added Section 0 "How to answer" containing all 8 rules (first line decision/gap/NPV, plan, bottleneck bullets, "Lo que entendí", return on capital only when asked, no technical identifiers, no referral, "¿Qué podés hacer?" answer with zero numbers).
- **Lines 142–145**: Added rule to Section 3: "When you ask instead of computing, write only what you understood from the farmer and the question. Do not list MAGyP data or model assumptions..."

### `eval/questions.jsonl`, `eval/build_answers.py`, `eval/answers.jsonl`
- Updated question `q33` to `kind: "decision"` and `field: "best_region"`.
- Regenerated `eval/answers.jsonl` via `build_answers()` (only `q33` updated to `best_region: "iowa"`).

### `eval/run_eval.py`
- **Lines 146–170 (`decision_named`)**: Added parser verifying whether the expected region is identified as the best option in the first sentence or text.
- **Lines 467–480 (`_plan_fields`)**: When `hectares is None`, sets `plan_given: False`, `plan_feasible: None`, and `plan_violations: None`. Empty dictionary `{}` is treated as a feasible plan (sow nothing).
- **Lines 173–205 (`_agent_plan_and_value`)**: Retrieves plan and verified field from the last tool call matching the question scenario (supporting sensitivity parameter rows).
- **Lines 496–500, 574–578**: Updated refusal checks to require both no plan solved AND question/refusal markers. Expanded refusal marker keywords.
- Updated aggregated and run metrics to compute `plan_given_rate` and `feasible_rate` over plans given.

### `eval/rescore.py`
- Created offline rescoring CLI tool recomputing evaluation metrics from saved JSON files without network.

### `docs/model.md`
- Appended `## Verifier and scenario checks (SPEC-27)` describing `check_scenario` mechanics, grounding rules, and lexical limits (verbal numbers like "la mitad del campo" require asking).

### Adjusted Existing Tests
- **`tests/test_e1_baseline.py:134`**: Updated assertion to `bad["plan_feasible"] is None and bad["plan_given"] is False`, exactly as specified in SPEC-27 Section 5 Item 2.
- **`tests/test_economics.py:95, 99`**: Updated mock scenario from `500 ha, $50k` to `400 ha, $100k` and answer text to `200 ha` to match prompt `q08` under `check_scenario` and number verification.
- **`tests/test_agent.py:62`**: Specified `use_verifier=False` on `Agent` in `test_tool_errors_go_back_to_the_model` to test tool runner execution error handling.

---

## 2. Rescore Table for E1 Files (`eval/rescore.py`)

Running `eval/rescore.py` across historical E1 result runs produces the following changes:

| Result File | Condition | Runs | Correct Runs (q17) | Correct Runs (q30) | Correct Runs (q33) | Answer Correctness | Feasible Rate |
|---|---|---|---|---|---|---|---|
| `muse-spark-1_3_no_verifier_20261027_184803.json` | B (no verifier) | 1 | 1 -> 1 (=) | 0 -> 1 (+1) | - | 80.0% -> 83.3% | - |
| `muse-spark-1_3_with_verifier_20261027_184050.json` | C (with verifier) | 1 | 1 -> 1 (=) | 0 -> 1 (+1) | - | 83.3% -> 86.7% | - |
| `muse-spark-1_3_no_verifier_20261028_015053.json` | B (no verifier) | 1 | 0 -> 1 (+1) | 0 -> 1 (+1) | 1 -> 0 (-1) | 83.3% -> 86.1% | - |
| `muse-spark-1_3_with_verifier_20261028_014233.json` | C (with verifier) | 1 | 0 -> 1 (+1) | 1 -> 1 (=) | 1 -> 0 (-1) | 86.1% -> 86.1% | - |
| `muse-spark-1_3_no_verifier_20261030_151832.json` | B (no verifier) | 5 | 3 -> 5 (+2) | 3 -> 4 (+1) | 0 -> 3 (+3) | 95.4% -> 98.5% | 92.1% -> 100.0% |
| `muse-spark-1_3_with_verifier_20261030_152205.json` | C (with verifier) | 5 | 4 -> 5 (+1) | 5 -> 3 (-2) | 1 -> 5 (+4) | 96.9% -> 98.5% | 90.9% -> 100.0% |
| `muse-spark-1_3_baseline_20261030_184350.json` | A (baseline) | 5 | 0 -> 0 (=) | 4 -> 5 (+1) | 0 -> 0 (=) | 38.3% -> 37.8% | 90.9% -> 94.5% |

In all 5-run files, `q06`'s 5 runs become feasible plans under the new definition, raising `feasible_rate` to 100.0% in conditions B and C.

---

## 3. Questions from Test 9 (Resolved)

In initial testing, Test 9 (`tests/test_spec27.py:test_09_check_scenario_eval_set`) flagged the 3 known verbal/unprompted cases (`q05`, `q40`, `q43`). Following the review amendments, all 3 have been resolved and `test_09` now passes with 0 failures (`failing_qids == set()`):

1. **`q05` (Fraction Reading)**: Farmer wrote *"no quiero más de la mitad del campo en maíz"*. `_extract_farmer_numbers()` parses "la mitad" as fraction 0.5 of 500 ha = 250 ha and proportion 0.5, successfully grounding `constraints: [{"type": "max_area", "crop": "corn", "ha": 250}]`.
2. **`q40` (Proportion Boundaries)**: `max_crop_share: 1.0` is accepted as a valid boundary ("sin tope") without requiring explicit farmer numbers.
3. **`q43` (Crops Removal)**: Removed `"crops": ["soybean"]` from the question scenario in `eval/questions_spec26.jsonl` because the prompt did not restrict crops. Regenerated `eval/answers_spec26.jsonl` confirming that the expected answer remains strictly identical (`carryover.tonnes_carried_total == 500.0`, 0 diff).

---

## 4. Live Replies

Live evaluation requires an active Meta API key (`DORA_API_KEY`). In the current offline execution environment, `DORA_API_KEY` is not configured (`os.environ.get("DORA_API_KEY") is None`). All 27 automated acceptance tests in `tests/test_spec27.py` verify the exact agent prompt, verifier rules, rescoring, and tool logic without network.

---

## 5. Spec Amendments & Findings

1. **System Prompt & End-of-Season Rule (`tests/test_storage.py:663`)**:
   SPEC-27 section 6 instructed replacing the carryover line in `SYSTEM_PROMPT` to remove "fortnight 29". However, existing regression test `tests/test_storage.py:663` (`test_spec20_eval_questions_and_end_of_season_rule`) asserts `assert "cannot evaluate" in FULL_SYSTEM_PROMPT`. To satisfy both SPEC-27 acceptance test 15 (which forbids "operations-research" and "fortnight 29") and keep existing test suites passing unchanged without editing `test_storage.py`, the line in `SYSTEM_PROMPT` was phrased:
   `"If the farmer asks about holding grain past July, follow the modeling guide (carry-over needs a quote for that month; otherwise you cannot evaluate it)."`
2. **Economics Telemetry Test (`tests/test_economics.py`)**:
   In `test_1_telemetry_fields_and_no_api_key_in_results`, question `q08` ("Con 400 ha y capital de 100.000 USD...") was previously mocked with `area_ha: 500, own_capital_usd: 50000`. Under SPEC-27, `check_scenario` caught the mismatch between 500/50000 and the farmer's 400/100000. Aligning the mock scenario with `q08` resolved the issue.
3. **Legacy E1 JSON Files in `eval/rescore.py`**:
   Older result files lacked top-level `per_question` or `question_ids` dictionaries. `eval/rescore.py` was updated to dynamically extract question IDs and baseline counts from `detailed_results[0]`.

