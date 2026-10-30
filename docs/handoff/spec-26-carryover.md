# Handoff Report: SPEC-26 Carryover Stock Valued at Next Season's Price

**Branch:** `spec-26-carryover` (created from `main` at commit `5718721`)  
**Status:** Completed, review amendments implemented, and fully verified  
**Date:** 2026-10-30  

---

## 1. Summary of Implementation & Review Amendments (30/10)

Implemented terminal valuation of grain carried past July ($T - 1 = 29$) into the next campaign, as specified in `docs/specs/SPEC-26-carryover-stock.md`, and incorporated all 6 points from the "Review amendments (30/10)":

1. **Income Tax on Carried Stock Valuation (Review Amendment 1):**
   - Removed `realized_profit`. Carried grain is valued at terminal option value $V_{c,m}$ and adds directly to pre-tax taxable profit $\Pi = \text{pre\_tax\_wealth} - K_0$, matching the treatment of purchased land end value and terminal livestock herd value.
   - Eliminates using carryover as an artificial tax shelter.
   - Formulas:
     $$T = t \cdot \Pi \quad \text{if } \Pi > 0 \text{ (with } t = \text{income\_tax\_rate}), \quad \text{NPV} = \text{NPV}_{\text{LP}} - \text{discount} \cdot T$$
     $$\text{tax\_mult} = (1 - t) \quad \text{if } \Pi > 0 \text{ and } t > 0, \quad 1 \text{ otherwise}$$
   - Updated `docs/model.md` explicitly stating this economic model assumption: closing grain inventory is valued at market and subject to income tax as part of the season's economic result.

2. **Local Port / Elevator Quote at `price_point` (Review Amendment 2):**
   - Quote in `carryover.price_usd_t` is defined at `price_point` (local port or country elevator post-retenciones, FAS/pizarra), not Chicago (CBOT).
   - Updated the example in `docs/specs/SPEC-26-carryover-stock.md` (line 19) to `"oferta acopio Quequén, dic-2027"`.
   - Updated `dora/modeling_guide.md` explaining that carryover quotes represent local terminal bids, not CBOT futures.
   - When quote is sourced from `price_curve` (not direct producer quote), `carryover_basis` applies basis ONLY if it is scalar or explicitly covers `sell_month`. If the basis series ends before `sell_month`, basis extrapolation is rejected and the crop is not carried (`reason: "no_basis"`).
   - Updated `eval/questions_spec26.jsonl` (q43) to a local Quequén elevator bid with source `"oferta acopio Quequén (test question q43)"`.

3. **Clean Validation of `sell_month` (Review Amendment 3):**
   - `_validate()` in `dora/tools.py` checks that `sell_month` is strictly formatted as `YYYY-MM` (4-digit year, 2-digit month 01–12) and occurs strictly after season end ($T - 1$, July). Returns clean user-facing error messages instead of unhandled exceptions.
   - `Scenario.carryover_k()` in `dora/scenario.py` validates the `YYYY-MM` format and month range ($1 \le \text{month} \le 12$), raising `ScenarioError` (never `ValueError`).

4. **Stochastic Engine & Climate Scenarios (Review Amendment 4):**
   - In `_optimize_stochastic()` (`dora/engine.py`):
     - Verified per-climate mass balance: $\text{harvest}_s = \text{sales}_s + \text{forwards}_s + \text{shrink}_s + \text{carried}_s$ across all crops.
     - Fixed `shrink_entry` to `float(opt.get("shrink_at_entry", 0.0))`.
     - Computed probability-weighted expected carryover: `tonnes_carried_total` and expected terminal valuation `carried_end_value_usd`.
     - Added `tonnes_by_climate` dict detailing total carried stock per climate scenario.
     - Surfaced `carryover` in `r.carryover` and `evaluate_season()`.

5. **Fixed Benchmarks for Test 1 Zero Drift (Review Amendment 5):**
   - `test_1_zero_drift_without_carryover` in `tests/test_carryover.py` hardcodes the exact values from `main` commit `5718721` across all 6 reference scenarios (NPV, final wealth, crop hectares, and shadow prices for capital, land, and credit).

6. **SPEC-25 LaTeX Tab Character Fix (Review Amendment 6):**
   - Replaced literal tab characters `\t` + `ext` and `\t` + `ilde` in `docs/model.md` SPEC-25 section with `\text` and `\tilde`.

---

## 2. Benchmark Reference Values from `main` (commit `5718721`)

The 6 reference scenarios produce the following exact results in `main` (`5718721`), now hardcoded as regression baselines:

1. **Scenario 1 (Default Base):**
   - NPV: $88,186.596781$ USD | Final Wealth: $92,466.524581$ USD
   - Hectares: Wheat $121.722765$ ha, Soybean $250.000000$ ha, Corn $0.0$, Sunflower $0.0$
   - Duals: Capital $0.160813$, Land $37.734801$ USD/ha, Credit f14 $0.112785$

2. **Scenario 2 (Rented Land, $150$ USD/ha):**
   - NPV: $66,148.695574$ USD | Final Wealth: $69,359.065986$ USD
   - Hectares: Wheat $23.910527$ ha, Soybean $153.086981$ ha, Sunflower $129.176453$ ha
   - Duals: Capital $0.142883$, Land $171.432437$ USD/ha, Credit f14 $0.060086$, f18 $0.029959$

3. **Scenario 3 (Storage Options - Own Silo & Silo Bag):**
   - NPV: $88,186.596781$ USD | Final Wealth: $92,466.524581$ USD
   - Hectares: Wheat $121.722765$ ha, Soybean $250.000000$ ha
   - Duals: Capital $0.160813$, Land $37.734801$ USD/ha, Credit f14 $0.112785$

4. **Scenario 4 (Forward Sale 200 t Soybean at $310$ USD/t):**
   - NPV: $84,645.792747$ USD | Final Wealth: $88,753.876001$ USD
   - Hectares: Wheat $121.722765$ ha, Soybean $250.000000$ ha
   - Duals: Capital $0.160813$, Land $37.734801$ USD/ha, Credit f14 $0.112785$

5. **Scenario 5 (Land Buy, 35% Income Tax, 1% Gross Receipts Tax):**
   - NPV: $69,697.676579$ USD | Final Wealth: $73,080.288387$ USD
   - Hectares: Wheat $152.982581$ ha, Soybean $200.000000$ ha
   - Duals: Capital $0.095376$, Land $24.041110$ USD/ha, Credit f14 $0.061225$

6. **Scenario 6 (Sowing Windows & Machinery Capacity):**
   - NPV: $105,500.092511$ USD | Final Wealth: $110,620.289857$ USD
   - Hectares: Wheat $32.688471$ ha, Corn $150.000000$ ha, Soybean $91.211359$ ha
   - Duals: Capital $0.327999$, Land $0.000000$ USD/ha, Credit f14 $0.140265$, f20 $0.148535$

---

## 3. Test Suite Verification

- **Carryover Test Suite (`tests/test_carryover.py`):** 12 tests, 100% passing:
  - `test_1_zero_drift_without_carryover`: verified against hardcoded `5718721` main numbers.
  - `test_2_carryover_decision_high_vs_low_quote`: high quotes carry grain to $T-1$; low quotes sell inside season.
  - `test_3_carryover_value_matches_formula`: $V_{c,m}$ matches Section 2 formula to $< 10^{-9}$.
  - `test_4_storage_life_and_capacity_limits`: silo bag carries nothing when storage life is exceeded; own silo respects capacity.
  - `test_5_crop_without_quote_carries_nothing`: unquoted crops carry nothing and are reported in `not_carried`.
  - `test_6_curve_not_extrapolated_past_last_month`: curves ending before `sell_month` do not extrapolate.
  - `test_7_mass_balance_with_carried_stock`: mass balance verified across all crops.
  - `test_8_storage_capacity_dual_perturbation_test`: capacity dual at $T-1$ matches finite difference perturbations.
  - `test_9_income_tax_applies_to_carried_grain`: income tax taxes carried grain valuation, strictly lowering NPV and taxing entire wealth gain.
  - `test_10_curve_quote_without_basis_not_carried`: curves without explicit basis series reaching `sell_month` result in `reason: "no_basis"` and 0 carried.
  - `test_11_malformed_sell_month_validation`: malformed `sell_month` returns clean `ScenarioError` / error payload.
  - `test_12_stochastic_engine_carryover_and_mass_balance`: two-stage stochastic engine validates per-climate mass balance and surfaces `tonnes_by_climate` in `r.carryover`.

- **Full Suite (`.venv\Scripts\python -m pytest`):**
  - **283 passed, 1 skipped** (offline test for live feeds) in 53.42s.
  - Zero test regressions across entire repository.
