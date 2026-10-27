# SPEC-02: Farmer constraints and their opportunity cost

**Status:** to implement after SPEC-01. **Branch:** `spec-02-user-constraints`. Do not merge into `main`; it gets reviewed first.

## Why
Farmers face decisions imposed from outside the optimum: "at least 200 ha of soybean", "no more than 150 ha of corn", "wheat at least 30% of the land", "I already sold 300 t of soybean for May at 320 USD/t". Each such constraint has a **shadow price**: what the farmer gives up to meet it (its opportunity cost). It is zero if the constraint is not binding. DORA should report it, in USD of today, per unit of the constraint.

## Constraint types
A new scenario field `constraints: list[dict]`, each item one of:

| `type` | Fields | Math |
|---|---|---|
| `min_area` | `crop`, `ha` | x_c ≥ ha |
| `max_area` | `crop`, `ha` | x_c ≤ ha |
| `min_share` | `crop`, `share` | x_c ≥ share · Σ_k x_k |
| `forward_sale` | `crop`, `month` ("YYYY-MM"), `tonnes`, `price_usd_t` | fixed delivery of `tonnes` in the first fortnight of `month` at `price_usd_t` |

Each item may carry an optional `label` (free text, e.g. "contract with the cooperative") that is echoed back.

## Engine changes (`dora/engine.py`)
- **Area constraints** are new **rows** in `A_ub`, not bounds, so their duals come out directly:
  - `min_area`: −x_c ≤ −ha.
  - `max_area`: x_c ≤ ha.
  - `min_share`: share·Σ_k x_k − x_c ≤ 0.
- **Forward sale:** a new variable `f_k ≥ 0` per commitment, at fortnight `p_k`:
  - Cash row `p_k`: add `−price_usd_t` (net of marketing per tonne) for `f_k`. Same sign convention as `sell`: income enters with a negative coefficient.
  - Stock row of the crop at `p_k`: add `+1` for `f_k` (it leaves the stock, like `sell`).
  - A new **equality** row: `f_k = tonnes`.
  - If `p_k` is before the crop's harvest fortnight, raise `ScenarioError` with a clear message.
- **`Result`** gains `constraint_duals: list[float]`, one per item, as **opportunity cost per unit**: how much the NPV increases if the constraint is loosened by one unit.
  - For `min_area`, `max_area`, `min_share`: the value of relaxing the row, with the same sign handling as the land row. Units: USD per ha, or USD per share point (1% of the land) for `min_share`.
  - For `forward_sale`: minus the dual of `f_k = tonnes`, so that a positive number means delivering one tonne less would raise the NPV. Units: USD per tonne.
- If the constraints make the program infeasible (for example, `min_area` adding up to more than `area_ha`), raise `ScenarioError` naming the constraints involved, not a raw solver message.
- Update `docs/model.md` with the new rows and their line numbers.

## Tools
- `PARAMETERS["constraints"]`: validated list. It has unknown types, unknown crops, negative numbers, shares outside (0, 1], badly formed months or prices ≤ 0 → error.
- `build_scenario`: echoes each constraint with origin `"farmer"`.
- `evaluate_season`: a new section `"constraints"`, one item per constraint, with: `type`, `label`, `binding` (bool, |dual| > 1e-6), `opportunity_cost` (number), `unit` and `meaning`. For example: "meeting this costs X USD of today per hectare; loosening it by one hectare would raise the present value by that amount".
- `schemas.py`: the `constraints` array with `oneOf` the four item shapes.

## Acceptance tests (`tests/test_constraints.py`)
Every opportunity cost is checked against perturbation, using the same between-derivatives check as `tests/test_engine.py`.
1. **Binding `min_area`:** with plenty of capital, `min_area` of corn = 150 ha (corn is not chosen without it). The opportunity cost is > 0 and lies between the one-sided derivatives when `ha` moves ±1.
2. **Non-binding `min_area`:** `min_area` soybean = 50 ha when the optimum already sows 250 ha → `binding` false, cost 0.
3. **`max_area`** on soybean below its optimum → binding, cost > 0, perturbation check.
4. **`min_share`** wheat 0.4 → perturbation check moving `share` by ±0.01.
5. **`forward_sale`** of soybean in May of year 2 at a price below the market net price → cost > 0, perturbation on `tonnes` ±1. At a price well above it, the cost is negative: the contract is worth more than the market.
6. **Infeasible:** `min_area` corn 300 + `min_area` soybean 300 on 500 ha → `ScenarioError` naming both.
7. **Without constraints**, results are identical to the current engine (NPV rel 1e-12).
8. **All existing tests still pass.**

## Rules
Same as SPEC-01:
- English code in the existing style.
- No new dependencies and no network.
- Keep the signs of the existing equations.
- Small commits on the branch, not on `main`.
