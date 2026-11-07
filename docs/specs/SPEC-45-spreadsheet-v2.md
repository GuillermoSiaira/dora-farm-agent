# SPEC-45: the spreadsheet v2 (the whole model inside, solvable with OpenSolver, a DORA menu in Google Sheets, sales strategy and visible verification)

**Status:** ready (7/11), approved by Guillermo. Implement in **`D:\projects\dora-main`**, on branch `spec-45-spreadsheet-v2` created from `spec-46-satellite-ndvi` once SPEC-46 is committed (SPEC-45 was reserved first but is implemented after 46; 47 then stacks on 45). Do not merge, do not push. Commit **one phase at a time** (A, B, C below) with messages starting `SPEC-45 implementation (phase X):`; write the handoff and Claude reviews after each phase. **Do not redeploy `serve_app.py` or `serve_mcp.py` before 10/11.** Cost: 0 USD for phases A and B; phase C may call language models, **ask Guillermo first** and say how many calls.

Touch only: `dora/engine.py` (labels for variables and rows, **no change to the model**), `dora/spreadsheet.py`, `dora/tools.py` (one tool and the existing export), `dora/schemas.py`, `dora/modeling_guide.md` (one paragraph), `app.py` (one button and a code box), `mcp_server/server.py` (two tools and one plain HTTP route), new `sheets_addon/` (Apps Script code), new `scripts/make_example_sheets.py`, new `docs/ejemplos/planillas/`, new `eval/sheets_gallery.py` (phase C), `requirements-dev.txt`, new `tests/test_spec45.py`, existing `tests/test_spec42.py` only where a sheet order or name changes, `tests/test_tools.py` and `tests/test_spec40.py` (tool lists only), and the handoff.

**Why.** SPEC-42 gave the farmer the plan as a spreadsheet he can play with, but the engine's decisions are fixed values: if he changes a price, the margins move and the plan does not. Guillermo wants the person to be able to **re-run the optimisation himself** in the spreadsheet he knows (he tested it in Google Sheets with the OpenSolver add-on, which works like Excel's Solver), and to talk to DORA from there. Two things come out of it:
1. **Trust that does not depend on us.** The whole linear programme is in the file: anyone can solve it with an independent solver and get DORA's plan. "No nos creas: resolvelo vos."
2. **A familiar interface.** The farmer or his analyst works in Sheets; a "DORA" menu sends the edited file back to DORA to recompute, verify and say what changed.

**Measured size (Claude, 7/11, `evaluate_season` with the default data):** Pampas core 2,000 ha owned, 500,000 USD → **196 variables, 65 ≤ rows, 116 = rows, 598 non-zeros**; SE Buenos Aires 500 ha, 50,000 USD → 190, 65, 112, 584. Small for a spreadsheet (a 181 × 196 grid, 99 % empty). **Excel's built-in Solver is capped at 200 variables**: DORA sits at the edge and goes over with livestock, storage options or routes. So the file says "use OpenSolver" (no cap; CBC in Excel, Google's solver in Sheets) and only mentions Excel's Solver as "works for small plans".

## Phase A: the model inside the workbook

### A1. Names for every variable and row (`dora/engine.py`)
`_Index.new(label)` keeps a list of variable labels: a short machine key and a Spanish/English description, e.g. `ha[soybean,w1]` "Hectáreas de soja, ventana 1" / "Soybean hectares, window 1"; `sell[corn,p12]`, `stock[soybean,p14,silo_bolsa]`, `S[p5]` "Plata en el banco, quincena 5", `D[p5]` "Deuda, quincena 5", `rent_in`, `rent_out`, `buy`, `heads[cow_calf]`. Every `A_ub.append`/`A_eq.append` also appends a row label: group (`land`, `cash[p]`, `harvest_balance[c,p]`, `storage_capacity[p]`, `credit_line`, `user_constraint[i]`, `livestock_grass[season]`, ...) and description. Add to `Result` an optional `lp: LPModel | None` (filled only when `optimize(sc, keep_lp=True)`), with `c`, `A_ub`, `b_ub`, `A_eq`, `b_eq`, `bounds`, `var_labels`, `row_labels`, `x` (the optimum) and the objective constant (if any). **Identity test:** with `keep_lp=True` every existing engine number is identical; `linprog` on the stored matrices gives the same `x` and NPV. Climate scenarios (`_optimize_stochastic`): not supported, same message as SPEC-42.

### A2. Which coefficients are formulas
SPEC-42 already writes, as live formulas on the **Supuestos** inputs, the net price of each crop in each fortnight (`net_price_route`) and the input payments per hectare per fortnight (cost per ha × payment share). Reuse those helper cells: in the model sheet, a coefficient is a **formula pointing at the helper cell** when it is exactly one of them (e.g. the coefficient of `sell[soybean,p12]` in `cash[p12]` is the net soybean price in p12; the coefficient of `ha[corn,w1]` in `cash[p3]` is minus the corn payment per ha in p3; the coefficient of `ha[c,w]` in `harvest_balance` is minus the yield). Everything else is a value, grey, with the note "valor del motor". The right-hand sides that are inputs (owned land, own capital, credit line, storage capacity, farmer's constraints) are formulas on Supuestos too. Keep a list `formula_linked_inputs` (the Supuestos keys whose edit flows into the model) and `value_only_inputs` (keys that affect a value coefficient: editing them in the sheet needs DORA). Do not approximate a formula: if a coefficient is not exactly a helper cell, it is a value.

### A3. The sheet **Modelo / Model**
Layout, one block, so any solver reads it:
- Row 1: variable descriptions; row 2: variable keys; **row 3: the decision cells** (start = DORA's optimum, yellow, named range `dora_vars`); row 4: lower bounds; row 5: upper bounds (blank = no limit); row 6: objective coefficients; cell `B8` **objective** = `SUMPRODUCT(row6, row3)` (+ constant), named `dora_objective`, label "Valor presente del plan (lo que se maximiza)".
- From row 11: one row per constraint, **equalities first, then ≤ rows** (so each group is a contiguous range): column A description, B key, then the coefficients under each variable (blank for zero), then `LHS = SUMPRODUCT(coefs, dora_vars)`, the sense (`=` or `≤`), and the RHS. Named ranges `dora_eq_lhs`, `dora_eq_rhs`, `dora_le_lhs`, `dora_le_rhs`.
- A frozen header and a short guide at the top right: "Para volver a optimizar: Extensiones → OpenSolver → Solve. El modelo ya está cargado." / en equivalent.
- Coefficients that are formulas look normal; values are grey. Nothing in this sheet is meant to be edited by hand except through Supuestos; protect it with a warning-only protection (the user can override, see A6).

### A4. The model pre-loaded for the solver
Write the **Excel Solver model names** as workbook defined names, which Excel's Solver and OpenSolver for Excel read on open: `solver_opt` (= `Modelo!$B$8`), `solver_typ` = 1 (maximise), `solver_adj` (= the decision range), `solver_neg` = 1 when every lower bound is 0, `solver_lin` = 1 / `solver_eng` = 2 (Simplex LP), `solver_num` = number of constraint entries, and for each entry `solver_lhsN` / `solver_relN` (1 ≤, 2 =, 3 ≥) / `solver_rhsN`: one entry for the equality block, one for the ≤ block, and one per contiguous run of finite upper bounds (and of non-zero lower bounds, if any). Antigravity checks the exact names and codes against the documentation of Excel's Solver and OpenSolver's source, and writes the references in a comment.

**Step 0, before writing A4 (Google Sheets):** how OpenSolver for Google Sheets stores its model is not known yet (named ranges, hidden sheet or developer metadata). Antigravity makes `docs/ejemplos/planillas/lp-minimo.xlsx`, a 3-variable, 2-constraint LP with the Excel Solver names. **Guillermo** (manual, 5 minutes) uploads it to Google Sheets, opens Extensions → OpenSolver, and says whether the model shows up loaded; then defines the same model by hand in OpenSolver, saves it, and sends a screenshot of Data → Named ranges and of the sheet list (including hidden ones). From that, Antigravity writes whatever Sheets' OpenSolver reads (if it is metadata the `.xlsx` cannot carry, the Apps Script of phase B writes it on first open). Record the answer in the handoff.

### A5. Independent re-solve test (the one that matters)
`tests/test_spec45.py` opens the exported file with the formula evaluator of SPEC-42 (`formulas`), reads the model sheet (the evaluated coefficients, bounds, RHS and objective), builds the matrices and solves them with **scipy HiGHS independently of `dora.engine`**. On the four scenarios of SPEC-42's tests and the livestock case: the objective equals DORA's NPV within 0.01 USD and every hectare and sale within 0.01. Then **edit an input in Supuestos** (soybean price +20 % in every fortnight; own capital × 2; corn yield −15 %), evaluate, re-solve the sheet's model, and compare with DORA solving the edited scenario: equal within 0.01 USD **for every edit whose keys are in `formula_linked_inputs`**; for an edit in `value_only_inputs`, the test asserts that the sheet says it needs DORA (A6). This is the property the demo claims; it must hold or the claim goes out.

### A6. Plan of DORA or plan re-solved outside DORA (visible in the sheet)
Hidden sheet `_dora` also stores DORA's decisions and the original Supuestos values. In **Verificación**, live formulas:
- `=IF(SUMPRODUCT(ABS(dora_vars - _dora_vars)) > 0.01, "Plan recalculado fuera de DORA: sin verificar. Mandale la planilla a DORA para verificarlo.", "Plan de DORA, verificado")`, with green/red conditional formatting, repeated in the warning box of **Resumen**.
- A list of edited inputs (`Supuestos` value ≠ original), and if any of them is in `value_only_inputs`: "Este cambio necesita que DORA recalcule: la planilla sola no lo puede reflejar."
- If any model coefficient cell was overwritten by hand (a cell that should be a formula holds a constant, or a value differs from `_dora`): "Cambiaste el modelo: el resultado ya no es comparable con el de DORA."

### A7. Reading back a re-solved file (`read_plan_xlsx`, extends SPEC-42 section 5)
When the uploaded file's decisions differ from DORA's: solve the edited scenario with DORA and compare with the decisions in the file. Same plan within tolerance → "OpenSolver (o el solver que usaste) llegó al mismo plan que DORA: verificado." Different → explain which: an edit DORA reflects and the sheet could not (value-only input), a hand-edited model cell, or a worse solution (lower objective: "el solver se detuvo antes del óptimo"). Return `sheet_plan`, `dora_plan`, `same_plan`, `reason`. The verifier checks the agent's explanation as any other answer.

### A8. Sales strategy sheet **Estrategia de venta / Sales strategy** (from the research map, item 5b)
One row per sale in the plan: crop, fortnight (real date when `start_date` is set), tonnes, channel (`contado a cosecha`, `desde acopio: <option>`, `venta a futuro`), gross price, net price, income; then per crop: how much is sold at harvest, stored and sold later, contracted forward, and the average net price of each channel. Values from the result (`evaluate_season`'s sales, storage and forward outputs), **no new economics**; tonnes are decision values (grey), prices are the helper formulas, incomes are formulas. A short line on top: "Esto es cuándo, cuánto y por dónde vender, según el plan. Si cambian los precios, pedile a DORA que recalcule." Hedging with futures or options as an engine decision is **out of scope** (an extension of its own).

### A9. Visible verification (research map 5b)
Extend **Verificación** so a person sees, without reading hashes: the language model that built the scenario (`model` from the agent, or "armado a mano en la pestaña Escenario"), the date, engine version, the checks passed (in words), the SPEC-40 hashes and, when published, the SPEC-41 record with its links. One sentence on top: "Cada número de este plan lo calculó el motor de DORA; el modelo de lenguaje solo armó el escenario y lo explicó."

### A10. Example spreadsheets now (no language model, no cost)
`scripts/make_example_sheets.py` writes, in es, to `docs/ejemplos/planillas/`: Pampas core 2,000 ha owned 500,000 USD (Guillermo's case); SE Buenos Aires 500 ha 50,000 USD; 300 ha rented with credit; SE BA with `allow_rent_out`; a livestock case (SPEC-30); Iowa 400 ha. Each `.xlsx` under 1 MB, plus a `README.md` saying what each one is and how to open it in Google Sheets and OpenSolver. Guillermo uses these to try the flow before phase B.

## Phase B: Google Sheets with a DORA menu

**Constraint:** a `.xlsx` cannot carry a script, and publishing a Workspace add-on means Google's review (a process we avoid). So: a **template Google Sheet with a bound Apps Script**, owned by Guillermo; its "make a copy" link (`.../copy`) copies the script too. The farmer opens the link, makes a copy, and has the menu.

### B1. Apps Script (`sheets_addon/Code.gs`, `sheets_addon/Sidebar.html`, `sheets_addon/appsscript.json`, versioned in the repo)
Menu **DORA** with:
- **Cargar plan** — a sidebar with two ways: paste a **plan code** (from the app, B3) or fill a short form (region, hectares, own or rented, own capital, crops). Calls DORA (B2), receives the workbook as JSON and writes every sheet of phase A (values, formulas, formats, named ranges, protections, and the OpenSolver model metadata if step 0 found it is needed).
- **Recalcular con DORA** — reads Supuestos (and the decisions) and `_dora`, sends them to DORA, rewrites the workbook with the new plan, and shows in the sidebar `what_changed` (crops in/out, hectares moved, NPV difference) and, if the farmer had re-solved, A7's verdict.
- **Volver al plan de DORA** — restores the decisions from `_dora` (local, no call).
- **¿Qué cambié?** — lists the edited inputs (local).
- **Resolver acá con OpenSolver** — a dialog with the two steps (install once; Extensions → OpenSolver → Solve).
Scopes: `spreadsheets.currentonly`, `script.external_request`, `script.container.ui`; nothing else. No key in the script. Calls go to the public endpoint with the anonymous limits of SPEC-44.
- **Say it plainly in the README and the dialog:** on first use Google shows "Google no verificó esta app" for any unreviewed script; the farmer clicks "Configuración avanzada → Ir a DORA". Verification is a later step if it takes off.

### B2. Endpoint (`mcp_server/server.py`)
Apps Script cannot speak the MCP protocol comfortably, so add a plain HTTP route next to `/mcp`: `POST /api/sheet` with `{"action": "export" | "import", "scenario" | "plan_code" | "sheet": ..., "lang": "es"}`, same auth middleware and anonymous limits (SPEC-44), stateless. `export` returns the workbook as a JSON description (`{"sheets": [{"name", "cells": [[row, col, value_or_formula, style_id]], "merges", "named_ranges", "protections", "hidden"}], "styles": {...}, "solver_model": {...}}`) produced by the **same code** that writes the `.xlsx` (one builder, two writers: openpyxl and JSON). `import` takes the sheet's Supuestos, decisions and `_dora` as JSON and runs A7 and SPEC-42 section 5 (`read_plan_xlsx` on JSON instead of bytes). Also two MCP tools with the same behaviour: `export_plan_sheet_json`, `import_plan_sheet_json`. Not deployed before 10/11.

### B3. App
Next to "Descargar planilla (.xlsx)": **"Abrir en Google Sheets"**, which opens the template's copy link in a new tab and shows the plan code with a copy button: "En la planilla nueva: menú DORA → Cargar plan → pegá este código." The plan code is the validated scenario, compressed (zlib) and base64url, with a 4-character checksum; under 4 KB for every example of A10 (test). No server storage.

### B4. What Guillermo does once
Create the template sheet in his Drive (`DORA — plantilla`), paste the three files (Extensions → Apps Script), set sharing to "anyone with the link can view", and put the copy link in `.env` as `DORA_SHEETS_TEMPLATE_URL` (not a secret, but configuration). The handoff gives the steps with screenshots.

## Phase C: one spreadsheet per certified model (research map 5b), after asking Guillermo

`eval/sheets_gallery.py`: for one farmer question (Guillermo's case, in Spanish), take the scenario each **certified** model built (models certified by the benchmark, research map 4c) from an existing evaluation results file (E11 or later) when it records the built scenario; otherwise, run the agent with each model **only after Guillermo approves the cost**. For each: the spreadsheet (A9 shows which model built it) into `docs/ejemplos/galeria/`. Plus **one rejected case**: the cheapest model alone, without DORA's tools, answering the same question; its answer goes into a one-sheet workbook marked in red "Respuesta sin DORA: números sin respaldo", with the verifier's list of unsupported numbers. A `README.md` table: model, cost of the run, NPV of its plan, same plan as the reference (yes/no), verified (yes/no).

## Tests (`tests/test_spec45.py`, no network, no LLM, `DORA_OFFLINE=1`, prices from `magyp_june`)
1. **Labels:** every variable and row has a label; `keep_lp=True` changes no number of any existing engine test; `linprog` on the stored model reproduces `x` and NPV.
2. **Model sheet layout:** named ranges exist and point at the right cells; equalities before ≤ rows; zeros blank.
3. **Solver names (A4):** the defined names are present with the right references and codes; `solver_num` matches the entries; `lp-minimo.xlsx` solved by the test's own reader gives the known optimum.
4. **Independent re-solve, unedited (A5):** five scenarios, objective within 0.01 USD, decisions within 0.01.
5. **Independent re-solve after edits (A5):** the three edits; linked → equals DORA on the edited scenario; value-only → the sheet's "needs DORA" message is on (evaluated).
6. **Outside-DORA flag (A6):** change one decision cell → the Verification text flips to "Plan recalculado fuera de DORA"; restore → back to "Plan de DORA, verificado". Overwrite a model formula with a constant → "Cambiaste el modelo".
7. **Read back (A7):** a file whose decisions were replaced by the re-solved optimum of an edited scenario → `same_plan: true`; decisions perturbed to a feasible worse point → `same_plan: false`, reason "worse"; hand-edited coefficient → reason "model edited".
8. **Sales strategy (A8):** tonnes per crop add up to the plan's sales; channels match the storage and forward outputs; incomes are formulas that evaluate to the engine's.
9. **Verification text (A9):** model name shown when given, "armado a mano" otherwise; hashes equal SPEC-40's provenance.
10. **Examples (A10):** the script produces the six files, each opens with openpyxl, each under 1 MB, each passes test 4.
11. **JSON writer (B2):** `export` JSON rebuilt into a workbook by a test writer gives the same cells and formulas as the `.xlsx` for two scenarios; `import` JSON of an unedited sheet → no changes; with edits → same result as `read_plan_xlsx` on the equivalent `.xlsx`.
12. **Endpoint (B2):** `/api/sheet` anonymous export works within limits; 21st call in a minute → 429; invalid key → 401 (SPEC-44 rules).
13. **Plan code (B3):** round trip scenario → code → scenario identical; tampered code → checksum error; all A10 codes under 4 KB.
14. **Apps Script (B1):** `node --check` is not available for `.gs`; instead a test parses `Code.gs` for the five menu items and asserts no key, token or URL other than the configured endpoint appears in it.
15. **Tools and MCP:** new tools in `test_tools.py`'s and `test_spec40.py`'s lists; SPEC-42's tests still pass (update sheet order only where the new sheets are inserted: Resumen, Plan por cultivo, Estrategia de venta, Caja por quincena, Supuestos, Modelo, Sensibilidad, Verificación, `_dora`).
16. After the suite, `git status --porcelain dora/data observatory` is empty.

Then the full suite (`python -m pytest -q`), last line in the handoff (0 failed).

## Manual checks for Guillermo (Antigravity cannot do them; list results in the handoff)
1. Step 0 of A4 (OpenSolver in Sheets reads the pre-loaded model or not).
2. Upload `docs/ejemplos/planillas/pampas-core-2000ha.xlsx` to Google Sheets, open OpenSolver, Solve: same NPV as the Resumen (to the dollar). Change the soybean price in Supuestos, Solve again, and compare with DORA's recompute (menu or app).
3. Phase B: make a copy of the template, Cargar plan with a code from the app, Recalcular con DORA after an edit.
4. If Excel is at hand: open the same file, Data → Solver shows the model loaded; with OpenSolver for Excel, Solve gives the same NPV.

## Demo script (Telegraph; Bolsa de Comercio de Rosario)
1. In the app: Guillermo's case (Pampas core, 2,000 ha, 500,000 USD). DORA gives the plan, verified.
2. "Abrir en Google Sheets" → copy → DORA → Cargar plan. The spreadsheet appears: plan, sales strategy, cash by fortnight, and the tab **Modelo**: "Acá está el problema entero que resolvió DORA: 196 variables, 181 restricciones."
3. Extensions → OpenSolver → Solve. Same present value, to the dollar. "No hace falta creernos: lo resolvió otro solver, en tu planilla."
4. Change the soybean price −20 % in Supuestos. The Verification box turns red: "plan recalculado fuera de DORA". Solve again with OpenSolver: the plan changes. DORA → Recalcular con DORA: DORA gets the same plan, turns it green and explains what moved ("pasaste 300 ha de soja a maíz, el valor presente baja X USD").
5. Close: "La planilla es tuya: la podés tocar, resolver y llevar al banco. DORA arma el problema, lo resuelve, lo verifica y lo deja abierto para que cualquiera lo controle."

## Handoff (`docs/handoff/spec-45-spreadsheet-v2.md`), after each phase
What changed; the size of the model sheet for each example; the A5 test output; the list of `value_only_inputs` and why each one is not a formula; step 0's answer; for phase B the template steps and the endpoint check (local only before 10/11); for phase C the table. Do not mark anything as passed unless its output proves it.
