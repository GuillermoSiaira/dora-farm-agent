# SPEC-50 Handoff: The model builds the LP spreadsheet

**Branch:** `spec-50-sheet-bench`
**Worktree:** `D:\projects\dora-hackathon\.claude\worktrees\spec-50-sheet-bench`

---

## Commit 1: Formula Evaluator, LP Extraction, and Grader

Implemented in commit 1:
- **`eval/sheets/evaluator.py`**:
  - Tokenizer and recursive descent AST parser supporting:
    - Scalar arithmetic: `+`, `-`, `*`, `/`, unary `-`, parentheses
    - Cell references in A1 notation (e.g. `B5`)
    - Range operations with `SUM(B5:E5)` and `SUMPRODUCT(B5:E5, B2:E2)`
  - Cycle detection using DFS with graph traversal (`CycleError`).
  - Strict security whitelist:
    - Whitelisted formula functions: only `SUM` and `SUMPRODUCT`.
    - Disallowed functions (`IF`, `MAX`, `MIN`, etc.) raise `InvalidSheetError`.
    - Disallowed references (cross-sheet `Sheet2!A1`, named ranges) raise `InvalidSheetError`.
    - Absolute rejection of Python reflection/execution (`eval`, `exec`, `__import__`, etc.).
- **`eval/sheets/grader.py`**:
  - `grade_sheet(model_input, expected_objective, allowed_numbers, ...)`
  - Linearity verification:
    - Constant evaluation (all decision variables = 0).
    - Unit gradient extraction per variable $j$ (variable $j=1$, others $0$).
    - Verification at 3 seeded random evaluation points (relative tolerance $10^{-7}$). Discrepancy marks formulation as `nonlinear`.
  - Linear programming solver via HiGHS (`scipy.optimize.linprog(method='highs')`):
    - Variables are treated as free `(None, None)` by default to accurately detect formulation omissions.
    - Explicit detection of `missing_nonneg` when no constraint specifies non-negativity.
  - Number extraction & Allowed Set:
    - Extracts all numeric literals from cells and formulas.
    - Computes allowed set from problem statement numbers, standard scales/units ($x/100$, $x \times 1000$, $x/1000$, $x \times 100$, $1 - x/100$, fractions), $0$, $1$, and `allowed_extra`.
    - Identifies `invented_numbers`.
  - Incomplete problem handling (`asked_or_declared`):
    - Verifies whether missing problem parameters are queried in `questions_to_user` or declared in `assumptions`.
  - JSON Extraction (`extract_sheet_json`):
    - Robust extraction handling markdown code fences (` ```json `), raw text, and multiple JSON blocks (selects first valid block).
- **`tests/test_spec50.py`**:
  - `test_01_formula_evaluator`
  - `test_02_linearity`
  - `test_07_json_extraction`

---

## Review Feedback Adjustments (Pre-Commit 2)

Per reviewer instructions:
1. **Decimal & Thousands Parsing in Text Fallback:**
   - Fixed regex and string cleaning in `extract_numbers_from_text`. Tokens like `0.4` and `1.5` are parsed as floats `0.4` and `1.5` (avoiding truncation/scaling to 4 or 15).
   - Correctly handles formats like `260.000`, `180,000`, and `14%`.
   - Each problem in `eval/sheets/problems.py` has an explicit `statement_numbers` list, keeping text parsing purely as fallback.
2. **Strict Allowed Set Rules:**
   - Universal constants are strictly restricted to `{0.0, 1.0, -1.0}`.
   - Division by 100 ($x/100$) is permitted **only** for numbers explicitly given as percentages (`percentage_numbers`).
   - Domain-specific conversions (e.g. days per month, units per ton) are moved to each problem's `allowed_extra` with explicit comments.
   - Verified with a dedicated unit test in `test_statement_numbers_text_fallback_and_strict_allowed` ensuring that invented numbers `10.0` and `100.0` are flagged as invented and fail grading.

---

## Commit 2: The 12 Problems, Reference LPs, Fixtures, Dual Checker, Sensitivity, and Recipe

Implemented in commit 2:
- **`eval/sheets/problems.py`**:
  - Complete definitions of the 12 benchmark problems with realistic domain data and original text in Spanish and English:
    1. `prob_01`: Two crops, land and labour (Tow 1999) - asks dual & reading
    2. `prob_02`: Minimum cost feed ration (nutrition) - asks dual
    3. `prob_03`: Multi-origin multi-destination logistics (transportation)
    4. `prob_04`: Harvest sale vs silo storage (grain marketing) - asks reading
    5. `prob_05`: Swine breeding and on-farm corn consumption (farm integration) - asks dual
    6. `prob_06`: Irrigation allocation under water deficit (water management)
    7. `prob_07`: Agricultural machinery repair parts blending (manufacturing)
    8. `prob_08`: Sunflower oil processing and byproduct meal blending - asks dual
    9. `prob_09`: Biofuel blending with octane and emissions limits - asks reading
    10. `prob_10`: Three-year crop rotation with fixed land lease rent - asks reading
    11. `prob_11`: Working capital financing with unstated available capital (`incomplete: "capital"`)
    12. `prob_12`: Pasture cattle stocking rate with unstated forage biomass (`incomplete: "biomasa"`)
  - Deterministic solver `_solve_lp_dict` running HiGHS via `scipy.optimize.linprog`.
  - JSONL serializer `dump_problems_jsonl` writing deterministically to `eval/sheets/data/problems.jsonl`.
- **`eval/sheets/grader.py` updates**:
  - `check_dual_sheet(primal_info, dual_sheet_data, ...)`:
    - Validates dual sense inversion (`min` for max primal, `max` for min primal).
    - Checks dual variable indices and bounds (`y_i >= 0`).
    - Maps dual variables to primal constraints via `price_of_row`.
    - Checks dual structural constraint matrix against transposed primal columns with positive multipliers ($\lambda > 0$).
    - Verifies strong duality ($|z_D^* - z_P^*| \le 10^{-3} (1 + |z_P^*|)$).
  - `generate_sensitivity_report(primal_info, solver_res, opt_val)`:
    - Shadow prices and slack variables for constraints.
    - Reduced costs for decision variables.
    - Allowable RHS ranges computed by bisection on boundary re-solves.
    - Allowable objective ranges computed by bisection maintaining plan stability.
  - `grade_reading(answers, report, problem)`:
    - Validates economic interpretation answers against sensitivity report.
    - Enforces expected physical/economic units (e.g. `USD/ha`, `USD/hora`, `ha`). Wrong unit fails `reading_ok`.
- **Hand-built Fixtures (`tests/fixtures/spec50/`)**:
  - `prob_01.json` through `prob_12.json` written with formulas, decision variables, objectives, and constraints.
  - All fixtures grade `solved = True` (or `handled = True` for incomplete problems 11 and 12).
- **Tow's Spreadsheet Recipe**:
  - `eval/sheets/data/recipe.es.md`: 1,158 words (limit $\le 1600$).
  - `eval/sheets/data/recipe.en.md`: 1,124 words (limit $\le 1600$).
  - Covers Tow's 5-step primal spreadsheet layout and the dual sheet economic interpretation (pp. 48–60).
- **`tests/test_spec50.py`**:
  - Tests 1, 2, 7 (Commit 1)
  - Strict allowed numbers & text fallback test (Review fix)
  - Test 3: Round trip across all 12 problems against HiGHS reference solutions
  - Test 4: Missing non-negativity detection (missing `>= 0` yields unbounded or suboptimal)
  - Test 5: Invented numbers detection (e.g. rent changed to 180,000)
  - Test 6: Incomplete problem handling (`handled = False` without assumptions, `True` with declaration/question)
  - Test 8: Determinism of problems JSONL serialization
  - Test 11: Dual sheet checking across dual-enabled problems (1, 2, 5, 8)
  - Test 12: Sensitivity report allowable ranges perturbation check and reading question grading

---

### Table of Benchmark Problems

| ID | Title | Domain | Vars | Cons | Dual | Reading | Incomplete | Expected Objective |
|---|---|---|---|---|---|---|---|---|
| `prob_01` | Dos cultivos, tierra y trabajo | Agriculture | 2 | 2 | Yes | Yes | None | 36,000.0 USD |
| `prob_02` | Dieta de costo mínimo | Nutrition | 2 | 3 | Yes | No | None | 1.10 USD |
| `prob_03` | Transporte 3x3 | Logistics | 9 | 6 | No | No | None | 4,200.0 USD |
| `prob_04` | Venta vs almacenamiento | Grain marketing | 8 | 5 | No | Yes | None | 244,250.0 USD |
| `prob_05` | Producción porcina y grano | Farm integration | 5 | 5 | Yes | No | None | 31,440.0 USD |
| `prob_06` | Riego bajo déficit | Water management | 3 | 3 | No | No | None | 57,000.0 USD |
| `prob_07` | Repuestos de maquinaria | Manufacturing | 3 | 3 | No | No | None | 2,700.0 USD |
| `prob_08` | Procesamiento de girasol | Agribusiness | 4 | 5 | Yes | No | None | 13,000.0 USD |
| `prob_09` | Mezcla de biocombustible | Energy / blending | 3 | 4 | No | Yes | None | 760.0 USD |
| `prob_10` | Rotación de cultivos con alquiler | Crop rotation | 3 | 3 | No | Yes | None | 34,000.0 USD |
| `prob_11` | Financiamiento de campaña | Finance | 2 | 3 | No | No | `capital` | Handled (assumptions / questions) |
| `prob_12` | Carga ganadera en pastoreo | Livestock | 2 | 2 | No | No | `biomasa` | Handled (assumptions / questions) |

---

### Strict Allowed Set Reference Table

Universal allowed set: `{0.0, 1.0, -1.0}`.
Division by 100 ($x/100$) only for explicit percentage numbers.
Explicit `allowed_extra` domain numbers:
- `prob_04`: none
- `prob_05`: none
- `prob_08`: none
- `prob_09`: none
- `prob_10`: none
- `prob_11`: declared via `assumptions` in model JSON
- `prob_12`: declared via `assumptions` in model JSON

---

### Test Suite Results

`pytest tests/test_spec50.py -v`:
```
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.7.0 -- D:\projects\dora-hackathon\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\projects\dora-hackathon\.claude\worktrees\spec-50-sheet-bench
configfile: pytest.ini
plugins: anyio-4.15.1
collecting ... collected 11 items

tests/test_spec50.py::test_01_formula_evaluator PASSED                   [  9%]
tests/test_spec50.py::test_02_linearity PASSED                           [ 18%]
tests/test_spec50.py::test_07_json_extraction PASSED                     [ 27%]
tests/test_spec50.py::test_statement_numbers_text_fallback_and_strict_allowed PASSED [ 36%]
tests/test_spec50.py::test_03_round_trip PASSED                          [ 45%]
tests/test_spec50.py::test_04_missing_nonneg PASSED                      [ 54%]
tests/test_spec50.py::test_05_invented_numbers PASSED                    [ 63%]
tests/test_spec50.py::test_06_incomplete_problem PASSED                  [ 72%]
tests/test_spec50.py::test_08_determinism PASSED                         [ 81%]
tests/test_spec50.py::test_11_dual_sheet PASSED                          [ 90%]
tests/test_spec50.py::test_12_sensitivity_report_and_reading PASSED      [100%]

============================= 11 passed in 19.05s =============================
```

Full repository test suite (`pytest -q`):
```
534 passed, 3 skipped in 150.65s (0:02:30)
```
0 failures.
