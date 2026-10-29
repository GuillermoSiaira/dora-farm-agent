# SPEC-21: Rotation on the land actually held, a land shadow price that means one more hectare, and taxes in the region comparison

**Status:** draft (28/10), to implement on branch `spec-21-rotation-taxes`, created from `main` **after** `spec-20-storage` is merged (both touch `engine.py` and `tools.py`). The review that motivates it is in `docs/mapa-del-codigo.md`, section 7.2.

## Why
The land and tax review of 28/10, run on `main` (`05902aa`), found:
- **The rotation is a fixed bound computed on the land the farmer could have,** not on the land held: `total_land = owned + rent-in cap + buy cap` (`engine.py`, `optimize`), and `x_c ≤ max_crop_share × total_land`. Iowa with 500 ha owned and up to 1,000 ha to rent sows 750 ha of corn and no soybean: the rotation disappears. The livestock share cap has the same problem.
- **The land shadow price does not say what one more hectare is worth when the rotation binds.** Because the caps are fixed numbers, the dual of the land row measures one more hectare with every crop's cap held still. With 2,000,000 USD of capital: Iowa, own land, reports 0 USD/ha while one more hectare (area and rotation together) adds 720.65 USD; Balcarce reports 46.80 and one more hectare adds 98.06. The agent would tell an Iowa farmer that one more hectare is worth nothing.
- **The region comparison is before taxes.** `compare_regions` reads `taxes_*.json` only to flag them as provisional. No tax enters the engine: not the land tax (Iowa 75 USD/ha, Argentina 15), not gross receipts (Argentina 1 %, Brazil's Funrural 1.5 %), not the transaction tax (Argentina 0.6 %). The comparison promises to treat every region the same, and taxes are where they differ most.
- **The return on capital and land is over 15 months, not a year, and does not say so.** Balcarce: 3.5 % in 29 fortnights, 2.9 % a year, below the 4 % deposit rate.
- **The tax files of Brazil and the United States carry estimates ("~$30/acre", "~$3 USD/ha/ano") without a placeholder flag,** so the comparison reports them as checked.

## 1. Rotation and livestock share on the land held
Land held: `H = owned + rent_in + buy − rent_out` (the right-hand side of the land row, with the decisions moved to the left).

- **Rotation, one row per crop** (replacing the bound `x_c ≤ max_crop_share × total_land`):

  x_c − share·rent_in − share·buy + share·rent_out ≤ share·owned

  with `share = max_crop_share`. Without renting in, buying or renting out, it gives exactly the old bound, so every single-field scenario without land decisions gives the same plan and NPV as `main`.
- **Livestock share** (the row `Σ_a y_a ≤ max_livestock_share × total_land`): the same change, `Σ_a y_a − m·rent_in − m·buy + m·rent_out ≤ m·owned`.
- `total_land` stays only for the infeasibility check of `min_area` (it is the most land the farmer could have) and for the loose bound `y_a ≤ total_land`.
- Report the dual of each crop's rotation row in `Result` (`rotation_shadow_price`, USD per hectare of cap, per crop) and in `evaluate_season` when it is positive: "the rotation costs you X USD per hectare of soybean you cannot add".

## 2. The land shadow price is the value of one more owned hectare
`Result.land_shadow_price` must equal `∂NPV/∂owned`. Owned land appears in several right-hand sides: the land row, every rotation row (× share), the livestock share row (× m), the bound `rent_out ≤ owned`, and the land tax paid in fortnight 0 (`− land_tax × owned` in the cash row). The shadow price is the sum of those duals, each times its coefficient. The test (below) checks it by solving again with one hectare more and one less.

`evaluate_season.land_comparison` keeps its text ("an extra hectare is worth X to you; renting one costs Y; the money tied up in one costs Z a year"), now with the right X.

## 3. Taxes inside the engine in the region comparison
- In `compare_regions` (both modes, and the land-free `farming_only` run), every region gets, from its `taxes_*.json`, the fields the engine already knows: `gross_receipts_rate`, `transaction_tax_rate`, `land_tax_usd_ha_year`. A value the farmer gave in the scenario wins, as today with the land price.
- **Income tax stays out of the engine in the comparison** and is reported next to each region: `npv_after_income_tax_usd` and the rate used, with the note that the rate is that of a company (see the data section) and is an assumption about the taxpayer. The ranking is done on the NPV before income tax and after the other taxes. Reason: the three files use a company rate while most farmers pay as individuals, so applying it would rank regions on a number we cannot defend yet.
- Single-field `evaluate_season` does not change: taxes enter only if the farmer or the model sets them, as now. `modeling_guide.md` adds one line: when the farmer asks for the result "after taxes" in a single field, set those three fields from the country's file and say where they come from.
- Each region entry in the comparison lists the taxes applied (`taxes_applied`: name, rate, source, placeholder).

## 4. Returns with their period
- `return_on_capital` and `return_on_capital_and_land` keep their values (the season, 29 fortnights) and gain `season_months` (14.5) and the annual equivalents `return_on_capital_annual` and `return_on_capital_and_land_annual`, computed as `(1 + r)^(24/29) − 1`, with their `_pct` fields.
- The comparison shows the annual one next to the deposit rate. The agent's prompt says: when a return is quoted, say whether it is for the season or for a year.

## 5. Tax data
- `taxes_brazil.json` and `taxes_united_states.json`: add `"placeholder": true` and a `"_review"` line saying which figures are estimates, until each one is read in its source (the land tax figures first).
- `taxes_argentina.json`: export duties stay as they are (they are only reported in `tax_wedge`; MAGyP prices are already net of them) until the decree in force is read. Do not copy rates from memory or from news. If the decree is read, put its number and date in `export_duties_source`.
- Every `income_tax_source` adds that it is a company rate. Nothing else changes in the income tax data.
- No figure in this spec may be used as data: every number goes into a file only with its source read, or with `placeholder: true`.

## Acceptance tests (`tests/test_rotation_taxes.py`)
1. **Unchanged where nothing should change:** single field, without renting in, buying or renting out (Balcarce default; Iowa and zona núcleo with 2,000,000 USD; one scenario with livestock and `max_livestock_share`): plan and NPV equal those of `main` (to 1e-6).
2. **Rotation on the land held:** Iowa, 500 ha owned, `max_rent_in_ha` 1,000, rent 677.10, 2,000,000 USD: no crop above half of the land held; corn = soybean when both pay.
3. **Renting out shrinks the caps:** a scenario where the farmer rents out part of the land: each crop ≤ share × (owned − rented out).
4. **Land shadow price against perturbation of owned land, rotation free:** Iowa and Balcarce with 2,000,000 USD (the cases of the review): `land_shadow_price` lies between the right and left derivatives of NPV in `owned_ha` (±1 ha). It must be about 720 in Iowa and about 98 in Balcarce, not 0 and 46.80.
5. **The same with land tax and with rent:** with `land_tax_usd_ha_year` = 75 and with a regional rent: the perturbation check holds.
6. **Rotation shadow price:** in test 4's Iowa case, the corn and soybean rotation duals are positive and their sum, times the share, plus the land row's dual, plus the other terms, equals the reported land shadow price.
7. **Taxes in the comparison:** `compare_regions`, 500 ha, 500,000 USD: Iowa's result is lower than without taxes by the land tax (500 × 75 USD in fortnight 0, valued today); Argentina's gross receipts and transaction tax appear in the cash rows; `taxes_applied` lists them with their source and flag; a rate the farmer gives wins over the file.
8. **Income tax only reported:** in the comparison, the plan and the ranking do not depend on the income tax rate; `npv_after_income_tax_usd` = the after-tax NPV computed by hand for one region.
9. **Annual returns:** `return_on_capital_and_land_annual` = `(1 + r)^(24/29) − 1` for the Balcarce case of the review (3.46 % → 2.86 %).
10. **Placeholders:** the comparison flags the taxes of Brazil and the United States as provisional.

The existing test `test_land_against_perturbation` (`tests/test_engine.py`) holds the rotation fixed on purpose to check the old meaning. It is the only existing test that may change: replace it with test 4's check. Any other existing test whose numbers change must not be edited: stop, and list it in the handoff with the old and new numbers and why.

## Evaluation
The questions that use `compare_regions` or `tax_wedge` (4 today) get their expected answers rebuilt with `build_answers.py`. The handoff lists every expected number that changed, old and new.

## Live check
In the demo: compare the four regions for 500 ha and 500,000 USD and ask "¿cuánto vale una hectárea más en Iowa?". Every number must pass the verifier, and the answer must not be "nothing".
