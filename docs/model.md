# The engine, equation by equation

Each equation is stated in math, then pointed to the line of `dora/engine.py` that writes it, with its sign. The solver (`scipy.optimize.linprog`, HiGHS) **minimizes** and takes every constraint as `A x = b` or `A x ≤ b`, so equations are written with all variables on the left.

## Indices and data
- `p = 0 … T−1`: fortnights, `T = 30`. Fortnight 0 is the first half of the season's first month (May in Argentina and Mato Grosso, April in Iowa).
- `c`: crop. `a`: livestock activity. `r`: route to the buyer. `k`: forward sale. `m`: way to store grain (`own_silo`, `silo_bag`, `elevator`, SPEC-20).
- `h_c`: harvest fortnight of crop `c` (`REGIONS[...]["calendar"]` in `scenario.py`).
- `e_{c,p}`: USD per hectare paid in fortnight `p` (`Scenario.payments_per_ha`): field operations and seed at sowing, fertilizer and crop protection on their dates, overhead spread until harvest. Rent is **not** in it (it is paid by `rent_in`).
- `y_c`: yield, t/ha. `π_{c,p,r}`: net price, USD/t, for a sale in `p` by route `r` (below).
- Storage option `m`: capacity `Cap_m` (`null` = no limit), entry cost `fill_m` (USD/t put in at `h_c`), holding cost `monthly_m` (USD/t/month, paid at `monthly_m / 2` per fortnight on ending stock), entry shrink `shrink_entry_m`, monthly shrink `shrink_monthly_m` (fortnightly shrink `δ_m = 1 − (1 − shrink_monthly_m)^{1/2}`), and maximum life `max_months_m` (`null` = no limit). When `storage_options` is empty (off by default), the engine builds a single legacy `own_silo` option with `Cap_m = storage_capacity_t`, `fill_m = 0`, `monthly_m = storage_cost_usd_t_month`, zero shrink and `max_months_m = null`.
- `r_i`, `r_c`: fortnightly rates on cash surplus and on credit.
- `K`: own capital. `L`: credit line. `H_own`: owned land. `R`: regional rent, USD/ha. `P_land`: land price, USD/ha.
- `τ`: tax per cash movement (Argentina's transaction tax); `g`: gross receipts tax rate.

| Coefficient | Default source |
|---|---|
| `y_c`, costs, price at harvest, marketing and harvest costs | MAGyP "Márgenes y Resultados", June 2026 (Argentina); ISU A1-20 2026 (Iowa); IMEA (Mato Grosso, provisional) |
| Payment and harvest calendar | Assumption (`REGIONS[...]["calendar"]`) |
| Monthly price rise after harvest, legacy storage cost, rates | Assumptions (`Scenario` defaults) |
| Ways to store (`storage_options`, off by default) | `storage_<region>.json` (FACMA / INTA / Reglas y Usos in Argentina; ISU A2-33 in Iowa; CONAB in Mato Grosso; unobserved items marked `placeholder: true`) |
| Price curve and monthly basis | CBOT futures plus each region's `basis` or `basis_by_month` (ISU A2-41/A2-42 in Iowa), or MAGyP's port quotes (`feeds.py`) |
| `R`, `P_land` | `land_<region>.json` |
| Routes and freight | `routes_<region>.json` (provisional); without routes, one truck leg (below) |

### Net price (SPEC-17 & SPEC-20: every cost counted once, monthly basis)
Each data source declares its **price point**, the place where its price is quoted:
- `"port"` (MAGyP: Bolsa de Cereales quotes at Rosario or Bahía Blanca). The source's marketing and harvest cost includes the freight `F` to that port, so `F` is taken out of marketing and carried by the route.
- `"local_elevator"` (Iowa and Mato Grosso: CBOT plus local basis). The basis already discounts the trip onward, so the reference route adds its inland legs back.

  gross_{c,p} = curve price_{c,p} + basis_{c,p}, or the source's price × (1 + monthly rise)^{months after harvest}
  destination_{c,p} = gross_{c,p} + [inland legs of route 1 if the price is local] + port and ocean legs of route 1
  farm-gate_{c,p,r} = destination_{c,p} − all legs of r − g·gross − τ·gross
  π_{c,p,r} = farm-gate_{c,p,r} − (marketing_c / y_c − F·[price point = port])

Here `basis_{c,p}` (`Scenario.basis_at` in `dora/scenario.py`, lines 473–487) is either a flat scalar in USD/t or a monthly dictionary `{"YYYY-MM": USD/t}` (from `basis_usd_t[c]` or `basis_by_month[c]` in `basis_<region>.json`), linearly interpolated across fortnights and flat before the first month and after the last (`_interpolate_monthly`, lines 177–201), identically to `curve_price`. Without routes, route 1 is one truck leg of `F` (the farmer's `freight_usd_t` when given).

## Variables
- `x_c ≥ 0`: hectares of crop `c`. `y_a`, `y_{low,a} ≥ 0`: hectares of livestock on shared land and on cattle-only land.
- `rent_in`, `rent_out`, `buy ≥ 0`: hectares rented in, rented out and bought.
- `v_{c,p,r} ≥ 0`: tonnes of crop `c` sold in fortnight `p` (`p ≥ h_c`) via route `r`.
- `in_{c,m} ≥ 0`: tonnes of crop `c` put into storage option `m` in its harvest fortnight `h_c` (line 231).
- `s_{c,p,m} ≥ 0`: tonnes of crop `c` in storage option `m` at the end of fortnight `p`, for `p ≥ h_c` (line 235).
- `o_{c,p,m} ≥ 0`: tonnes of crop `c` taken out of storage option `m` in fortnight `p`, for `p > h_c` (line 237).
- `S_p ≥ 0`: cash surplus at the end of `p`. `D_p ≥ 0`: credit used at the end of `p`.
- `f_k ≥ 0`: tonnes delivered under forward sale `k` in fortnight `p_k`.
- `z_{c,t} ≥ 0` (only with `payment_options`, SPEC-19): hectares of crop `c` whose seed, fertilizer and crop protection are paid under supplier term `t` (the base term or an option); `Σ_t z_{c,t} = x_c`.

## Objective
Maximize the present value of final wealth, plus what the bought land and the herd are worth at the end:

  max (S_{T−1} − D_{T−1})·(1+r_i)^{−(T−1)} + buy·P_land·(1 + appreciation)^{T/24}·(1+r_i)^{−(T−1)} + Σ_a herd end value·y_a·(1+r_i)^{−(T−1)}

Line 254 sets the discount factor; lines 256–270 the coefficients, **with the sign flipped** because the solver minimizes. Income tax is applied after solving (lines 711–717): it scales the result and every reported shadow price by `tax_mult = 1 − t` when profit is positive (line 731) without changing the plan. Season returns `return_on_capital` and `return_on_capital_and_land` span `T − 1 = 29` fortnights (`season_months = 14.5`) and are annualized as `(1 + r)^{24/29} − 1` (lines 719–728). In `compare_regions` (`dora/tools.py`), each region's `gross_receipts_rate`, `transaction_tax_rate` and `land_tax_usd_ha_year` enter the LP from `taxes_<country>.json` (unless overridden by the farmer), while corporate `income_tax_rate` stays out of the LP and is reported alongside (`npv_after_income_tax_usd`).

## Cash, every fortnight (equality)

  S_p − D_p = (1+r_i)·S_{p−1} − (1+r_c)·D_{p−1}
             + Σ_{c,r} π_{c,p,r}·v_{c,p,r} + Σ_k π_k·f_k·[p = p_k]
             − Σ_c e_{c,p}·x_c − Σ_{c,m} fill_m·in_{c,m}·[p = h_c] − Σ_{c,m} (monthly_m / 2)·s_{c,p,m}
             − [p = 0]·( R·(1+τ)·rent_in − R·(1−τ)·rent_out + (P_land·(1+τ) + land tax)·buy )
             − livestock payments and herd purchase + livestock sales
             + [p = 0]·(K − land tax·H_own)

Everything moved to the left, as in the code:

| Term | Coefficient | Line |
|---|---|---|
| `S_p`, `D_p` | +1, −1 | 293 |
| `S_{p−1}`, `D_{p−1}` | −(1+r_i), +(1+r_c) | 295 |
| `x_c` (costs leave cash; `e_{c,p}` already includes `τ`) | +e_{c,p} | 297 (`add_payments`, 283–287) |
| `x_c`, `z_{c,t}` with `payment_options`: fixed payments (operations, overhead) on `x_c`, each term's input payments (delayed, with surcharge, in installments) on `z_{c,t}` | +e^{fixed}_{c,p}, +e^{t}_{c,p} | 283–287 |
| `in_{c,m}` at `p = h_c` (storage entry/fill cost leaves cash; does not pay `τ`) | +fill_m | 299–303 |
| `s_{c,p,m}` for `p ≥ h_c` (fortnightly storage holding cost leaves cash; does not pay `τ`) | +monthly_m / 2 | 304–306 |
| `v_{c,p,r}` (sales bring cash) | −π_{c,p,r} | 307–309 |
| `f_k` (forward sale brings cash in `p_k`): contract price − marketing without `F` − freight of route 1 if the price point is the port − taxes | −π_k | 311–322 |
| `rent_in` (rent paid up front in `p = 0`) | +R·(1+τ) | 326 |
| `rent_out` (rent received in `p = 0`) | −R·(1−τ) | 328 |
| `buy` (price plus the year's land tax in `p = 0`) | +P_land·(1+τ) + land tax | 330 |
| `y_a`, `y_{low,a}` (livestock payments in `p`) | +payments_{a,p} | 335–339 |
| `y_a`, `y_{low,a}` (herd purchase in `p = 0`) | +herd price·(1+τ) | 341–347 |
| `y_a`, `y_{low,a}` (livestock sale) | −net income_a | 349–353 |
| right-hand side | K − land tax·H_own in `p = 0`, else 0 | 357–360 |

Rent is paid in full in fortnight 0, as is usual in Argentina. Iowa's cash rent is often paid in two installments; the dates are not yet read in a source, so the model keeps one payment and says so here. Storage costs do not pay Argentina's 0.6% transaction tax (`τ`): on ~1 USD/t per fortnight it is under a cent, and elevators typically deduct fees on the sale settlement (which already pays `τ` on the gross price).

## Grain stock, every crop, option and fortnight from harvest (equalities, SPEC-20)

At harvest (`p = h_c`):

  Σ_r v_{c,h,r} + Σ_k f_k·[crop_k = c, p_k = h_c] + Σ_m in_{c,m} − y_c·x_c = 0       (lines 364–375)
  s_{c,h,m} − (1 − shrink_entry_m)·in_{c,m} = 0                        for each m   (lines 377–384)

After harvest (`p > h_c`), with `1 − δ_m = (1 − shrink_monthly_m)^{1/2}`:

  s_{c,p,m} − (1 − δ_m)·s_{c,p−1,m} + o_{c,p,m} = 0                    for each m   (lines 388–396)
  Σ_r v_{c,p,r} + Σ_k f_k·[crop_k = c, p_k = p] − Σ_m o_{c,p,m} = 0                 (lines 398–407)

Forward deliveries are fixed: `f_k = tonnes_k` (lines 410–416). Summing the stock equations over `p = h_c … T−1` with `s_{c,T−1,m} = 0` enforces the exact mass balance `harvest = sales + forward deliveries + shrink` for every crop, checked after solving at lines 880–890.

## Limits (inequalities and bounds)

| Constraint | Math | Line |
|---|---|---|
| Land (shared arable) | Σ_c x_c + Σ_a y_a − rent_in − buy + rent_out ≤ H_own | 431–440 |
| Rotation (each crop `c`, on land held `H = H_own + rent_in + buy − rent_out`, SPEC-21) | x_c − share·rent_in − share·buy + share·rent_out ≤ share·H_own | 444–454 |
| Cattle-only land (lowlands) | Σ_a y_{low,a} ≤ livestock_only_ha | 458–466 |
| Max livestock share (on land held, SPEC-21) | Σ_a y_a − m·rent_in − m·buy + m·rent_out ≤ m·H_own | 468–478 |
| Storage capacity, each option `m` with `Cap_m ≠ null`, each fortnight | Σ_c s_{c,p,m} ≤ Cap_m (options with `Cap_m = null` get no row) | 480–492 |
| Credit line, each fortnight | D_p ≤ L | 494–498 |
| Route capacity (season) | Σ_{c,p} v_{c,p,r} (+ forward deliveries by that route) ≤ capacity_r | 501–515 |
| Shared leg capacity (season or month) | Σ over every route that uses the leg of Σ_{c,p} v_{c,p,r} ≤ capacity_leg | 517–589 |
| Min area (user constraint) | −x_c ≤ −ha | 595–600 |
| Max area (user constraint) | x_c ≤ ha | 601–606 |
| Min share (user constraint) | share·Σ_k x_k − x_c ≤ 0 | 607–615 |
| Payments by a date (user constraint, SPEC-19) | Σ_{p ≤ end of month} (payments per hectare on `x_c` and `z_{c,t}`) ≤ usd | 616–627 |
| Crop area non-negativity | x_c ≥ 0 (bound; rotation moved to row above) | 632 |
| End-of-season storage window | s_{c,T−1,m} = 0 for every `m` (bound) | 635 |
| Storage life (`max_months_m ≠ null`) | s_{c,p,m} = 0 for `p > h_c + 2·max_months_m` (bound) | 636–641 |
| Debt repaid | D_{T−1} = 0 unless `final_debt_allowed` (bound) | 642–643 |
| Land decisions | rent_in ≤ rent-in cap, rent_out ≤ H_own (if allowed), buy ≤ max_buy | 644–646 |
| Livestock land bounds | y_a ≤ total land, y_{low,a} ≥ 0 | 647–651 |

**Stated assumption — storage window.** Because the season has `T = 30` fortnights and `s_{c,T−1,m} = 0` leaves no grain at the end of fortnight 29, each crop's post-harvest storage window inside the model has `(T − 1 − h_c) / 2` months (for example, 3 months from late April to late July for soybean in Southeast Buenos Aires, 1 month from late June to late July for safrinha corn in Mato Grosso, and 8–8.5 months from October to June in Iowa). `evaluate_season` and `shadow_prices` report this window (`storage.window_by_crop`) alongside the end-of-window breakeven net price (`storage.breakeven_by_crop`, `dora/tools.py` lines 510–630) evaluated at `E_{c,m} = min(T − 1, ⌊h_c + 2·max_months_m⌋ + 1)` (the last fortnight in which grain can be sold out of option `m`, equal to `T − 1` when `max_months_m` does not bind earlier):

  breakeven_{c,m} = ( π_{c,h}·λ_h + fill_m·λ_h + Σ_{p=h}^{E_{c,m}−1} (monthly_m / 2)·λ_p·kept_{p,m} ) / ( λ_{E_{c,m}}·kept_{E_{c,m},m} )

where `kept_{p,m} = (1 − shrink_entry_m)·(1 − δ_m)^{p − h}` is the share of a tonne put in at harvest `h` still remaining at the end of fortnight `p`. Because `breakeven_{c,m}` uses the solution's own cash values `λ_p`, the comparison `π_{c,end} > breakeven_{c,m}` is strict only when capital is not scarce; when capital is scarce and the plan stores part of the harvest, `λ_p` adjusts until storing and selling at harvest are indifferent at the margin (`breakeven_{c,m} = π_{c,end}`). The agent never extrapolates beyond fortnight `T − 1`.

## Shadow prices (duals)
HiGHS returns, for each constraint, `∂(objective)/∂(right-hand side)`. The objective is −NPV before income tax, so **every dual changes sign** (lines 673–674). When `income_tax_rate > 0` and season profit is positive, **every reported shadow price** is multiplied by `tax_mult = 1 − t` (line 731) so that it equals the after-income-tax derivative of NPV; **`cash_value` (`λ_p`), `internal_rate_annual` and the stretch rates `rate_for_stretch` remain pre-income-tax** because internal rates are ratios `λ_p / λ_{p+1}` in which any constant factor cancels.

- `λ_p` (`Result.cash_value`, pre-income-tax): value today (before income tax) of one more dollar available in `p` (cash equation). With no capital shortage, `λ_p = (1+r_i)^{−p}` and `λ_0 = 1`.
- Shadow price of capital (`Result.capital_shadow_price`, line 914): `(λ_0 − 1)·tax_mult`, what one more dollar of own capital is worth today beyond depositing it at the market rate, after income tax (`∂NPV/∂K = λ_0·(1 − t) + t·d`, while depositing yields `1 − t + t·d` with `d = (1+r_i)^{−(T−1)}`, so their difference is `(λ_0 − 1)·(1 − t)`). Inside each capital stretch (`Result.get_capital_stretches`, lines 105–106), this season-wide figure is named `capital_shadow_price_today` so it is not confused with the stretch's own `rate_for_stretch`.
- Internal rate between `p` and `p+1` (pre-income-tax): `λ_p / λ_{p+1} − 1`, annualized as `(λ_p/λ_{p+1})^{24} − 1` (line 675). Above the market rate means capital is scarce in that stretch.
- Rotation (`Result.rotation_shadow_price`, lines 803–806): `μ^{rot}_c · tax_mult`, in USD today per extra hectare of crop `c`'s rotation cap.
- Land (`Result.land_shadow_price = ∂NPV / ∂H_own`, lines 780–801): `(μ^{land} + share·Σ_c μ^{rot}_c + m·μ^{ls} + μ^{rent\_out} − land\_tax·λ_0)·tax_mult`.
- Storage (`storage_by_option[m]["shadow_price_by_fortnight"]`, `["shadow_price_usd_t"]`, and `Result.storage_shadow_price` for `own_silo`, lines 873–900) and credit (`Result.credit_shadow_price`, lines 902 and 917): the duals of their rows multiplied by `tax_mult`, in USD today per extra tonne or dollar of credit line.
- User constraints (`Result.constraint_duals`, lines 733–753), routes and shared legs (lines 755–778), and cattle-only land (line 808): opportunity cost per unit of loosening the constraint, multiplied by `tax_mult`.

## How each one is checked (`tests/test_engine.py`, `tests/test_storage.py`, `tests/test_rotation_taxes.py`, `tests/test_income_tax_duals.py`)
The NPV is concave in each resource. So each dual must lie between the right derivative and the left derivative, computed by solving again with one unit more and one unit less. Plus economic and accounting properties:
- With plenty of capital, the internal rate equals the market rate everywhere and no credit is used.
- For every crop, `harvest = sales + forward deliveries + shrink`.
- Without `storage_options`, the solution equals the legacy single-option formulation identically.
- When capital is not scarce (and no capacity limit binds), grain is stored until the end of the window iff the model's end-of-window net price exceeds `breakeven_{c,m}`; when capital is scarce and the plan stores grain, the endogenous cash values equalize `breakeven_{c,m}` and the end-of-window net price.
- Rotation and livestock share caps apply to the land actually held (`H_own + rent_in + buy − rent_out`), `Result.land_shadow_price` matches finite-difference perturbations of `owned_ha` with rotation free, and payment terms without a surcharge never lower the NPV.


## Sowing windows and machinery (SPEC-25)

Each crop $c$ can have multiple sowing windows $w \in W_c$, each with its own sowing fortnight $	ext{sow}_{c,w}$, harvest fortnight $h_{c,w}$, and input/fertilizer schedule:
- **Decision variables**: $x_{c,w} \ge 0$ hectares sown in window $w$. Total crop area is $x_c = \sum_{w \in W_c} x_{c,w}$.
- **Financing**: with supplier payment options (SPEC-19), the term allocation is $z_{c,w,t} \ge 0$ with $\sum_t z_{c,w,t} = x_{c,w}$.
- **Harvest arrival & storage**: harvest of crop $c$ arrives across the set of fortnights $H_c = \{h_{c,w}\}$ with earliest harvest $h_c^0 = \min H_c$. Storage entry $	ext{in}_{c,m,p}$ occurs for every $p \in H_c$. Storage life $	ext{max\_months}_m$ is counted conservatively from $h_c^0$.
- **Sales and stock balance**: for every $p \ge h_c^0$:
  $$\sum_r v_{c,p,r} + \sum_k f_k \cdot [c_k=c, p_k=p] + \sum_m 	ext{in}_{c,m,p} - \sum_m o_{c,p,m} = \sum_{w: h_{c,w}=p} y_{c,w} \cdot x_{c,w}$$
  Mass balance $\sum_w y_{c,w} \cdot x_{c,w} = 	ext{sales} + 	ext{forward} + 	ext{shrink}$ is verified after solving.
- **Machinery capacity constraints**: when $	ext{sowing\_capacity\_ha\_per\_fortnight}$ is specified:
  $$\sum_{c, w: 	ext{sowing}_{c,w} = p} x_{c,w} \le 	ext{cap}_{	ext{sow}}$$
  The shadow price of this constraint reflects the value of an extra hectare of planter capacity in fortnight $p$.

## Two-stage stochastic engine (SPEC-25)

When $	ext{climate\_scenarios} = [\{id: s, 	ext{probability}: p_s, 	ext{yields}: y^s\}, \dots]$ is provided:
- **Assumption — climate mapping**: the seasonal outlook's rainfall terciles (below normal, near normal, above normal) map directly to dry, normal, and wet scenarios ($p_{	ext{dry}}, p_{	ext{normal}}, p_{	ext{wet}}$).
- **Stage 1 (decided today, before climate unfolds)**: crop window hectares $x_{c,w}$, financing $z_{c,w,t}$, land tenure ($	ext{rent\_in}, 	ext{rent\_out}, 	ext{buy}$), livestock, and forward sales contracts $f_k$.
- **Stage 2 (recourse, per climate scenario $s$)**: grain sales $v^s_{c,p,r}$, storage entry/stock/exit, cash $S^s_p$, and debt $D^s_p$.
- **Objective**:
  $$\max \sum_s p_s \cdot 	ext{NPV}_s$$
- **Duals per climate**: the dual value returned by HiGHS for scenario $s$ is weighted by $p_s$; the reported unweighted dual (the value of an extra dollar in fortnight $p$ if climate $s$ occurs) is divided by $p_s$ ($	ilde{\lambda}^s_p = \lambda^s_p / p_s$).
- **Value of Stochastic Solution (VSS)**: expected NPV of the stochastic solution minus the expected NPV of the deterministic normal-year plan evaluated across all climates ($	ext{VSS} \ge 0$).
