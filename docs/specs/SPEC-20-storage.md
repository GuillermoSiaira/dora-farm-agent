# SPEC-20: Ways to store grain, a basis that changes by month, and shrink

**Status:** draft (28/10), to implement on branch `spec-20-storage`. It touches `engine.py`, `scenario.py`, `tools.py`, `schemas.py`, `modeling_guide.md`, `agent.py`, `docs/model.md` and tests.

## Why
The storage review of 28/10 found that the engine's arithmetic is right but storage never pays with the defaults:
- In Balcarce with 500,000 USD of capital, the default 0.8 % monthly price rise stores nothing and the silo's shadow price is 0. Storage only starts above about 1.2 % a month. With the saved Rosario and CBOT curves of 27/10 it stores nothing either. The tests force storage with a 3 % monthly rise.
- There is only one way to store: one capacity and one monthly cost (2 USD/t/month, an assumption with no source). That cost looks like what a commercial elevator charges. A silo bag is paid mostly when it is filled and has almost no capacity limit. In an own silo, the monthly cost is low because the building is already paid for.
- The basis is the same all season. In Iowa the main reason to store is a weak basis at harvest that recovers afterwards. With a flat basis that reason disappears.
- No grain is lost in storage. In reality grain shrinks and loses some quality.
- The season ends in fortnight 29 and no grain may be left. That cuts the storage window: soybean in Argentina can be held about 3 months, safrinha corn in Mato Grosso one month. This is not changed here, but it must be stated in the answers.

After this spec, the question "should I store?" must have an answer that depends on the data, not a fixed "no".

## 1. Ways to store (`storage_options`)
Each option:

| Field | Meaning |
|---|---|
| `id` | name, e.g. `"own_silo"`, `"silo_bag"`, `"elevator"` |
| `kind` | `"own_silo"`, `"silo_bag"` or `"elevator"` (for the report and the guide) |
| `capacity_t` | tonnes; `null` = no limit |
| `fill_cost_usd_t` | paid once, in the harvest fortnight, per tonne put in (bag, bagging and extraction; reception at the elevator) |
| `monthly_cost_usd_t` | paid every fortnight on the stock, at half this value |
| `shrink_at_entry` | share lost when the grain goes in (0.005 = 0.5 %) |
| `shrink_monthly` | share lost per month in storage |
| `max_months` | longest time the grain may stay (a silo bag's useful life); `null` = no limit |

**Legacy behavior.** If `storage_options` is empty, the engine builds a single option from the old fields: `{"id": "own_silo", "kind": "own_silo", "capacity_t": storage_capacity_t, "fill_cost_usd_t": 0, "monthly_cost_usd_t": storage_cost_usd_t_month, "shrink_at_entry": 0, "shrink_monthly": 0, "max_months": null}`. Every existing scenario then gives the same plan and the same NPV.

**Regional data.** A new file `dora/data/storage_<region>.json` for each region, with one entry per `kind` and fields `source`, `as_of`, `placeholder`. **No figure is copied from this spec: every value is read from a publication that was opened, with its page or table, or else marked `placeholder: true` with the reason.** Sources to look for (none checked yet):
- Argentina: INTA publications on silo bag costs and shrink; elevator storage fees (tarifas de acopio) from the Bolsa de Cereales, the Bolsa de Comercio de Rosario or the cooperatives.
- Iowa: Iowa State University Ag Decision Maker, files on the cost of storing grain on the farm and at a commercial elevator.
- Mato Grosso: IMEA or CONAB on storage costs and capacity.

Open decision (see the end): whether the regional options are available by default or only when the farmer talks about storing.

### Engine
Variables for each crop `c`, option `m` and fortnight `p ≥ h_c`:
- `in_{c,m} ≥ 0`: tonnes put into option `m` at harvest (harvest fortnight only);
- `s_{c,p,m} ≥ 0`: tonnes in `m` at the end of `p`;
- `o_{c,p,m} ≥ 0`, for `p > h_c`: tonnes taken out of `m` in `p`.

Sales `v_{c,p,r}` and forward deliveries `f_k` are not split by option. Fortnightly shrink: `δ_m = 1 − (1 − shrink_monthly_m)^{1/2}`.

Grain stock, replacing the current equation:

  p = h_c:  Σ_r v_{c,h,r} + Σ_k f_k·[c, h] + Σ_m in_{c,m} = y_c·x_c
            s_{c,h,m} = (1 − shrink_at_entry_m)·in_{c,m}                     for each m
  p > h_c:  s_{c,p,m} = (1 − δ_m)·s_{c,p−1,m} − o_{c,p,m}                    for each m
            Σ_r v_{c,p,r} + Σ_k f_k·[c, p] = Σ_m o_{c,p,m}

Limits:
- Capacity, for each option with `capacity_t`, every fortnight: `Σ_c s_{c,p,m} ≤ capacity_m`. Options with no limit get no row.
- Life: `s_{c,p,m} = 0` for `p > h_c + 2·max_months_m` (bounds).
- End of season: `s_{c,T−1,m} = 0` for every `m`.

Cash, fortnight `p` (the sign is that of a payment, as with `e_{c,p}`):

  + fill_cost_m·in_{c,m}·[p = h_c] + (monthly_cost_m / 2)·s_{c,p,m}

Storage does not pay the transaction tax (Ley 25.413), as today: 0.6 % of a cost of about 1 USD/t per fortnight is less than one cent, and an elevator usually deducts its fee from the sale settlement, which already pays the tax on the gross price.

### Result
- `Result.storage_shadow_price` stays: the one of `own_silo` if it exists, else zeros (so `summary`, the observatory and the tests keep working).
- New `Result.storage_by_option`: for each option, the peak tonnes, the tonnes per crop and fortnight, the total cost (fill plus monthly), the tonnes lost to shrink, and, for options with a capacity, the shadow price per fortnight and its sum.
- Check that adds up: for each crop, harvest = sales + forward deliveries + shrink.

## 2. A basis that changes by month
- `basis_usd_t[c]` takes a number (as now) or a dict `{"YYYY-MM": USD/t}`. The dict is read like the price curve (`curve_price`): linear between points, flat before the first and after the last. A dict with the same value every month gives the same result as the number.
- The basis files (`basis_<region>.json`) may carry `"basis_by_month"` next to `"basis"`. When it exists, it is used with the curve. Iowa first: ISU's basis publication (the source already named in `basis_iowa.json`) or USDA AMS cash bids. It must be read from the publication; otherwise `placeholder: true`.
- Without a curve, the price keeps rising by `monthly_price_rise`, as now. That default (0.8 %) stays an assumption and is stated as such.

## 3. Storage window and answers
- `evaluate_season` and `shadow_prices` report `storage.window_by_crop`: for each crop, the harvest month, the last month grain may be sold (fortnight `T − 1`, the end of the season), and the months in between.
- They also report `storage.breakeven_by_crop`: for each crop and option, the net price in the last month of the window at which storing until then is worth the same as selling at harvest. Formula, with `λ` the cash values of the solution:

  breakeven = ( π_h·λ_h + fill·λ_h + Σ_{p=h}^{T−2} (monthly/2)·λ_p·kept_p ) / ( λ_{T−1}·kept_{T−1} )

  where `kept_p` is the share of a tonne put in at harvest that is still there at the end of `p`, after shrink. The report shows it next to the model's net price for that month. With no capacity limit binding, storing pays exactly when the model's price is above the breakeven.
- `modeling_guide.md`: "tengo un silo de 800 t" → `own_silo` with `capacity_t` 800; "embolso" → `silo_bag`; "lo dejo en el acopio" → `elevator`. If the farmer gives a cost, it replaces the regional one (the build output says who said what, as now).
- `agent.py` (`SYSTEM_PROMPT`): if the farmer asks about holding grain past the end of the season (e.g. soybean until the next harvest), say that the model ends in that month and cannot evaluate it. Do not extrapolate.
- `docs/model.md`: the new equations, with their lines, and the window as a stated assumption.
- `schemas.py` and `tools._validate`: `storage_options` with type and range checks (capacity ≥ 0, costs ≥ 0, shrink in [0, 0.2], `max_months` > 0), unknown `kind` rejected, ids unique.

## Acceptance tests (`tests/test_storage.py`)
1. **Legacy:** without `storage_options`, the plan and the NPV equal those of `main` today (Balcarce default; the scenarios of `test_storage_against_perturbation` and `test_storage_responds_to_curve`). The existing tests pass unchanged.
2. **One option equal to the legacy fields** gives the same plan and NPV as no option.
3. **Fill cost, by hand:** a single crop with a constant price rise chosen so that storing one month just pays the monthly cost and the interest. With `fill_cost = 0`, storage is used; with a fill cost of 1 USD/t, it is not.
4. **Shrink:** with `shrink_monthly = 0.01` and grain held 4 fortnights, the tonnes sold equal the tonnes put in × `(0.99)^2` (to 1e-6); harvest = sales + shrink.
5. **Life:** a silo bag with `max_months = 2` has no stock after `h + 4`, even with a price rise that pays storing until the end.
6. **Capacity shadow price:** for an option with a capacity that binds, the sum of its duals lies between the left and right derivatives (±1 t), as in `test_engine.py`.
7. **No limit:** an option with `capacity_t = null` adds no row and reports no shadow price.
8. **Choice between options:** own silo of 200 t, cheap per month; unlimited silo bag with a fill cost; a price rise that pays storage. The own silo fills first; the rest goes into the bag only if it pays its fill cost (checked by hand from the breakeven).
9. **Monthly basis:** a dict with the same value every month equals the number; a basis weak at harvest and stronger later (synthetic values in the test, not data) makes Iowa store with the CBOT snapshot of 27/10, and a flat basis does not.
10. **Window:** soybean in Balcarce: harvest fortnight 23, window of 3 months; safrinha corn in Mato Grosso: 1 month.
11. **Breakeven:** in test 3's scenario the reported breakeven equals the hand computation (to 0.01 USD/t), and storage is used exactly when the price is above it.
12. **Validation:** negative capacity, shrink of 0.5, unknown `kind` and repeated ids give errors the model can read.

## Evaluation
Add three questions to `eval/questions.jsonl`, with their expected numbers built by `build_answers.py`:
- "¿Me conviene embolsar la soja hasta julio?" (Balcarce, regional options): the answer gives the breakeven and the model's July price.
- "Tengo un silo de 500 t, ¿cuánto vale agrandarlo?": the shadow price of `own_silo`.
- "¿Y si la guardo hasta la cosecha que viene?": the agent says the model ends in July.

## Live check
In the Gradio demo, Balcarce and Iowa: ask about storing, look at the storage block of the answer, and check that every number passes the verifier.

## Open decision (for G)
Are the regional ways to store on by default?
- **Off by default (recommended):** without a mention of storage, only the farmer's own silo, as now. The 36 evaluation answers do not change; the agent adds the regional options when the farmer asks about storing.
- **On by default:** closer to reality (anyone can bag grain), but the plans of many evaluation questions change and the answers have to be rebuilt.
