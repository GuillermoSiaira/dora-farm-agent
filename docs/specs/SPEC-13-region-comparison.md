# SPEC-13: Compare regions and saved runs side by side

**Status:** to implement. **Branch:** `spec-13-compare`. Do not merge into `main`; it gets reviewed first.

## Why
Right now the demo shows one region at a time, and the observatory shows a fixed table. A farmer or an investor asks a comparative question: "where does the same money work best?" and "what changes if I farm here instead of there?". Two kinds of comparison answer it:

1. **Saved runs:** the user runs several scenarios (different regions, capital, credit, land options) and compares them.
2. **Same money, every region:** one budget, and the engine finds the best plan in each region, under one of two rules (below).

## 1. Engine and tools
New tool `compare_regions(scenario, regions, mode)` in `dora/tools.py`, with its schema in `dora/schemas.py`.
- `mode = "same_farm"`: same hectares, same own capital and credit line, region-specific data (costs, yields, prices, basis, freight, taxes, land price and rent).
- `mode = "same_budget"`: the budget `B` = own capital. In each region the farmer owns no land (`owned_ha = 0`) and may **buy** (`max_buy_ha` large) or **rent in** (`max_rent_in_ha` large) at that region's prices. The engine decides how much land to buy or rent and what to sow. This is the investor's question, and it uses SPEC-10 as it is.
- The tool runs `optimize` once per region and returns, per region:
  - NPV, NPV per hectare farmed, return on capital, return on capital and land;
  - hectares by crop, rented in, bought;
  - capital shadow price, land shadow price, the annualized internal rate per fortnight;
  - freight share of the gross price (freight ÷ price at the farm gate);
  - the `placeholder` flag of every data file used, so provisional data is visible next to its number.
- Regions with provisional data stay in the comparison, marked.

## 2. Demo: a "Comparar / Compare" tab
- **Save run:** a button under the plan saves the current run (inputs and results) with an editable name, default "<region> · <capital> · <date-time>". Runs live in the browser session (`gr.State`), up to 8; a "clear" button empties the list.
- **Compare saved runs** and **Same money, every region** (mode selector) produce:
  - a table, one column per run or region, rows as in section 1, numbers formatted in the current language;
  - chart A: internal rate per fortnight, one line per run, with the market rate as a gray dashed line (same style as the existing chart, so it reads the same way);
  - chart B: bars of return on capital and return on capital and land, side by side per run;
  - chart C: farm-gate price decomposition per region, a stacked bar: destination price − ocean freight − port − inland freight − taxes = farm-gate price (uses SPEC-14; until then, only inland freight and taxes).
- Provisional data: a "dato provisorio / provisional" badge on the column.
- Every label in Spanish and English, through the existing `ui_texts` list in `app.py`.

## 3. Agent
- Modeling guide phrases: "¿dónde me conviene producir?", "comparame Pergamino con Iowa", "si tuviera 2 millones de dólares, ¿dónde compro campo?" → `compare_regions` with the right mode.
- The verifier already checks numbers against tool outputs; the comparison output is a tool output, so nothing new is needed there.

## Acceptance tests (`tests/test_compare.py`), no network
1. `same_farm` over one region returns exactly the numbers of `evaluate_season` for that scenario.
2. `same_farm` over all regions returns one entry per region, each with its `placeholder` flags.
3. `same_budget`: with land price and rent of a region set high enough, the engine neither buys nor rents and keeps the cash at the deposit rate; with them low, it buys or rents. One case each way.
4. `same_budget`: own capital is the only money at the start: bought land × price + first-fortnight payments ≤ capital + credit line.
5. Saving 9 runs keeps the last 8.
6. Chart A has one line per run plus the market-rate line; chart B has two bars per run.
7. All existing tests still pass.
