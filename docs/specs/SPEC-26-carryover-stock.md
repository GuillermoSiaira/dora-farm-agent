# SPEC-26: Grain kept past July, valued at next season's price

**Status:** draft (30/10), to implement on branch `spec-26-carryover`, created from `main` **after** `spec-25-climate-sowing` is merged (both touch the stock equations in `dora/engine.py`). Do not merge into `main`; it gets reviewed first. It changes the model, so it starts a new model version: after the merge, rerun the review checks, regenerate `eval/answers*.jsonl` and tag the version.

**No number is typed by hand.** The price of grain sold next season comes from a quote (a futures or forward price for that month, or the farmer's own), with its source and date. Without a quote for that month there is no carry-over, and the agent says why.

## Why
The season has 30 fortnights, from May to the end of July of the next year, and the engine forces the stock to zero at the end (`bounds[stock_opt[c, T − 1, m]] = (0, 0)`, `dora/engine.py`). Grain still in the silo at the end of July has no value in the model, so keeping grain into the next campaign never pays, even when it does in real life: soybean harvested in April and sold the following spring, or wheat held until the next harvest when the futures curve is in carry.

The farmer's real question is "¿vendo ahora o guardo para la campaña que viene?". Today the agent can only say that the model ends in July (`storage.window_by_crop`). Extending the horizon to two full seasons would double the problem and need next season's crop plan. A terminal value is enough: grain kept at the end of July is worth, today, what it will fetch when sold next season, minus the cost and shrink of keeping it until then and the money tied up.

## 1. Data (`Scenario.carryover`)
Off by default. When given:

```json
"carryover": {
  "sell_month": "2027-12",
  "price_usd_t": {"soybean": 320.0},
  "price_source": "CBOT SX27 settlement, 2026-10-29"
}
```

- `sell_month`: the month the carried grain would be sold. It must be after the season's last month and within the storage option's life (below).
- Price per crop, one of:
  - **from the price curve,** when `price_curve` has an explicit quote for `sell_month` (the curve is not extrapolated past its last month: `_interpolate_monthly` keeps the last value flat, which would invent a price);
  - **from the farmer** (`price_usd_t`), with `price_source` saying where it comes from.
- A crop without a quote for `sell_month` is not carried: its end stock stays at zero, as today, and the report says why.
- The engine never extrapolates `monthly_price_rise` past the season to make up a price.

## 2. The value of one tonne carried
For crop `c` kept in option `m` at the end of fortnight `T − 1` and sold in `sell_month`, which is `k` months after the season's last month:

  V_{c,m} = π^{next}_{c} · (1 − δ_m)^{2k} · (1 + r_i)^{−2k} − Σ_{q=1}^{2k} (monthly_m / 2) · (1 − δ_m)^{q} · (1 + r_i)^{−q}

  (in USD at the end of the season, per tonne in the silo at the end of July; the objective discounts it to today like the final cash)

- `π^{next}_{c}`: the net price at the farm gate for that quote, computed with the same rule as every other sale (`Scenario.net_price_route` on the first route, with that month's freight, marketing, gross receipts and transaction tax). The fortnight index for `sell_month` lies past `T − 1`; the implementer checks that every price and route function accepts it, and does not change any of them for fortnights inside the season.
- `δ_m` is the fortnightly shrink of option `m` (`1 − δ_m = (1 − shrink_monthly_m)^{1/2}`), and the holding cost is paid every fortnight on the stock left at its end, at `monthly_m / 2`: the same conventions as inside the season (`docs/model.md`, "Grain stock").
- `(1 + r_i)^{−q}`: the money tied up, at the fortnightly deposit rate, from the end of the season to each payment and to the sale.
- If option `m` has `max_months_m` and `months already held at T − 1 + k > max_months_m`, then `V_{c,m}` does not exist for that option: its end stock stays at zero.

## 3. The engine (`optimize`)
- For each crop and option with a value: the bound on `s_{c,T−1,m}` becomes `(0, None)` and the objective adds `V_{c,m}·(1+r_i)^{−(T−1)}` per tonne, alongside the final cash (lines 254–270). The capacity rows of the option keep binding in fortnight `T − 1`.
- The value is pre-income-tax, like the end value of bought land; `docs/model.md` says so. With `income_tax_rate > 0`, write in the model doc how the carried value enters the after-tax result (it is not realized profit this season).
- Mass balance check (after solving): `harvest = sales + forward deliveries + shrink + carried stock`, per crop.

## 4. Reports
- `evaluate_season`: `carryover` with, per crop and option, tonnes carried, `V_{c,m}` (USD of today per tonne), the quote used with its source and date, and the crops not carried with the reason (no quote, storage life).
- `storage.window_by_crop`: when carry-over applies, say the grain can be kept into next season and until which month; otherwise keep today's text.
- The modeling guide: when the farmer asks about keeping grain until the next campaign, call `evaluate_season` with `carryover` if there is a quote; if there is none, ask for it or say the model ends in July. Never quote next season's price from memory.

## Acceptance tests (`tests/test_carryover.py`, no network)
1. Without `carryover`, plan, NPV and every shadow price equal `main` in at least 6 scenarios.
2. With a quote high enough, the plan keeps grain to the end of July and reports it carried; with a quote low enough, it sells inside the season. Both checked against `V_{c,m}` computed by hand.
3. `V_{c,m}` from the engine equals the formula of section 2 to 1e-9, with shrink, holding cost and discount.
4. An option whose life ends before `sell_month` carries nothing; an option with capacity carries at most its capacity.
5. A crop without a quote for `sell_month` carries nothing, and the report names it.
6. The curve is not extrapolated: a curve whose last month is before `sell_month` gives no quote.
7. Mass balance with carried stock holds for every crop.
8. The storage capacity dual in fortnight `T − 1` passes the perturbation test (one tonne more and one less) when carry-over makes it bind.

The existing tests must pass unchanged. `eval/questions_spec20.jsonl` q39 ("¿y si guardo hasta la cosecha que viene?") keeps its expected answer without `carryover`; add one new question with a quote and its expected answer from `eval/build_answers.py`.

## Handoff (`docs/handoff/spec-26-carryover.md`)
What was done, the equations with their lines in `engine.py`, the tests, and anything in this spec that turned out to be wrong.

## Review amendments (30/10)
Review of commit `29dace2`. What already holds: without `carryover`, every result equals `main` (39 eval questions and 5 scenarios, stochastic and income tax included, compared field by field: no difference); `V_{c,m}` matches the formula by hand (q43: 298.99 USD/t); `net_price_quote` equals `net_price_route` for every crop at fortnights 10, 20 and 29; the full suite passes (279, 1 skipped). Fix the following on the same branch.

### 1. Income tax: tax the carried value, like the land
`realized_profit` leaves the carried grain out of taxable profit, but its growing costs stay in. So carrying grain works as a tax shelter: in q43 with `income_tax_rate = 0.35` the tax drops to zero and the NPV is the same as with no tax (151,432 USD), while without carry-over the tax takes about 13,000 USD of NPV. The value is not exempt; at most it is taxed later.
- Tax `profit = pre_tax_wealth − own_capital` as before SPEC-26 (it already includes the end value of bought land and the herd). Remove `realized_profit`; `tax_mult` goes back to `profit > 0`.
- `docs/model.md`: the carried grain is valued at `V_{c,m}` in taxable profit, the same treatment as the end value of land. Do not cite a tax law for it; it is a model assumption.
- Test: with `income_tax_rate > 0` and grain carried, `tax = rate · (pre_tax_wealth − own_capital)`, and the NPV is lower than with rate 0.

### 2. The quote is a local price, not Chicago
The engine applies freight, taxes and marketing to the quote as if it were the model's own price point (`price_point`: the port price, Quequén or Rosario, after export duties, like the MAGyP prices). A CBOT price is in Chicago and before Argentine export duties; using it as is overstates the value by a lot. The example in section 1 of this spec (`CBOT SX27`) was wrong.
- `carryover.price_usd_t` is a price at the model's price point: a local futures price for that month (Matba-Rofex) or a buyer's offer. The modeling guide says so: if the farmer gives a Chicago price, ask for the local price; never convert it.
- Fix the example in section 1 and q43. The q43 quote is the farmer's own hypothetical figure (e.g. "el acopio me ofrece 380 USD/t en Quequén para diciembre de 2027"), with `price_source` saying it is the farmer's quote in a test question. No exchange, settlement or date that did not happen.
- Basis for a quote from `price_curve`: `basis_at(c, p_sell)` keeps the last month's basis flat past the season, which invents it. Use the basis only if it is a scalar or has an explicit value for `sell_month`; otherwise that crop has no quote (`reason: "no_basis"`).

### 3. A malformed `sell_month` must not crash the tool
`"sell_month": "dic-2027"` raises an uncaught `ValueError` in `carryover_k`. Validate the format (`YYYY-MM`) in `_validate` and return the same kind of error message as for a month before the season end.

### 4. The stochastic engine (climate scenarios)
With `climate_scenarios`, carried grain enters the objective but `evaluate_season` reports no `carryover` block and the mass balance check does not include it. Report carried tonnes per climate and in expectation, and check `harvest = sales + forwards + shrink + carried` per climate.

### 5. Test 1 compares the branch with itself
`test_1_zero_drift_without_carryover` compares `carryover=None` with the default, which is also `None`. Store the `main` values (NPV, hectares, capital, land, credit and storage duals) for the 6 scenarios as fixed numbers in the test, computed from `main` at `5718721`.

### 6. Unrelated, found in passing (SPEC-25)
In `docs/model.md`, the SPEC-25 section has `\t` read as a tab: `$	ext{sow}_{c,w}$` and others. Replace with `\text`.
