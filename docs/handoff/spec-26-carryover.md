# Handoff Report: SPEC-26 Carryover Stock Valued at Next Season's Price

**Branch:** `spec-26-carryover` (created from `main` at `5718721`)  
**Status:** Completed and verified  
**Date:** 2026-10-30  

---

## 1. Summary of Changes

Implemented terminal valuation of grain carried past July ($T - 1 = 29$) into the next campaign, as specified in `docs/specs/SPEC-26-carryover-stock.md`:
1. **Scenario (`dora/scenario.py`):**
   - Added `carryover: dict | None = None` to `Scenario`.
   - Added `carryover_k(sell_month)`: computes month difference $k$ from season end ($T - 1 = 29$, July) to `sell_month`. Raises `ScenarioError` if $sell\_month \le season\_end\_month$.
   - Added `carryover_quote(c, sell_month)`: retrieves explicit quote from `sc.carryover["price_usd_t"][c]` (with source) or from `sc.price_curve[c][sell_month]`. Strictly prevents flat curve extrapolation via `_interpolate_monthly` or `monthly_price_rise`.
   - Added `net_price_quote(c, p, gross_p, r)`: computes farm-gate net price for fortnight $p$ using route $r$ (accounting for freight, taxes, and marketing).
   - Added `carryover_value(c, option_id)`: evaluates terminal value $V_{c,m}$ per crop and storage option, enforcing storage life constraints (`held_at_end + k <= max_months_m`).

2. **Optimization Engine (`dora/engine.py`):**
   - Added `carryover: dict = field(default_factory=dict)` to `Result` and surfaced it in `Result.summary()`.
   - Objective function: added carryover valuation term $- (1 + r_i)^{-(T-1)} \cdot V_{c,m} \cdot s_{c, T-1, m}$ for active $(c, m)$ pairs.
   - Bounds: stock bounds at $T - 1$ relax from `(0, 0)` to `(0, None)` for eligible $(c, m)$ pairs with valid quotes and within storage life limits.
   - Wealth & Income Tax: terminal wealth includes carried stock value ($\sum_{c,m} V_{c,m} s_{c,T-1,m}$). Carried stock is treated as unrealized inventory, so income tax applies only to realized profit ($\text{realized\_profit} = S_{T-1} - D_{T-1} + \text{end\_value}\cdot\text{buy} + \text{herd\_ev} - K_0$).
   - Physical shrink calculation in `storage_by_option`: updated to subtract end stock $s_{c, T-1, m}$ (`sh_c = in_val - out_val - s_end`), preventing carried grain from being falsely categorized as shrink.
   - Mass balance validation: updated to $\text{harvest} = \text{sales} + \text{forwards} + \text{shrink} + \text{carried stock}$.
   - Two-stage stochastic engine (`_optimize_stochastic`): added carryover support for consistency.

3. **Tools & Reporting (`dora/tools.py`):**
   - Registered `"carryover"` in `PARAMETERS` and excluded from `_ASSUMPTIONS`.
   - Validated `sell_month` (must be after season end) and positive prices in `_validate()`.
   - `_storage_report()`: added `can_carry_over`, `carryover_sell_month`, `carryover_sell_month_name`, and `carryover_note` in `window_by_crop[c]` when carryover applies. Without carryover, existing text and `last_month_name` remain 100% unchanged.
   - `evaluate_season()`: includes `out["carryover"]` with crop and option breakdowns, carried tonnes, $V_{c,m}$, quotes, sources, and non-carried reasons.

4. **Documentation & Evaluation:**
   - Updated `dora/modeling_guide.md` with carryover instructions for agent interactions.
   - Updated `docs/model.md` with objective equations, terminal valuation math, and income tax treatment.
   - Added `eval/questions_spec26.jsonl` (q43) and generated `eval/answers_spec26.jsonl` using `eval/build_answers.py`.

---

## 2. Equations and Exact Code Line References in `dora/engine.py`

| Concept | Mathematical Equation | Lines in `dora/engine.py` |
|---|---|---|
| Objective discount factor | $\text{discount} = (1 + r_i)^{-(T-1)}$ | Line 346 |
| Carryover objective terms | $\text{obj}[s_{c,T-1,m}] -= \text{discount} \cdot V_{c,m}$ | Lines 381–383 |
| Bounds relaxation | $\text{bounds}[s_{c,T-1,m}] = (0, \text{None})$ for active $(c,m)$ | Lines 831–834 |
| Carried inventory valuation | $\text{carried\_end\_val} = \sum_{c,m} V_{c,m} \cdot s_{c,T-1,m}$ | Lines 907–911 |
| Pre-tax wealth & realized profit | $W = S_{T-1} - D_{T-1} + \text{land} + \text{herd} + \text{carried}$; $\Pi_{\text{realized}} = W - \text{carried} - K_0$ | Lines 912–913 |
| Income tax on realized profit | $T_{\text{usd}} = t \cdot \Pi_{\text{realized}}$ (if $t > 0$ and $\Pi_{\text{realized}} > 0$) | Lines 914–917 |
| Shrink with carried stock | $\text{shrink}_{c,m} = \text{in} - \text{out} - s_{c,T-1,m}$ | Lines 1057–1059 |
| Mass balance equation | $\text{harvest}_c = \text{sales}_c + \text{forwards}_c + \text{shrink}_c + \text{carried}_c$ | Lines 1094–1099 |
| Carryover report generation | Constructs `carryover_res` with tonnes, $V_{c,m}$, quotes, and reasons | Lines 1166–1205 |

In `dora/scenario.py`:
- `Scenario.carryover_k`: Lines 959–971
- `Scenario.carryover_quote`: Lines 973–986
- `Scenario.net_price_quote`: Lines 988–1004
- `Scenario.carryover_value`: Lines 1006–1054 ($V_{c,m}$ computation matching Section 2 formula)

---

## 3. Findings and Technical Insights

1. **Storage Shrink Accounting:**
   In `engine.py`, shrink was previously computed simply as $\text{in} - \text{out}$. With carryover stock, grain remaining in the silo at $T - 1$ ($s_{c,T-1,m}$) would have been counted as shrink. Subtracting $s_{c,T-1,m}$ ensures exact physical mass conservation.

2. **Income Tax on Carried Stock:**
   Carried grain is valued at $V_{c,m}$ and adds to final wealth, but is unrealized inventory during the current campaign. Applying income tax solely to realized operational cash profit ensures shadow prices and tax wedges represent actual current-year tax liabilities without taxing unrealized stock.

3. **Multi-fortnight Storage Capacity Duals:**
   Storage capacity in the engine is enforced across all fortnights $p \in [0, T-1]$. A seasonal perturbation of $\text{storage\_capacity\_t}$ perturbs capacity across all fortnights. When capacity binds at $T - 1$, the dual $\mu_{\text{storage}}[29]$ was verified via both single-fortnight binding setups and isolated finite-difference testing, confirming agreement with HiGHS duals to $10^{-10}$.

---

## 4. Test Results

- **New Carryover Tests (`tests/test_carryover.py`):** 8 passed in 0.94s:
  - `test_1_zero_drift_without_carryover`: 6 distinct scenarios equal baseline without carryover.
  - `test_2_carryover_decision_high_vs_low_quote`: high quotes carry grain to $T-1$; low quotes sell inside season.
  - `test_3_carryover_value_matches_formula`: $V_{c,m}$ matches Section 2 formula to $< 10^{-9}$.
  - `test_4_storage_life_and_capacity_limits`: silo bag carries nothing when storage life is exceeded; own silo respects capacity.
  - `test_5_crop_without_quote_carries_nothing`: unquoted crops carry nothing and are reported in `not_carried`.
  - `test_6_curve_not_extrapolated_past_last_month`: curves ending before `sell_month` do not extrapolate.
  - `test_7_mass_balance_with_carried_stock`: mass balance verified across all crops.
  - `test_8_storage_capacity_dual_perturbation_test`: capacity dual at $T-1$ matches finite difference perturbations.
- **Full Test Suite (`pytest`):** 279 passed, 1 skipped (offline check) in 37.03s. Zero regressions across all prior test modules.
- **Evaluation Questions:**
  - `eval/questions_spec20.jsonl` q39 keeps expected value `"julio"`.
  - `eval/questions_spec26.jsonl` (q43) added and verified with `eval/answers_spec26.jsonl` via `build_answers.py`.
