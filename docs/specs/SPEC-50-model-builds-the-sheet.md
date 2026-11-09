# SPEC-50: the model builds the LP spreadsheet (a bench for formulation, graded by a program and audited by a person)

**Status:** ready (9/11/2026), asked for by Guillermo ("escribila").
- **Branch:** `spec-50-sheet-bench`, created from `claude/keen-wilson-695e01`. That branch has the E9 harness, E12 and the daily runner.
- **Worktree:** `D:\projects\dora-hackathon\.claude\worktrees\spec-50-sheet-bench`.
- **Git:** no merge, no push. Commit messages start with `SPEC-50 implementation:`. Write the handoff; Claude reviews.
- **Cost of the implementation: zero.** No test calls a model. The only paid calls come later, through the daily runner, on Kaggle's free quota.

**Touch only:**
- the new package `eval/sheets/` (`problems.py`, `grader.py`, `render.py`, `audit.py`, `__init__.py`) and its data `eval/sheets/data/`;
- the new runner `eval/run_sheets.py`;
- a `runner` field in `eval/daily/run_daily.py`;
- `tests/test_spec50.py`;
- the handoff `docs/handoff/spec-50-sheet-bench.md`.

Do not change the agent, the engine, `eval/run_eval.py` or `eval/run_e9.py`.

## Why
Every experiment so far (E1 to E12) asks a model a farmer's question. The model fills a DORA scenario and the engine builds and solves the LP. That measures whether the model uses the tool well. **It does not measure whether the model can formulate a linear program**, and formulating is what a person does in Excel or Google Sheets.

On 8/11 Gemini inside Google Sheets did exactly that: it built a 500 ha Pergamino LP (`docs/investigacion/2026-11-08-gemini-sheets-vs-dora.md`). The solve was correct, but it **invented the inputs that decide the result** without saying so: capital, the land split, the rent, the rotation caps.

This spec builds a bench where the model writes the whole sheet and a program grades it:
- Does the LP have the right optimum?
- Does every number in it come from the statement?
- Does the model ask, or state its assumptions, when data is missing?

It is also the measurement for the focus decided on 8/11 (`docs/plan/foco-2026-11.md`): small local models specialised in operations research. The modelling recipes distilled from Tow and from Dorfman, Samuelson and Solow (`docs/investigacion/2026-11-08-material-tow-curso.md`, `docs/material/dss/`) enter as arms. Their effect is measured, not assumed.

## 1. What the model returns: a sheet as JSON
Asking a model for an `.xlsx` binary is not reasonable. It returns one JSON object, the same thing a person types into a sheet plus the Solver dialog:

```json
{
  "cells": {"A1": "Cultivo", "B2": 524, "C2": "=B2*B5", "F10": "=SUMPRODUCT(B5:E5,B2:E2)"},
  "variables": "B5:E5",
  "objective": {"cell": "F10", "sense": "max"},
  "constraints": [{"lhs": "F12", "op": "<=", "rhs": "G12"}, {"lhs": "B5:E5", "op": ">=", "rhs": 0}],
  "assumptions": ["capital propio: no lo dijo; supongo 0 y lo pregunto"],
  "questions_to_user": ["¿Cuánto capital propio tenés?"],
  "dual_sheet": {
    "cells": {"A1": "Precio de", "B1": "tierra", "B5": 0, "H2": "=B5*1+C5*0.4"},
    "variables": "B5:D5",
    "price_of_row": [0, 1, 2],
    "objective": {"cell": "H10", "sense": "min"},
    "constraints": [{"lhs": "H2", "op": ">=", "rhs": 650}]
  }
}
```

**The model never computes a price by hand,** just as it never solves the primal by hand: HiGHS solves both. The machine does the arithmetic. The bench measures two things: whether the model can *formulate* the dual, and whether it can *read* the prices.

**`dual_sheet`** is required only when the problem asks for it (`asks_dual`, section 3). It is the dual written as a second sheet, in the same format and with the same formula rules:
- one variable per row of the primal, which is the price of that item;
- `price_of_row[k]` says which primal constraint the k-th dual variable prices (the index in `constraints`);
- one constraint per activity (Tow's recipe: what the activity uses, valued at those prices, compared with what it pays);
- the opposite sense to the primal.

Sign bounds on the prices (`>= 0`, `<= 0`, free) go in `constraints` like any other.

The dual is fundamental here. Shadow prices and indifference prices are how DORA explains a plan ("an extra hectare is worth X"; "sunflower would enter at Y"). The recipe for the dual comes from the primal one. In Tow's table of activities × items, the dual is the transpose:
- each item (row) gets its price;
- each activity (column) gets its dual constraint;
- the type of each row fixes the sign of its price.

**Reading the prices, a second turn.** In problems with `asks_reading` (section 3), after the grader has solved the model's primal, it sends back a sensitivity report of that sheet, the same report Excel's Solver gives:
- the shadow price of each constraint (HiGHS's `marginals`, converted to the "value of one more unit" convention);
- the slack;
- the reduced cost of each variable;
- the ranges of the right-hand side and of the objective coefficients, computed by the grader through re-solves.

It then asks the questions in the problem, as a farmer would ask them. The model answers in JSON: `{"answers": [{"q": 0, "value": 67.12, "unit": "USD/ha", "explanation": "..."}]}`.

**Rules for the content:**
- Cells hold a number, a text, or a formula that starts with `=`.
- **Allowed in formulas:** cell references and ranges in A1 notation on a single sheet; numbers; `+ - * /`; parentheses; `SUM`; `SUMPRODUCT`. Anything else (`IF`, `MAX`, other sheets, names) makes the sheet invalid and is counted as such. These are the formulas Solver and OpenSolver handle in a linear model.
- **Constraints:** `lhs` and `rhs` are a cell, a range or a number. A range compares element by element with a range of the same shape, or with a scalar. `op` is one of `<=`, `>=`, `=`.
- **Text fields:** `assumptions` and `questions_to_user` are free text, and both may be empty.
- **Parsing the answer:** the model may surround the JSON with prose. The grader takes the first balanced JSON object that parses.

## 2. The grader, a program (`eval/sheets/grader.py`)
The grader never calls a model and never uses Python's `eval`. Formulas are evaluated by a small evaluator of our own: tokenizer, then parser, then an evaluation over the cell graph. It detects cycles and rejects any function that is not allowed.

**Extracting the LP from the sheet:**
1. Every formula cell is a function of the variable cells. The grader checks linearity and gets the coefficients by evaluation:
   - with all variables at 0, the value is the constant;
   - with variable *j* at 1 and the rest at 0, the value minus the constant is coefficient *j*;
   - at three random points, seeded, the linear prediction must match the evaluation (tolerance 1e-7 relative). If it does not, the sheet is "nonlinear" and invalid.
2. The objective cell and each constraint row become a row of `A x (op) b`, with the right-hand-side cell also evaluated.
3. The grader solves with HiGHS (`scipy.optimize.linprog`, method `highs`). Variables are free unless a constraint bounds them: the model must state `>= 0`. Forgetting it is a typical formulation error and is measured.

**Comparing with the exact answer:**
- `status`: one of `invalid` (does not parse, a function that is not allowed, nonlinear, a cycle), `infeasible`, `unbounded` or `optimal`.
- `objective_ok`: the optimum is within 0.1 % (relative) or 1 unit (absolute) of the expected value.
- `solution_ok`: each expected decision value (for example, hectares per activity) matches within 0.5 % or 0.5 units. With alternative optima, `objective_ok` counts and `solution_ok` is reported but not required.
- `invented_numbers`: every numeric constant in the sheet, in cells and in formulas, must belong to the problem's **allowed set**:
  - the numbers in the statement, with their trivial forms (percentages as fractions, thousands, simple unit conversions);
  - 0 and 1;
  - the problem's `allowed_extra` list.

  The constants outside that set are listed one by one. This is the Gemini check: "it put a capital of 260,000 that nobody gave it".
- On **incomplete problems** (section 3): `asked_or_declared` is true if the missing data appears in `questions_to_user`, or in `assumptions` with an explicit value. Inventing the missing data silently is the failure that matters most, and it is reported apart.

**Checking the dual sheet** (only when `asks_dual`). The grader extracts the LP of `dual_sheet` the same way as the primal, then runs two checks.
- `dual_structure_ok`: **it is the dual of the model's own primal.** The comparison is with the canonical dual, built by code from the extracted primal `(c, A, b, row types, sense)`:
  - coefficient matrix `Aᵀ`;
  - right-hand side `c`;
  - objective `b`;
  - the sign of each price set by its row type. With `max` and `<=`, the price is >= 0; with `>=`, it is <= 0; with `=`, it is free. With `min`, the signs are mirrored.

  Rows and columns are matched through `price_of_row` and the order of the variables. A dual row multiplied by a positive constant, or written with its sides flipped, is accepted. The convention is the same in `grader.py` and in the recipe.
- `strong_duality_ok`: HiGHS solves the dual sheet, and its optimum equals the primal optimum within 0.1 %.
- `dual_ok` holds when both checks hold. The dual is scored against the model's own primal, so a model with a wrong primal can still write its correct dual. Both results are reported, and the summary separates "correct dual of a correct primal".

**Checking the reading** (only when `asks_reading`). Each answer is compared with the value the grader computes **from the same report it handed to the model**, so the only thing being measured is whether the model read it right:
- a shadow price, with its unit;
- an indifference price: the current price plus or minus the reduced cost (per unit of the activity's price), or the end of the objective-coefficient range;
- how much a resource can grow before its price changes (the right-hand-side range).

`reading_ok` holds when the value is within 0.5 % and the unit is right. If the model's primal is wrong, the reading is still scored on its own report, and reported apart.
- **Not graded:** the free text of the `explanation`. It goes to the human audit (section 5), because it is where the student, or the model, shows that they understood.

**The final score.** A problem is **solved** when it is not incomplete, `status = optimal`, `objective_ok` holds and `invented_numbers` is empty. An incomplete problem is **handled** when `asked_or_declared` holds and nothing else is invented.

## 3. The problems (`eval/sheets/problems.py` → `eval/sheets/data/problems.jsonl`)
Every problem has:
- `id`, `title`, `statement_es`, `statement_en`, `domain`, `difficulty` (1 to 3), `source`;
- `asks_dual` (bool): problems 1, 4, 5, 8, 9 and 10 ask for the dual sheet;
- `asks_reading`: a list of questions, each with `kind` (`shadow_price`, `indifference_price` or `rhs_range`), the constraint or activity, and the text in both languages. Problems 1, 4, 9 and 10 have them. For 9 and 10 the questions are what an extra hectare is worth, the soybean price at which the plan changes, and how much capital can grow before its price changes;
- `reference_lp`: our own formulation, written in code as a function that returns `c`, `A_ub`, `b_ub`, `A_eq`, `b_eq` and `bounds`;
- `expected`: the objective and the decisions, **computed by solving `reference_lp` with HiGHS, never typed by hand**;
- `allowed_extra`;
- `incomplete`: the missing data, or `null`.

**The first set: 12 problems written by us.** We use our own words and our own numbers; nothing is copied from a book. Where a problem is inspired by a type of exercise from Tow, say so in `source` ("inspired by: Tow 1999, production-storage-sale type").
1. Two crops, land and labour (difficulty 1).
2. Diet: minimum cost with three nutrients (1).
3. Transport: 3 origins and 3 destinations (1).
4. Sell now or store: two grains, three silo types, a price now and later (2, Tow type).
5. Pig farmer: grain as the input to livestock, family labour and hired labour (2).
6. Rotation over three periods with rotation rules (2).
7. Production with an intermediate product, made or bought (2).
8. Small sawmill: logs to planks, planks to furniture, two credit tiers (3, inspired by the FAMASA type, with its own numbers).
9. **Pergamino, 500 ha owned**, with all the data given (capital, margins, rotation cap) (2).
10. **Pergamino, 500 ha rented**, with all the data, the rent included (2). Our version of Gemini's case, but complete.
11. **Incomplete:** Gemini's case as Guillermo asked it, with no capital, no rent and no land split (incomplete).
12. **Incomplete:** transport where a destination's demand is missing (incomplete).

**Later, without changing code:**
- problems built from the DSS catalogue (`docs/material/dss/02-ejemplos.jsonl`), only those with `verificado: true`;
- the generator of SPEC-48.

The loader reads extra `.jsonl` files with the same schema.

## 4. The arms (`eval/run_sheets.py`)
Same interface as `eval/run_e9.py`: `--model --base --key-var --env --max-tokens --concurrency --out`, plus `--arms` and `--ids`. The daily runner calls it the same way.

**System prompt:** "you build linear programming models as spreadsheets", followed by the JSON format of section 1, in both languages.

**The arms:**
- **`alone`:** the format only.
- **`recipe`:** the format, plus a modelling recipe of at most 1,200 words in `eval/sheets/data/recipe.es.md` and `.en.md`. It is **written by us**, from our notes on Tow's five-step method (activities, items, input-output coefficients, external flows, balance equations), with the checks an agent should run:
  - does every item have its balance row?
  - are the units of each row the same?
  - did you state non-negativity?
  - is any number not in the statement? If so, ask or declare it.

  **The recipe has a second part, the dual, deduced from the first.** Read Tow's chapter on duality and economic interpretation (book pp. 48–60, in `material-privado/`; a scanned PDF, never copied into the repo). Write in your own words how he goes from the primal table to the dual:
  - one price per item;
  - one dual constraint per activity ("what the activity uses, valued at those prices, is at least what it pays");
  - the signs according to the type of row;
  - how a shadow price and an indifference price are read.

  Add the checks:
  - does every row have its price, with the right sign?
  - does the dual objective equal the primal one?
  - does a row with slack have a price of 0?

  Cite the pages. Keep the whole recipe, both parts, at 1,600 words at most.

  When `docs/material/dss/01-receta-de-modelado.*.md` is reviewed, Claude merges it into this file. The spec does not depend on it.
- **`recipe_examples`:** `recipe` plus two worked examples. Each has a statement, the JSON sheet and a short line of reasoning, and both are built from problems 1 and 4. Both problems are then **excluded** from that arm's score, as E12 did with q01 and q09.

**The output** goes to `<out>/<model>_<arm>.json`: per problem, the model's raw reply, the parsed JSON, the grader's result and the tokens. `<out>/<model>_summary.json` has, per arm:
- `valid_rate`, `optimal_rate`, `solved_rate`;
- `invented_numbers_mean`;
- `handled_incomplete_rate`;
- `dual_ok_rate`, plus the rate of "correct dual of a correct primal";
- `reading_ok_rate`, over the questions asked;
- `missing_nonneg_rate`;
- tokens per problem;
- the cost, when `--usd-per-m` is given.

## 5. The human audit (`eval/sheets/render.py`, `eval/sheets/audit.py`)
A program grades every answer. **Guillermo audits a sample**, because a grader can be wrong as well:
- `render.py` turns each model JSON into a real `.xlsx` with openpyxl:
  - the formulas live in their cells;
  - the variables are coloured;
  - a "Solver" sheet lists the objective and the constraints;
  - a "Corrector" sheet holds the grader's verdict, the solved values and the invented numbers.

  Install openpyxl into `D:\projects\dora-hackathon\.venv`, the venv on D: (`pip install openpyxl`, cache on D:). The xlsx is for people only; the grader never reads it.
- `audit.py` writes one HTML page per run, `<out>/audit.html`. It shows, per problem, the statement, the sheet as a table, the grader's verdict, a link to the xlsx, and a place for Guillermo's verdict: the buttons "correcto", "incorrecto" and "dudoso", plus a note. The verdicts are saved to `eval/sheets/data/audit.jsonl` through a button that downloads a JSON file Claude then commits. A static page needs no server.
- **Sample:** 6 answers per run, seeded. Two the grader passed, two it failed, and two it scored as invented or incomplete.
- **Agreement:** `audit.py --agreement` reports the agreement between grader and person, and lists every disagreement. Each disagreement is a bug in the grader or in the problem, and both get fixed.

## 6. The daily runner (`eval/daily/run_daily.py`)
- **New optional field `runner`** in each queue entry: `"e9"` (the default, today's behaviour) or `"sheets"`. With `sheets`, the runner calls `eval/run_sheets.py` with the same flags.
- **Nothing else in the daily runner changes:** the caps, the quota check, the log and the commit stay as they are.
- **The queue:** do not add entries; Claude does. Add only the test.

## 7. Tests (`tests/test_spec50.py`, offline, no model)
1. The formula evaluator: arithmetic, `SUM` and `SUMPRODUCT` over ranges, precedence, unary minus, cycle detection, and rejection of `IF`, `MAX`, other sheets and Python injection (`__import__`).
2. Linearity: a linear sheet gives the exact coefficients; a sheet with `B5*C5` (two variables) is `nonlinear`.
3. **The round trip:** for each of the 12 problems, a hand-built *correct* sheet JSON (in `tests/fixtures/spec50/`) grades `solved` with the expected objective. Its objective equals `reference_lp` solved by HiGHS within 1e-6.
4. The same correct sheet without `>= 0` is detected as `missing_nonneg`. The grade is then either still `optimal` with a different objective, or `unbounded`, according to the problem.
5. **Invented numbers:** the correct sheet for problem 10 with the rent changed to 180,000 lists `180000` as invented and does not grade `solved`.
6. **Incomplete:** for problem 11, a sheet that puts a capital of 260,000 with no assumption or question is `handled = false`; the same sheet with the question "¿cuánto capital?" is `handled = true`.
7. The JSON extraction from a reply with prose around it, from one with two JSON blocks (it takes the first that parses), and from one with no JSON at all, which is `invalid`.
8. The determinism of `expected`: two runs of `problems.py` give byte-identical files.
9. `run_daily.py`, with `runner: "sheets"`, builds the `run_sheets.py` command. Monkeypatch `subprocess.run`; no network.
10. `render.py` writes an xlsx that openpyxl reopens, with the formula text unchanged in its cells.
11. **The dual sheet.** For each problem with `asks_dual`, the fixture's correct dual sheet gives `dual_ok`. Each broken version fails:
    - a price with the wrong sign bound fails `dual_structure_ok`;
    - a dual row whose coefficients are not the transposed column fails `dual_structure_ok`;
    - the primal's sense left unchanged (`max` instead of `min`) fails `dual_structure_ok`.

    A dual row multiplied by 2, or with its sides flipped, still passes. The canonical dual, built by code, matches HiGHS's `marginals` in the convention of section 1, and strong duality holds within 1e-6, on all 12 reference LPs.
12. **The report and the reading.**
    - For problems 1, 4, 9 and 10, the report's ranges match a direct check by re-solving. Take the price at the end of the range, then move it by 1 % to either side: the plan does not change on the inside and does change on the outside.
    - The indifference price read from the report equals the bisection on `reference_lp` within 0.5 %.
    - A reading answer with the right value and the wrong unit fails `reading_ok`.

## 8. Handoff
- The table of the 12 problems: their expected objective and how many variables and rows each has.
- The output of `pytest tests/test_spec50.py` and of the full suite.
- An `audit.html` built from the test fixtures (no model involved), so Guillermo sees the page before the first real run.
- What is still open about the allowed set of numbers: which conversions you accepted, and why.

## Not in this spec
- Running models. Claude adds the queue entries after reviewing:
  - Gemini 3.1 Flash Lite, GPT-5.4 nano and Granite (the cheap models, the focus);
  - Gemini 3 Flash (the one people have inside Sheets);
  - Claude Sonnet 5 (the ceiling);
  - later, the open local models.
- Multiple sheets, integer variables, and nonlinear Solver models.
- Training on these sheets, for example a LoRA trained on correct sheets. It comes after, with the split of SPEC-48 and its own cost approval.

## What we learn
- Whether a small model can **formulate**, not only call a tool, and how much the recipe and the examples add. That is the evidence behind "teaching models to formulate".
- Whether a model can **formulate the dual** (Tow's recipe) and **read** the shadow and indifference prices from a solver report. That is the economic reading of the plan, the part that is hardest to teach. The computation is always done by HiGHS, never by the model.
- How often models **invent data** without saying so, which is the risk that makes the verifier necessary in a company.
- Whether a program can grade a formulation reliably, measured against a person. That is what turns a teacher's correction into a bench that scales.
