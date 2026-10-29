# SPEC-24: Sowing dates as a decision, and the climate outlook as scenarios

**Status:** draft (29/10), to implement on branch `spec-24-climate-sowing`, created from `main` **after** `spec-23-demo-guide` is merged (both touch `dora/agent.py` and `dora/modeling_guide.md`).

**This SPEC lifts the model freeze on purpose** (G's decision, 29/10). The freeze (tag `model-frozen-2026-10-29`) was a working rule so that every experiment measures the same engine and the math review (SPEC-20, 21, 22) stays valid. Part 1 and Part 4 change the equations. So, after the merge: rerun the review checks (resolve with one unit more and one less, `tests/test_engine.py` style), regenerate `eval/answers*.jsonl` with `eval/build_answers.py`, tag `model-frozen-<date>`, and only then run E1 (`docs/plan-de-pruebas.md`).

**No number is typed by hand.** Every yield by sowing date, yield by type of year and probability comes from a source that is read and cited (file, page, date). Until it is read, the entry is `"placeholder": true` and the agent says so.

## Why
At the start of the coarse season (corn, soybean, sunflower) the farmer decides today: what to sow, **when** to sow it, all at once or in stages. That decides when each lot is harvested, so when there is grain to sell or store, and when the money comes in to pay the credit back. The decision depends on the climate outlook. Today DORA cannot take it:
- **The sowing date is not a decision.** Each crop has one sowing and one harvest fortnight, fixed in `REGIONS[...]["calendar"]` (`dora/scenario.py`). For example, corn in Balcarce is sown in fortnight 11 and harvested in 22. The engine cannot weigh early corn against late corn, or first-crop soybean against second-crop soybean, or say that staggering pays.
- **There is no climate data.** Yields are each source's averages (MAGyP, ISU, IMEA), one scenario. The national services publish seasonal outlooks every month as probabilities (below, near or above normal rainfall and temperature): SMN in Argentina, NOAA CPC in the United States, INMET and CPTEC in Brazil. DORA does not read them.
- **One forecast in a deterministic model sells a certainty that the climate does not give.** An outlook is a probability. The right answer is a plan that holds across climates, with what it loses in each one.

## 1. Sowing windows (engine)

### Data
Per region and crop, a list of sowing windows in `dora/data/sowing_<region>.json`:

```json
{"crop": "corn", "windows": [
  {"id": "early", "sowing": 11, "harvest": 22, "fertilizer": {"11": 0.5, "14": 0.5}, "crop_protection": {"12": 1.0},
   "yield_factor": 1.0, "source": "...", "as_of": "...", "placeholder": false},
  {"id": "late", "sowing": 15, "harvest": 26, "fertilizer": {"15": 0.5, "17": 0.5}, "crop_protection": {"16": 1.0},
   "yield_factor": null, "source": "", "placeholder": true}
]}
```

- `yield_factor` multiplies the crop's yield (MAGyP or the farmer's), or `yield_t_ha` gives it directly. A window with no read source keeps `placeholder: true`. In that case the engine still uses it **only when the farmer asks for that window or gives its yield**, and the report flags it.
- Sources to read (the implementer reads them and cites page and date; none is assumed here): INTA trials of yield by sowing date (Balcarce, Pergamino), Iowa State University Extension planting-date studies, Embrapa and IMEA for soybean and safrinha corn in Mato Grosso.
- **The default is one window per crop, equal to today's calendar.** Without `sowing_windows`, every scenario gives exactly the same plan, NPV and shadow prices as `main` (test 1).
- The farmer can override any window: `sowing_windows: {"corn": [{"id": "late", "sowing": 15, "harvest": 26, "yield_t_ha": 7.0}]}`.

### Variables and equations
- `x_{c,w} ≥ 0`: hectares of crop `c` sown in window `w`. `x_c = Σ_w x_{c,w}` stays as the crop's area: rotation, `min_area`, `max_area` and `min_share` apply to `x_c`, as now.
- Payments: each window has its own calendar, so `e_{c,w,p}` replaces `e_{c,p}` in the cash row. With `payment_options` (SPEC-19), the split is `Σ_t z_{c,w,t} = x_{c,w}`, and each term's payments are shifted from that window's purchase dates.
- Harvest arrives on several dates for the same crop. Let `H_c = {h_{c,w}}` be the harvest fortnights of crop `c` and `h_c^0 = min H_c`. The grain is the same product, so it shares one stock per storage option:
  - Entry into storage `in_{c,m,p}` exists for every `p ∈ H_c` (not only at `h_c`); its fill cost `fill_m` is paid in `p`.
  - Sales balance, for every `p ≥ h_c^0`:
    `Σ_r v_{c,p,r} + Σ_k f_k·[crop_k = c, p_k = p] + Σ_m in_{c,m,p} − Σ_m o_{c,p,m} = Σ_w y_{c,w}·x_{c,w}·[h_{c,w} = p]`
    (`o_{c,p,m}` exists for `p > h_c^0`; `in_{c,m,p} = 0` when `p ∉ H_c`).
  - Stock, for every `p ≥ h_c^0` and option `m`:
    `s_{c,p,m} = (1 − δ_m)·s_{c,p−1,m} − o_{c,p,m} + (1 − shrink_entry_m)·in_{c,m,p}` (with `s_{c,h_c^0−1,m} = 0`).
  - Storage life `max_months_m`: counted from each entry. With several entry dates this needs stock by cohort. Simplest rule, to be stated in `docs/model.md`: count the life from `h_c^0`, which is conservative. Or keep `s` by entry fortnight if the implementer finds it simple. Say which one was done.
  - Mass balance check (`engine.py`, after solving): `Σ_w y_{c,w}·x_{c,w} = sales + forward + shrink` for each crop.
- **Machinery, optional (the real reason to stagger):** `sowing_capacity_ha_per_fortnight` (planter) and `harvest_capacity_ha_per_fortnight` (combine, own or contracted). One row per fortnight: `Σ_{c,w: sowing_{c,w} = p} x_{c,w} ≤ cap` and the same for harvest. Report their duals: "one more hectare of planting capacity in the second half of October is worth X". Without these fields, no rows.

### Reports
- `evaluate_season`: `hectares` stays per crop (summed), plus `hectares_by_window` `{crop: {window: ha}}`, `harvest_t_by_fortnight`, and the placeholder flags of the windows used.
- `shadow_prices`: the machinery duals by fortnight, when present.
- `docs/model.md`: the new indices, variables and equations, with their lines, as the other sections.

## 2. Climate outlook, live (feeds)
- `dora/climate.py` with `climate_outlook(region)`: the latest seasonal outlook for the region's point (`REGIONS[...]["coords"]`). It returns the next three-month periods, with the probability of rainfall below, near and above normal (and temperature, if published), plus `source`, `issued`, `as_of` and `url`.
  - Argentina: SMN, "Pronóstico climático trimestral". United States: NOAA CPC, 3-month outlooks. Brazil: INMET / CPTEC, seasonal forecast.
  - The implementer checks which of them publish machine-readable data (files, an API, GIS layers). If a service only publishes images or PDFs, the snapshot is entered by hand from the published document, with its URL and date, and flagged `"manual": true`. It is never estimated.
  - Cached copy in `dora/data/climate/`. If the service does not respond, the last copy is used and says so (same behavior as prices, E4).
- Optional, informative only: `weather_forecast(region)`, the national service's short-range forecast (a storm front, rain in the next days). It is useful for harvest and logistics, and the agent may mention it, **but no number of the plan comes from it**.
- New tool in `TOOLS` and `TOOL_SCHEMAS`: `climate_outlook`.

## 3. The climate as yield scenarios (no new equations)
- Data: `dora/data/climate_yields_<region>.json`. Per crop (and window, when Part 1 gives them), the yield in dry, normal and wet years, with:
  - Yields by year from MAGyP "Estimaciones Agrícolas" by department (Argentina), USDA NASS county yields (Iowa), and CONAB / IBGE municipal data (Mato Grosso).
  - Each year classified as dry, normal or wet by the season's rainfall at the nearest station of SMN, NOAA or INMET, using the terciles of the series. The classification rule and the years used are written in the file.
  - `placeholder: true` until both are read.
- Probabilities: the outlook's terciles for the season's critical months (below normal → dry, near → normal, above → wet). This mapping is an assumption: it is written in the output and in `docs/model.md`.
- New tool `climate_scenarios(scenario)`:
  1. The optimal plan for each climate (yields of that climate).
  2. Each plan evaluated in every climate with its hectares fixed: the same method as `eval/plan_check.py` (E1). Move `evaluate_plan` into `dora/` so the tool and the evaluation share it.
  3. The matrix "plan for climate i, climate j happens → NPV", the expected NPV of each plan with the outlook's probabilities, the worst case of each one, and the regret ("planning for normal and getting dry loses X USD against having planned for dry").
  4. Source and date of the outlook and of the yields, and the placeholder flags.

## 4. One plan for all climates (two-stage stochastic engine)
`Scenario.climate_scenarios = [{"id": "dry", "probability": p, "yields": {...}}, ...]`. When given:
- **First stage, shared by all climates (decided today):** `x_{c,w}`, `z_{c,w,t}`, `rent_in`, `rent_out`, `buy`, livestock hectares, and forward sales.
- **Second stage, one copy per climate `s`:** sales `v^s`, storage `in^s`, `s^s`, `o^s`, cash `S^s`, debt `D^s`, with that climate's yields. Each climate has its own cash, stock, credit, storage and route rows.
- Objective: `max Σ_s prob_s · NPV_s`.
- Reports: the plan, the NPV in each climate, the expected NPV, the **value of the stochastic solution** (expected NPV of this plan minus that of the plan for the normal climate, evaluated in all climates), and the duals per climate. Per climate, `λ^s_p` is the value of a dollar in fortnight `p` weighted by `prob_s`. Divide by `prob_s` to report it per climate, and say so.
- With one scenario of probability 1, the result equals the deterministic engine exactly (test).

## 5. The agent
- `dora/modeling_guide.md`:
  - When the farmer plans the coarse season, or asks about sowing dates, call `climate_outlook` and say what it shows, with source and date. An outlook is a probability: never "it will rain" or "it will be dry". Say "the SMN gives 45 % probability of below-normal rainfall for November–January".
  - If the outlook leans one way, or the farmer asks "all at once or in stages?", evaluate it with `climate_scenarios` and the sowing windows.
  - The agent **may suggest without numbers** that something is worth looking at ("with this outlook it is worth looking at a staggered sowing"). Every number still comes from a tool, and the verifier checks it.
  - Placeholder windows and yields are said out loud.
- `dora/agent.py`: the system prompt mentions the new tools in one line. No other change.

## Acceptance tests (`tests/test_sowing_climate.py`, no network)
1. Without `sowing_windows` and `climate_scenarios`, the plan, NPV and every shadow price equal `main` in at least 6 scenarios (the 4 regions, scarce capital, storage options, payment options).
2. Two windows with the same calendar and yield split a crop's area arbitrarily, but give the same NPV as one window.
3. A late window with higher yield and later harvest is chosen when capital is plentiful. With scarce capital it can lose, because the money comes later. Both cases are checked against an NPV computed by hand.
4. Mass balance per crop with several harvest dates.
5. Machinery capacity: with a planter capacity below the area, the sowing is staggered. The dual of the capacity lies between the left and right derivatives (one more and one less hectare).
6. `climate_outlook` reads a stored snapshot from `tests/data/` and falls back to the cache, flagged, when the network fails.
7. `climate_scenarios`: the matrix diagonal equals the optimum of each climate. Every value is at most its column's diagonal (no plan beats the optimum of the climate that happens).
8. Stochastic engine: one scenario of probability 1 equals the deterministic engine. Its expected NPV is at least that of every per-climate plan evaluated in all climates. The duals of capital and land pass the perturbation test.
9. Agent with a scripted model: a question about sowing dates calls `climate_outlook`, and the answer passes the verifier.

## Evaluation
- Add to the E1 decision questions (`docs/plan-de-pruebas.md`): "¿Siembro el maíz todo junto o escalonado?", "El SMN da un trimestre seco, ¿cambio el plan?", "¿Me conviene soja de primera o de segunda?". Their expected answers come from `eval/build_answers.py`, never by hand.
- After the merge: review checks, new answers, new freeze tag, then E1.

## Live check
Balcarce, 500 ha, 100,000 USD, coarse season. With the outlook of the day: plan per climate, the matrix, the stochastic plan, and an answer from the agent that passes the verifier. Recorded with date and commit.
