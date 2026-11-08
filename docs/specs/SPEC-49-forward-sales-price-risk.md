# SPEC-49: forward sales as a decision, with price risk (hedge or sell at harvest)

**Status:** draft (8/11), asked for by Guillermo after reading the Pergamino sheet: "vende todo contado, no hace operaciones a término; no hay un análisis de eso".
- **Branch:** implement on `spec-49-price-risk`, created from `spec-45-spreadsheet-v2` (phase A approved at `fc6a4b2`), in `D:\projects\dora-main`.
- **Commits:** messages start `SPEC-49 implementation:`. Write the handoff; Claude reviews. Do not merge, do not push, do not redeploy.
- **Cost:** zero. No LLM is called; everything runs offline (`DORA_OFFLINE=1`).

**Touch only:**
- `dora/engine.py`: a new function `_optimize_price_risk`, plus the dispatch in `optimize`;
- `dora/scenario.py`: new fields;
- `dora/tools.py`: a new tool `hedge_analysis`;
- `mcp_server/server.py`: expose the tool;
- a new data file `dora/data/price_risk_<region>.json` for the 4 regions;
- a new `tests/test_spec49.py`;
- the handoff.

Do not change the deterministic model in `optimize` (the path without `price_risk`), nor `_optimize_stochastic` (SPEC-25), except to share helpers without changing results.

## Why
- **Today a forward sale is an input, never a decision.** The engine takes `constraints: [{"type": "forward_sale", crop, month, tonnes, price_usd_t}]` because the farmer already made the decision. It never chooses whether to sell forward, so the plan always sells at harvest or stores.
- **This is not a bug of the solver; it is how the model is built.** The price of each future fortnight comes from the futures curve plus basis. For a risk-neutral model, a forward at that price and a sale at harvest are worth the same in expectation, so it has no reason to hedge.
- **What a forward actually does:**
  - **it lowers risk:** a bad price at harvest no longer ruins the cash;
  - **it costs** when the forward price sits below the expected spot price (a premium), or when the crop fails and the farmer is short.

  To analyse "¿vendo a término o a cosecha, y cuánto?" the model needs price scenarios, a risk measure, and the forward quantity as a first-stage decision. This is the analysis an agronomist or an economist expects, and neither DORA nor Gemini in Sheets does it today (`docs/investigacion/2026-11-08-gemini-sheets-vs-dora.md`).

## 1. Scenario fields (`dora/scenario.py`)
```python
price_risk: dict | None = None
# {
#   "n_scenarios": 9,                 # equiprobable price scenarios, 5..15
#   "vol_annual": {"soybean": 0.20},  # optional overrides; else from the data file
#   "risk_weight": 0.0,               # beta in [0, 1]; 0 = risk neutral (today's behaviour)
#   "cvar_alpha": 0.10,               # the worst 10 % of outcomes
#   "forward_offers": [               # what the buyer offers today; default built from the curve
#     {"crop": "soybean", "month": "2027-05", "price_usd_t": 330, "max_tonnes": null}
#   ],
#   "max_hedge_share": 0.6,           # forward tonnes <= share of expected production, per crop
#   "with_climate": false             # combine with climate_scenarios (section 4)
# }
```
- **Default:** `price_risk is None`, and `optimize` behaves exactly as today. Test 1 checks it.
- **Validation in `dora/tools.py`, same style as the other fields:**
  - `n_scenarios` from 5 to 15;
  - `risk_weight` from 0 to 1;
  - `cvar_alpha` from 0.01 to 0.5;
  - each offer's month must be in the campaign, and its crop must be in the scenario;
  - `max_hedge_share` from 0 to 1.

## 2. Price scenarios (deterministic, no random numbers)
- **Starting point:** for each crop, the price the engine already uses at harvest (futures curve plus basis, i.e. `net_price_route` before costs) is the median. Price scenarios are **equiprobable lognormal quantiles**: `P_s = P_med * exp(sigma * sqrt(tau) * z_s)`.
  - `z_s` are the midpoint quantiles of a standard normal, `z_s = Phi^-1((s - 0.5) / S)`;
  - `tau` is the years from today to the sale fortnight;
  - `sigma` is the annual volatility.

  Then **re-centre each crop so that the mean of `P_s` equals `P_med`** (so a risk-neutral model sees the same expected price as today).
- **Crops move together.** Use the same `z_s` for every crop in one scenario: soy, corn and wheat prices are strongly correlated on CBOT. Write the assumption in the handoff and in the tool's output. A correlation matrix is out of scope.
- **Prices in later fortnights** of the same scenario move by the same factor as the harvest price. Storage then cannot "see the future" scenario by scenario beyond what the curve already says. This is the non-anticipativity of the second stage: decisions taken before the price is known must be the same in all scenarios. See section 3.
- **Volatility data:** `dora/data/price_risk_<region>.json`, with `vol_annual` per crop, `source` and `as_of`. Use the historical volatility of the CBOT front contract over the last 5 years. If you cannot compute it offline from data in the repo, put placeholder values (soybean 0.20, corn 0.22, wheat 0.25, sunflower 0.22) with `"placeholder": true`. The tool's output must then say "volatilidad supuesta, no medida".

## 3. The model (`_optimize_price_risk`)
Two stages, built like `_optimize_stochastic` (SPEC-25).

- **First stage, the same in every scenario:**
  - hectares per crop and window, land tenure, supplier terms (as today);
  - **forward tonnes `h[c, o]` for each offer `o`.** Price fixed at the offer price, net of the same costs as a spot sale through that route. Delivered in the offer's month and paid on delivery.
- **Second stage, one copy per price scenario `s`:**
  - spot sales, storage, cash `S_s[p]` and debt `D_s[p]` with the scenario's prices;
  - **non-anticipativity:** every decision in a fortnight before the first sale fortnight of the campaign (sowing, early costs, early credit) is equal across scenarios. Prices are only known from harvest on.
  - Implement this with explicit equality rows, or by building those variables once. Say which in the handoff.
- **Delivery:** for each offer, own production (and storage) delivered in its month + `buy_back_s[c, p]` = `h[c, o]`.
  - `buy_back` is grain bought at the scenario's spot price plus a cost (5 USD/t default, `buyback_cost_usd_t`);
  - over-hedging becomes costly when yields fail (section 4) or when spot rises.
- **Hedge limit:** `sum_o h[c, o] <= max_hedge_share * expected production of c` (expected yield × hectares, linear in the hectare variables).
- **Objective (mean-CVaR, linear form of Rockafellar–Uryasev):**
  - maximise `(1 - beta) * sum_s pi_s * NPV_s + beta * CVaR_alpha`;
  - with `CVaR_alpha = eta - (1 / alpha) * sum_s pi_s * u_s`, `u_s >= eta - NPV_s`, `u_s >= 0`, `eta` free.

  With `beta = 0` it is the expected NPV.
- **Every scenario keeps its own cash constraints**, so the plan is feasible in every price scenario, not only on average.
- **Size:** about 9 × the second-stage variables of today (of the order of 1,500 variables). HiGHS solves it in well under a second; measure it and report it.

## 4. With climate (`with_climate: true`)
If `climate_scenarios` is also given, the scenarios are the grid price × climate, with probability `pi_price * pi_climate` and at most 45 scenarios (refuse above that). Yields then fail in some scenarios while the forward is fixed. This is exactly where over-hedging shows up. Price and yield are independent in this version, and the handoff says so: an Argentine drought barely moves CBOT, but a US drought does.

## 5. Tool `hedge_analysis(scenario, risk_weights=[0, 0.25, 0.5, 0.75, 1.0], lang)`
It solves once per `risk_weight` and returns:
- **`frontier`:** for each `beta`:
  - expected NPV;
  - CVaR at `alpha`;
  - the worst scenario's NPV;
  - the best scenario's NPV;
  - forward tonnes and hedge ratio (forward tonnes / expected production) per crop;
  - hectares per crop;
  - minimum cash over scenarios and fortnights.
- **`price_scenarios`:** `P_s` per crop at harvest, with `sigma`, `tau`, the source and the placeholder flag.
- **Duals:**
  - `forward_offer_value_usd_t` per offer: the dual of the offer's `max_tonnes`, or the reduced cost of `h`, meaning how much a better offer would be worth;
  - `hedge_limit_shadow_price` per crop.
- **`indifference_price_usd_t` per offer at `beta = 0`:** the forward price at which the risk-neutral plan starts to sell forward. Compute it by a short bisection on the offer price (at most 20 solves), and report how many solves it took.
- **`explanation`:** a short text in the user's language. It is built only from numbers in the output, like the other tools' texts. Example:

  > "Sin aversión al riesgo, vender a término no suma: el precio ofrecido (330) es igual al esperado. Cubriendo el 40 % de la soja, el peor 10 % de los años pasa de −120.000 a −35.000 USD y el resultado esperado baja 6.000 USD."

  Never "conviene cubrirse" without the numbers. Never a recommendation of a broker, market or product.

The agent's guidance (`docs/modelling-guide` or the system prompt section that lists tools): when the farmer asks about selling forward, hedging, "¿vendo ahora o espero?", or a price fall, call `hedge_analysis`. Show the frontier as a small table, and let the farmer choose the risk level. Do not choose `beta` for the farmer.

## 6. Tests (`tests/test_spec49.py`, offline)
1. **No `price_risk`:** plan, NPV and every shadow price equal `optimize` today on the 6 example scenarios of SPEC-45 (± 1e-6).
2. **One scenario, zero volatility:** `n_scenarios = 5` with `vol = 0` gives the deterministic plan and NPV (± 0.01 USD), and forward tonnes are 0 or the NPV is indifferent to them.
3. **Mean is preserved:** for each crop, the mean of `P_s` equals the deterministic harvest price (± 1e-6).
4. **Risk neutral, fair offer:** with `beta = 0` and the offer equal to the expected price, expected NPV ≥ deterministic NPV − 0.01. The second stage can only adapt, never lose.
5. **Monotone frontier:** as `beta` goes 0 → 1, expected NPV does not increase, CVaR does not decrease, and the hedge ratio does not decrease (± 1e-6). Use pampas_core 2,000 ha and se_ba 500 ha.
6. **Premium:** an offer 5 % above the expected price takes the hedge to `max_hedge_share` even with `beta = 0`; an offer 5 % below gives 0 forward with `beta = 0`.
7. **Independent check of each scenario:**
   - fix the first stage (hectares and forward tonnes) of the solution;
   - re-solve each scenario alone with the deterministic engine, with that scenario's prices, the hectares fixed with `min_area = max_area`, and the forward as a `forward_sale` constraint;
   - compare `NPV_s` (± 0.01 USD) and compute CVaR from those `NPV_s` by sorting, independently of the LP (± 0.01).

   This is the "verify without knowing the answer" check: the stochastic LP is checked against the trusted deterministic path.
8. **Over-hedging with climate:** with `with_climate` and a dry scenario at 50 % yield, the hedge ratio at `beta = 1` stays below the dry-scenario production / expected production; `buy_back` is positive only in the dry scenarios.
9. **Validation:** bad `risk_weight`, an offer for a crop not in the scenario, `n_scenarios = 50`, or more than 45 grid scenarios give errors in the validation style, not a crash.
10. **Hygiene:** `git status --porcelain dora/data observatory` is empty after the tests, with no manual restore.

Run `tests/test_spec49.py` and the full suite after each commit (0 failed), and paste the real output in the handoff.

## 7. Live check (for the handoff; Guillermo runs it, no cost on our side)
In the app: "Tengo 500 ha propias en Pergamino y 260.000 dólares. ¿Me conviene vender parte de la soja a término? Me ofrecen 330 a mayo." The reply must:
- call `hedge_analysis`;
- show the frontier;
- say whether the volatility is measured or assumed;
- never invent a percentage it did not compute.

## Out of scope (write them as follow-ups in the handoff)
- futures with margin calls, and options (puts, collars);
- correlations between crops other than 1, and price–yield correlation;
- the spreadsheet version (a "Riesgo de precio" sheet in the SPEC-45 workbook), after this is reviewed.

## What we learn
- **Whether DORA can answer the question every farmer asks at sowing ("¿vendo ahora?") with numbers that can be checked.** Test 7 shows each scenario comes from the same trusted engine.
- **Where the value of a forward really comes from:** a premium over the expected price, or less risk. The frontier and the indifference price separate the two, which is what an economist expects to see.
