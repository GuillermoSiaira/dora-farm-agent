# SPEC-39: at what price would each crop enter the plan (break-even prices from the duals)

**Status:** ready (3/11). Implement **after SPEC-38 is merged** (it needs the owner's rent in the plan), on branch `spec-39-break-even-prices`, created from `main` at that point. Do not commit and do not merge: write the handoff and Claude reviews. Touch only `dora/engine.py` (read the reduced costs; no change to the model), `dora/tools.py` (a new tool), `dora/schemas.py` (its schema), `dora/modeling_guide.md` (one paragraph), `app.py` (one table in the Scenario tab), `tests/test_tools.py` (the tool list only), a new test file and the handoff.

**Why.** After SPEC-38, with June-2026 margins and today's prices, many owner plans will rent the whole farm out: no crop pays more than the zone's rent. Guillermo (3/11): the farmer then needs to know **at what price each crop would be worth sowing, in each fortnight he can sell it**. That is what linear programming gives for free: the reduced cost of a crop's hectares says how much NPV is lost per hectare forced into the plan; divided by the yield and by the value of a dollar in the sale fortnight, it is how much the price there must rise for the first hectare to break even. DORA already reports the duals of capital, credit, land, storage and constraints; it does not report this one.

## 1. Engine: expose the reduced costs (`dora/engine.py`, `optimize`)
The objective is −NPV (`engine.py:943`), solved with `scipy.optimize.linprog` (HiGHS). After the solve, read `res.lower.marginals` for the hectare variables `ha_w[c, wid]` (one per crop and sowing window). With the objective −NPV, the marginal of a variable at its lower bound 0 is d(−NPV)/d(lower bound): the NPV lost per hectare forced in, ≥ 0. **Check the sign on a small case before using it** (force 1 ha of a crop out of the plan with a `min_area` constraint and compare the NPV drop with the marginal; paste both in the handoff).
Add to `Result`:
- `reduced_cost_usd_ha: dict[str, dict[str, float]]` (crop → window id → NPV lost per hectare, in USD of the plan's start, multiplied by `tax_mult` like the other duals);
- `cash_value_by_fortnight`: the `lam` list already computed (value at the start of 1 USD at fortnight p), if `Result` does not keep it yet.
Nothing else in the engine changes. `_optimize_stochastic` is out of scope: the tool says "not available with climate scenarios" if called with one.

## 2. Tool `break_even_prices(scenario, crops=None, verify=True, lang)` (`dora/tools.py`)
For each crop of the scenario **with 0 ha in the plan** (or the crops passed), and for each of its sowing windows `w` (yield `Y_w` t/ha) and each fortnight `p` in which that crop can be sold (from harvest to the end of the horizon, the same set the sales variables use):
```
gap_net_p   = reduced_cost[c][w] / (Y_w * lam[p])          # USD/t of net price the farmer must receive at p
gap_price_p = gap_net_p / (1 - gross_receipts_rate - transaction_tax_rate)   # back to the quoted price
needed_p    = price_c(p) + gap_price_p                    # price_c(p): the price the plan uses at p, same point (port/FAS) as `price`
```
Take, per fortnight, the window with the smallest `gap_price_p`. Per crop, return:
```python
{
  "crop": c,
  "hectares_now": 0.0,
  "reduced_cost_usd_ha": ...,             # of the best window
  "price_point": "port" | "local_elevator",  # as in farm_gate_decomposition
  "by_fortnight": [{"fortnight": p, "label": fortnight_label(...) or fortnight_name, "price_now_usd_t": ..., "price_needed_usd_t": ..., "rise_pct": ...}, ...],
  "best": {the by_fortnight entry with the smallest rise_pct},
  "whole_curve_rise_usd_t": min over p of gap_price_p,   # if every month's price rose by this much, the crop enters
  "verified": True | False | None,
}
```
**What it means, in the output** (`meaning`, es/en): "Precio al que entra la primera hectárea, con todo lo demás igual. Si el precio sube más, el plan cambia y los otros valores también."
**Verification** (`verify=True`, default): for each crop, re-solve twice with that crop's whole price curve raised by `whole_curve_rise_usd_t × 1.02` and `× 0.98`. `verified = True` if the crop has > 0.5 ha in the first and ≤ 0.5 ha in the second; else `False` and keep the numbers with a note. With `verify=False`, `verified = None`. Use the same mechanism `sensitivity` uses to change a price; do not write a new one.
Crops already in the plan: return them in `already_in_plan` with their hectares and no price (out of scope: that needs ranging, not one dual).
If the plan rents land out, say so in `context`: "Hoy alquilar paga {rent} USD/ha; el cultivo tiene que superar eso."

Add the tool to `schemas.py` (description: "Price each crop not in the plan would need, in each fortnight it can be sold, for the first hectare to be worth sowing. Uses the LP duals and re-solves to check."), to the tool registry, and to the list in `tests/test_tools.py`.

## 3. Guide (`dora/modeling_guide.md`)
```
**At what price would a crop be worth sowing?** When the farmer asks it, or when the plan leaves a crop out or rents all the land, call `break_even_prices`. Quote, per crop, `best` (fortnight, price now, price needed, rise %) and `whole_curve_rise_usd_t`, and say `meaning` in your words: it is the price at which the first hectare enters, with everything else unchanged. If `verified` is false, say the number is approximate.
```

## 4. App (`app.py`, Scenario tab)
Under the plan, when at least one crop has 0 ha: a table `¿A qué precio te convendría sembrar?` / `At what price would it pay to sow?` with columns `Cultivo | Mejor quincena para vender | Precio hoy (USD/t) | Precio para que entre (USD/t) | Suba | Verificado`, and below it, in a closed `Accordion`, the full `by_fortnight` table per crop. Call the tool with `verify=True` only after the main plan is drawn (it re-solves), or behind a button `Calcular precios de indiferencia` if it takes more than 10 s on Guillermo's case: measure and say which in the handoff.

## Tests (`tests/test_spec39.py`, no network, prices from `magyp_june`)
1. **Sign and size of the reduced cost.** A scenario where corn has 0 ha: forcing 1 ha of corn (`min_area` 1) lowers the NPV by the reported reduced cost of its best window, within 1 %.
2. **Price needed works.** For that crop, raising its whole curve by `whole_curve_rise_usd_t × 1.05` makes it enter (> 0.5 ha); by `× 0.95` it does not.
3. **Per fortnight.** For the `best` fortnight only, raising that fortnight's price (and only that one) to `price_needed × 1.05` makes the crop enter.
4. **Taxes.** With `gross_receipts_rate` 0.01 and `transaction_tax_rate` 0.006 the gap is the net gap divided by 0.984 (unit test on the formula).
5. **Crops in the plan** are listed in `already_in_plan` with hectares and no price.
6. **SPEC-38 case:** Southeast Buenos Aires 500 ha owned, 50,000 USD, everything rented out: every crop gets a price, `context` mentions the rent, and test 2 holds for each crop.
7. **Climate scenarios:** the tool returns the "not available" message, no exception.
8. The tool is in `test_tools.py`'s list and runs through `run_tool`.

Full suite as in SPEC-35, plus these. Restore the price files before handing off:
```
git checkout -- dora/data/price_curves/ dora/data/basis_*.json
```

## Handoff (`docs/handoff/spec-39-break-even-prices.md`)
The sign check of 1 with its numbers; for Guillermo's case (Pampas core, 2,000 ha, 500,000 USD) after SPEC-38 and for Southeast Buenos Aires 500 ha: each crop's best fortnight, price now, price needed, rise %, verified; the run time with and without verification; a screenshot of the table; test output. Do not mark anything as passed unless its output proves it.
