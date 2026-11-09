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

Real pytest output for `tests/test_spec50.py`:
```
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.7.0 -- D:\projects\dora-hackathon\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\projects\dora-hackathon\.claude\worktrees\spec-50-sheet-bench
configfile: pytest.ini
plugins: anyio-4.15.1
collecting ... collected 3 items

tests/test_spec50.py::test_01_formula_evaluator PASSED                   [ 33%]
tests/test_spec50.py::test_02_linearity PASSED                           [ 66%]
tests/test_spec50.py::test_07_json_extraction PASSED                     [100%]

============================== 3 passed in 0.09s ==============================
```

Real output for full test suite (`pytest tests/`):
```
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.7.0
rootdir: D:\projects\dora-hackathon\.claude\worktrees\spec-50-sheet-bench
configfile: pytest.ini
plugins: anyio-4.15.1
collected 529 items

tests\test_agent.py ....                                                 [  0%]
tests\test_agent_polish.py ......                                        [  1%]
tests\test_app.py ..........                                             [  3%]
tests\test_calibration.py ....                                           [  4%]
tests\test_carryover.py ............                                     [  6%]
tests\test_compare.py ......                                             [  7%]
tests\test_constraints.py .........                                      [  9%]
tests\test_count_once.py ...........                                     [ 11%]
tests\test_demo_guide.py ................                                [ 14%]
tests\test_deploy.py .....                                               [ 15%]
tests\test_e1_baseline.py .............                                  [ 18%]
tests\test_e9.py ........s.....                                          [ 20%]
tests\test_economics.py ..........                                       [ 22%]
tests\test_engine.py ........                                            [ 24%]
tests\test_eval.py ....                                                  [ 24%]
tests\test_eval_e5.py .....                                              [ 25%]
tests\test_feeds.py ........s                                            [ 27%]
tests\test_field_image.py .........                                      [ 29%]
tests\test_financing.py ...........                                      [ 31%]
tests\test_income_tax_duals.py .......                                   [ 32%]
tests\test_land_taxes.py ........                                        [ 34%]
tests\test_livestock.py ......                                           [ 35%]
tests\test_multimodal.py .......                                         [ 36%]
tests\test_observatory.py .....                                          [ 37%]
tests\test_prices.py .........                                           [ 39%]
tests\test_regions_map.py .......                                        [ 40%]
tests\test_rotation_taxes.py ..........                                  [ 42%]
tests\test_routes.py ......                                              [ 43%]
tests\test_routes_network.py .....                                       [ 44%]
tests\test_sowing_climate.py .............                               [ 47%]
tests\test_spec27.py ...........................                         [ 52%]
tests\test_spec28.py ...............                                     [ 55%]
tests\test_spec29.py ............                                        [ 57%]
tests\test_spec30.py ...........                                         [ 59%]
tests\test_spec31.py ......                                              [ 60%]
tests\test_spec32.py .....                                               [ 61%]
tests\test_spec33.py .....s                                              [ 62%]
tests\test_spec33b.py .......                                            [ 63%]
tests\test_spec34.py .......                                             [ 65%]
tests\test_spec35.py ......                                              [ 66%]
tests\test_spec36.py ...............                                     [ 69%]
tests\test_spec37.py ...................                                 [ 72%]
tests\test_spec38.py ...........                                         [ 74%]
tests\test_spec39.py ........                                            [ 76%]
tests\test_spec40.py ..............                                      [ 79%]
tests\test_spec41.py ...............                                     [ 81%]
tests\test_spec42.py ..............                                      [ 84%]
tests\test_spec43.py ...............                                     [ 87%]
tests\test_spec44.py .........                                           [ 89%]
tests\test_spec50.py ...                                                 [ 89%]
tests\test_storage.py ................                                   [ 92%]
tests\test_tools.py ..............................                       [ 98%]
tests\test_whatsapp.py .........                                         [100%]

================= 526 passed, 3 skipped in 134.14s (0:02:14) ==================
```
