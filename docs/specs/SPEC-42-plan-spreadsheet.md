# SPEC-42: the plan as a spreadsheet (export, play with it, send it back)

**Status:** ready (5/11), approved by Guillermo. Implement **after SPEC-41 is committed** (it uses the MCP server of SPEC-40 and the record of SPEC-41), on branch `spec-42-plan-spreadsheet` created from `spec-43-modal-refresh` (SPEC-43 goes first), in **`D:\projects\dora-main`**. Do not merge, do not push. Commit with messages starting `SPEC-42 implementation:`; write the handoff and Claude reviews.

Touch only: `dora/engine.py` (a cash ledger read from the solution; **no change to the model**: same variables, rows, objective and results), a new `dora/spreadsheet.py`, `dora/tools.py` (two tools), `dora/schemas.py` (their schemas), `dora/modeling_guide.md` (one paragraph), `app.py` (download buttons and reading an uploaded `.xlsx`), `mcp_server/server.py` (two tools), `tests/test_tools.py` and `tests/test_spec40.py` (tool lists only), `requirements.txt` (`openpyxl`), a new `requirements-dev.txt` (the formula evaluator for tests), a new `tests/test_spec42.py` and the handoff.

**Why.** A farmer, or the analyst who works for him, lives in a spreadsheet; a chat gives him nothing he can keep, open, show the bank or change. The optimal plan in a format he knows is the bridge: he sees the plan, the cash fortnight by fortnight, where each number comes from, and he can change an assumption and send the file back to DORA to recompute. The spreadsheet is also the most natural thing an accountant's agent asks for through the MCP.

## 1. Cash ledger from the engine (`dora/engine.py`)
The fortnightly cash-balance rows (`engine.py`, "Equalities: cash in every fortnight") already hold every money flow as a coefficient times a variable. While building each row, also record each contribution with a label: `(group, crop_or_item, variable_index, coefficient)`. Groups: `inputs` (fixed and payment-term payments, per crop), `storage_fill`, `storage_monthly`, `sales` (per crop, net of freight, marketing and taxes), `forward_sales`, `rent_in`, `rent_out`, `buy_land`, `livestock_costs`, `livestock_income`, `cow_cull`. After the solve, compute and add to `Result`:
```python
cash_ledger: list[dict[str, dict[str, float]]]   # per fortnight p: group -> crop/item -> USD (inflows positive, outflows negative)
```
plus, per fortnight, `deposit_interest`, `credit_interest`, `credit_drawn` (D[p] − D[p−1] ≥ 0) and `credit_repaid`, and `opening_cash` (b_eq at p = 0). **Identity test:** for every p, `S[p] − D[p] = (1+ri)·S[p−1] − (1+rc)·D[p−1] + Σ ledger[p] (+ opening cash at p = 0)` within 1e-6 USD. The ledger adds labels only; it must not change any number of any existing test. Not for climate scenarios (`_optimize_stochastic`): the export says it is not available with climate scenarios.

## 2. The workbook (`dora/spreadsheet.py`, openpyxl)
`export_plan_xlsx(scenario: dict, lang: str, record: dict | None = None) -> bytes` validates and solves the scenario (with `tools` and `engine`, no new economics) and writes one `.xlsx`. All text in `lang` (es/en), numbers in USD of the plan's start unless the column says otherwise, money with thousands separators, hectares to 0.1, prices to 0.01. Sheets, in this order:

1. **Resumen / Summary.** At the top, in a filled box, the warning: es "Este plan era el óptimo con estos supuestos. Si cambiás algo, pedile a DORA que recalcule: mandá esta planilla por el chat." / en "This plan was the best one under these assumptions. If you change anything, ask DORA to recompute: send this file back in the chat." Then: what to sow (crop, hectares, sowing window), NPV, return on capital, max credit used and when, rent-out comparison (`tenure_comparison`: farm only, rent all, best, break-even rent) when the land is owned, and "what limits the plan" (the binding resources with their shadow prices, same wording the chat uses).
2. **Plan por cultivo / Plan by crop.** One row per crop with hectares > 0: hectares, yield (t/ha), tonnes, average sale price (USD/t, weighted by tonnes sold), cost per hectare, gross income, total cost, margin, margin per hectare. Live formulas (section 3).
3. **Caja por quincena / Cash by fortnight.** One row per fortnight (label from `fortnight_label`, real dates when `start_date` is set): opening cash, inflows and outflows by group (the ledger), deposit and credit interest, credit drawn and repaid, closing cash, debt. A line chart (openpyxl `LineChart`) with closing cash and debt. Live formulas.
4. **Supuestos / Assumptions.** One row per input the engine used: key (machine-readable path, e.g. `prices.soybean`, `price_curve.soybean.12`, `costs.corn.fertilizer`, `own_capital_usd`), description, value, unit, **origin** (from `build_scenario`: "lo dijo el productor", "factura <date>", default regional with its source and date, assumption), and an "edited" column that starts empty. Inputs are unlocked and coloured (light yellow); everything else is formulas or engine values (grey for engine decisions, with a note "decisión de DORA").
5. **Sensibilidad / Sensitivity.** Shadow prices (`shadow_prices`, including the fortnights with scarce capital) and break-even prices (`break_even_prices`, SPEC-39) per crop not in the plan: best fortnight, price now, price needed, rise %, verified. Values, not formulas, with the note: "Valen para un cambio chico, con todo lo demás igual."
6. **Verificación / Verification.** Engine version and fingerprint, `scenario_hash`, `result_hash`, the checks and whether they passed (SPEC-40 provenance), date. If `record` (SPEC-41) is published: `record_hash`, attestation UID, easscan and explorer links; if queued: "registro en cola" and the record id; if not configured: "sin registro on-chain". One line explaining how anyone can check it (`verify_record`).
7. **`_dora`** (hidden, protected): the validated scenario as JSON, the hashes, the engine version and the export date, used to read the file back (section 5). Not shown in the Summary.

File name: `dora-plan-<region>-<YYYY-MM-DD>.xlsx`. Keep it Google-Sheets-friendly: no macros, no data tables, no external links, no array formulas, only SUM, SUMPRODUCT, INDEX, IF, ROUND, cross-sheet references and named ranges; one chart type.

## 3. Live formulas, and the test that they reproduce the engine
The point of the spreadsheet is that the farmer can play with it. Rule: **every farmer-facing assumption is an input cell in Supuestos; every number that depends on it is a formula; the engine's decisions are values.**
- Decisions (values, grey): hectares per crop and window, share of each crop's harvest sold in each fortnight (tonnes sold ÷ tonnes harvested), storage and payment-term choices, credit drawn and repaid, rent-in/out/buy hectares.
- Inputs (Supuestos): price curve per crop and fortnight (plus basis), yield per crop and window, cost per hectare per crop and item, freight, marketing, export duty, gross receipts and transaction tax rates, rent, deposit and credit rates, storage costs, own capital.
- Formulas: tonnes = hectares × yield; tonnes sold in p = tonnes × share(p); net price in p and the input payments in p must follow `Scenario.net_price_route`, `fixed_payments_per_ha_window` and `input_payments_per_ha_window` **exactly** (read them; the timing shares of each cost item are values from the calendar, the amounts are formulas on the cost inputs); cash rows from those; NPV = final wealth discounted at the deposit rate, as the engine does.
- If one ledger group cannot be written as a formula that reproduces the engine to the cent (e.g. multi-leg routes, livestock, payment terms with instalments), write it as values from the ledger, grey, with the note "valor del motor: cambia solo si DORA recalcula", and list it in the handoff. Do not approximate a formula.
- **Test (the one Guillermo asked for):** open the exported file with a formula evaluator (the Python package `formulas`, or `pycel` if `formulas` cannot read the workbook; put it in `requirements-dev.txt`) without changing anything, and compare every formula cell against the engine: closing cash and debt per fortnight, margins per crop, NPV. Tolerance 0.01 USD. Run it on the scenarios of the tests below.
- A second test edits one input in the file (soybean price +10 % in every fortnight), evaluates, and checks that margins and cash moved in the direction and by the amount the arithmetic says (the decisions do not move: that is the warning's point).

## 4. Delivery
- **Tool** `export_plan_spreadsheet(scenario, lang)` in `dora/tools.py`: writes the file to a temp dir and returns `{"file": path, "file_name": ..., "sheets": [...], "formula_groups": [...], "value_only_groups": [...]}`. Guide paragraph (`modeling_guide.md`): "When the farmer asks for the plan in a spreadsheet, Excel, or a file to take to the bank or the accountant, call `export_plan_spreadsheet`. Say that the file has the plan, the cash by fortnight and where every number comes from, and that if he changes an assumption he can send it back and DORA recomputes."
- **App, chat tab:** when the agent's turn called `export_plan_spreadsheet`, show the file as a download under the answer (Gradio `gr.File`/`DownloadButton`), labelled "Descargar planilla del plan" / "Download the plan spreadsheet".
- **App, Scenario tab:** a button `Descargar planilla (.xlsx)` / `Download spreadsheet (.xlsx)` next to the plan, enabled after a plan is computed, exporting the scenario on screen.
- **MCP** (`mcp_server/server.py`): `export_plan_xlsx(scenario, lang="es", record=None)` returns the file as an embedded binary resource (base64, MIME `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`) plus `provenance`; the HTTP server keeps no files (stateless), so no links. `import_plan_xlsx(file_base64, lang="es")` does section 5 and returns its output with `provenance`. Cap the file at 5 MB.

## 5. Round trip (`read_plan_xlsx`)
`read_plan_xlsx(data: bytes, lang) -> dict`:
1. Accept only `.xlsx` (reject `.xlsm`, `.xls`, `.csv` with a clear message), up to 5 MB. Open with openpyxl, `data_only=True` for the Supuestos values; never evaluate or execute anything from the file. A Supuestos value that is a formula without a cached value → that row is ignored and listed in `ignored`.
2. Read `_dora`: the original scenario and hashes. If `_dora` is missing or its JSON hash does not match `scenario_hash`, say it is not a DORA file or was altered in `_dora`, and stop.
3. Compare each Supuestos input with the original; build the changed scenario (keys → scenario fields), validating every edited value with the same ranges as `PARAMETERS`. Edited values get origin "planilla del productor (<date>)". Out-of-range or unreadable values → `rejected` with the reason; the rest go through.
4. Solve the new scenario (`evaluate_season`), and return: `changes` (key, before, after), `plan_before` and `plan_after` (hectares, NPV, max credit, rent-out choice), `what_changed` (crops in/out, hectares moved, NPV difference), the new `scenario`, and the file of the new plan (`export_plan_spreadsheet`).
5. **Chat:** when the farmer uploads an `.xlsx` (the existing `chat_files` input), the app calls `read_plan_xlsx` itself (not the model), adds the result to the turn as a tool result, and lets the agent explain what changed. The verifier checks that answer as any other: every number must come from the read result or the new plan. The new spreadsheet is offered for download. (WhatsApp: out of scope here; `dora/whatsapp.py` does not change.)

## 6. Future scope (not in this spec; write in the handoff what it would take)
Reading a farmer's own spreadsheet in free format (his costs, his yields, his sales) as a data source: the model would read the sheet as a table and propose values with origin "planilla propia del productor", confirmed one by one, like the invoices of SPEC-34/36. Say which parts of `record_document` would serve and what is missing.

## Tests (`tests/test_spec42.py`, no network, no LLM, prices from `magyp_june`)
1. **Ledger identity** (section 1) on: SE Buenos Aires 500 ha owned, 50,000 USD; Pampas core 2,000 ha owned, 500,000 USD; a rented 300 ha case with credit; and SE BA with `allow_rent_out=True`. Every existing engine test still passes unchanged.
2. **Sheets.** The file has the 6 visible sheets in order plus hidden `_dora`; names and the warning text in es and in en.
3. **Formulas reproduce the engine** (section 3) on the four scenarios of test 1: cash, debt, margins and NPV within 0.01 USD. List the value-only groups for each.
4. **Editing moves the formulas** (section 3, second test).
5. **Origins.** In Supuestos, a value the farmer gave has origin "lo dijo el productor", a value from `record_document` has the invoice origin, a regional default has its source and date.
6. **Verification sheet** with hashes equal to SPEC-40's `provenance` for the same scenario; with a fake published record it shows the UID and the easscan link; without chain configured it says "sin registro on-chain".
7. **Round trip, no edits:** export → read → `changes` empty, plan identical.
8. **Round trip, edits:** soybean price −20 % and own capital ×2 → `changes` lists both, the new plan matches `evaluate_season` on the edited scenario, `what_changed` reports the difference.
9. **Rejected and ignored:** a negative yield is rejected with its reason; a formula with no cached value is ignored; the other edits go through.
10. **Not a DORA file / tampered `_dora`** → clear message, no solve. `.xlsm` and `.csv` rejected.
11. **Climate scenarios** → "not available" message, no exception.
12. **Tools and MCP:** `export_plan_spreadsheet` in `test_tools.py`'s list and through `run_tool`; `export_plan_xlsx` and `import_plan_xlsx` in the MCP tool list (update `test_spec40.py`'s count) and an MCP round trip returns a binary resource that opens with openpyxl.
13. **App:** the Scenario button produces a file (Gradio handler called directly), and an uploaded `.xlsx` in the chat goes through `read_plan_xlsx` (agent mocked).

Then the full suite (`python -m pytest -q`) and restore the price files:
```
git checkout -- dora/data/price_curves/ dora/data/basis_*.json
```

## Handoff (`docs/handoff/spec-42-plan-spreadsheet.md`)
- Screenshots of the six sheets for Guillermo's case (Pampas core, 2,000 ha, 500,000 USD), in Spanish.
- The formula test output, and the list of groups that stayed as values and why.
- The edited round trip of test 8 shown as the farmer would see it in the chat (agent mocked, or a real turn if the model is configured; say which).
- **For Guillermo, manual check (Antigravity cannot do it):** upload the exported file to Google Sheets and confirm that formulas, the chart and the hidden sheet survive; write down anything that broke. If LibreOffice is installed, open it headless and recalculate as a second check; it is not installed on this machine today.
- Section 6: what reading a free-format farmer spreadsheet would take.
- Test output. Do not mark anything as passed unless its output proves it.

## Claude's review (6/11): two fixes, after the SPEC-43 fixes (rebase this branch on them first)
1. **The full suite fails: 4 failed, 494 passed.** One is the `test_deploy` workflow test (SPEC-43 review, item 2). The other three are the trace tests (`test_spec40::test_14`, `test_spec41::test_15`, `test_spec43::test_12`): run in the full suite they find `dora/data/basis_argentina.json`, `price_curves/argentina_latest.json` and `cbot_latest.json` modified. Something earlier in the suite calls `feeds.refresh()` for real, and `export_plan_xlsx` does too: it rewrote those three files when Claude exported an example with `DORA_OFFLINE=1`. Fix at the root: `feeds.refresh()` returns `{"status": "offline", ...}` without network or writes when `DORA_OFFLINE=1`, and a `tests/conftest.py` autouse fixture sets `DORA_OFFLINE=1` for every test except the ones that test the feeds themselves with fakes. Then the full suite must pass with `git status --porcelain dora/data observatory` empty and no manual restore. Paste the full-suite line in the handoff.
2. **The cash sheet ignores edited costs.** In `Caja por quincena` the `Insumos` column holds engine values (e.g. `-11508.91` per fortnight), so a farmer who raises a cost in `Supuestos` sees the margin move but not the cash, the debt or the NPV. Input payments are linear and exact as formulas: hectares (engine value) × cost per hectare (the `Supuestos` cell) × the payment share of that fortnight (engine value, can sit in a hidden helper column or sheet). Write them as formulas; keep storage and credit as values with their note. New test: raise one crop's cost by 10% in `Supuestos`, evaluate with `formulas`, and check that the cash sheet's input outflows for that crop change by exactly 10% (to 0.01 USD) and that the NPV moves in the same direction.
