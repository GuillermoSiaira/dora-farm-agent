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
- `in_{c,m} ≥ 0`: tonnes of crop `c` put into storage option `m` in its harvest fortnight `h_c` (line 205).
- `s_{c,p,m} ≥ 0`: tonnes of crop `c` in storage option `m` at the end of fortnight `p`, for `p ≥ h_c` (line 207).
- `o_{c,p,m} ≥ 0`: tonnes of crop `c` taken out of storage option `m` in fortnight `p`, for `p > h_c` (line 209).
- `S_p ≥ 0`: cash surplus at the end of `p`. `D_p ≥ 0`: credit used at the end of `p`.
- `f_k ≥ 0`: tonnes delivered under forward sale `k` in fortnight `p_k`.
- `z_{c,t} ≥ 0` (only with `payment_options`, SPEC-19): hectares of crop `c` whose seed, fertilizer and crop protection are paid under supplier term `t` (the base term or an option); `Σ_t z_{c,t} = x_c`.

## Objective
Maximize the present value of final wealth, plus what the bought land and the herd are worth at the end:

  max (S_{T−1} − D_{T−1})·(1+r_i)^{−(T−1)} + buy·P_land·(1 + appreciation)^{T/24}·(1+r_i)^{−(T−1)} + Σ_a herd end value·y_a·(1+r_i)^{−(T−1)}

Line 237 sets the discount factor; lines 239–252 the coefficients, **with the sign flipped** because the solver minimizes. Income tax is applied after solving (lines 693–696): it scales the result and the after-tax shadow prices but does not change the plan.

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
| `S_p`, `D_p` | +1, −1 | 276 |
| `S_{p−1}`, `D_{p−1}` | −(1+r_i), +(1+r_c) | 278 |
| `x_c` (costs leave cash; `e_{c,p}` already includes `τ`) | +e_{c,p} | 280 (`add_payments`, 266–270) |
| `x_c`, `z_{c,t}` with `payment_options`: fixed payments (operations, overhead) on `x_c`, each term's input payments (delayed, with surcharge, in installments) on `z_{c,t}` | +e^{fixed}_{c,p}, +e^{t}_{c,p} | 266–270 |
| `in_{c,m}` at `p = h_c` (storage entry/fill cost leaves cash; does not pay `τ`) | +fill_m | 282–286 |
| `s_{c,p,m}` for `p ≥ h_c` (fortnightly storage holding cost leaves cash; does not pay `τ`) | +monthly_m / 2 | 287–289 |
| `v_{c,p,r}` (sales bring cash) | −π_{c,p,r} | 290–292 |
| `f_k` (forward sale brings cash in `p_k`): contract price − marketing without `F` − freight of route 1 if the price point is the port − taxes | −π_k | 294–305 |
| `rent_in` (rent paid up front in `p = 0`) | +R·(1+τ) | 309 |
| `rent_out` (rent received in `p = 0`) | −R·(1−τ) | 311 |
| `buy` (price plus the year's land tax in `p = 0`) | +P_land·(1+τ) + land tax | 313 |
| `y_a`, `y_{low,a}` (livestock payments in `p`) | +payments_{a,p} | 318–322 |
| `y_a`, `y_{low,a}` (herd purchase in `p = 0`) | +herd price·(1+τ) | 324–330 |
| `y_a`, `y_{low,a}` (livestock sale) | −net income_a | 332–336 |
| right-hand side | K − land tax·H_own in `p = 0`, else 0 | 340–343 |

Rent is paid in full in fortnight 0, as is usual in Argentina. Iowa's cash rent is often paid in two installments; the dates are not yet read in a source, so the model keeps one payment and says so here. Storage costs do not pay Argentina's 0.6% transaction tax (`τ`): on ~1 USD/t per fortnight it is under a cent, and elevators typically deduct fees on the sale settlement (which already pays `τ` on the gross price).

## Grain stock, every crop, option and fortnight from harvest (equalities, SPEC-20)

At harvest (`p = h_c`):

  Σ_r v_{c,h,r} + Σ_k f_k·[crop_k = c, p_k = h_c] + Σ_m in_{c,m} − y_c·x_c = 0       (lines 348–358)
  s_{c,h,m} − (1 − shrink_entry_m)·in_{c,m} = 0                        for each m   (lines 361–368)

After harvest (`p > h_c`), with `1 − δ_m = (1 − shrink_monthly_m)^{1/2}`:

  s_{c,p,m} − (1 − δ_m)·s_{c,p−1,m} + o_{c,p,m} = 0                    for each m   (lines 372–380)
  Σ_r v_{c,p,r} + Σ_k f_k·[crop_k = c, p_k = p] − Σ_m o_{c,p,m} = 0                 (lines 382–391)

Forward deliveries are fixed: `f_k = tonnes_k` (lines 395–400). Summing the stock equations over `p = h_c … T−1` with `s_{c,T−1,m} = 0` enforces the exact mass balance `harvest = sales + forward deliveries + shrink` for every crop, checked after solving at lines 819–829.

## Limits (inequalities and bounds)

| Constraint | Math | Line |
|---|---|---|
| Land (shared arable) | Σ_c x_c + Σ_a y_a − rent_in − buy + rent_out ≤ H_own | 414–423 |
| Cattle-only land (lowlands) | Σ_a y_{low,a} ≤ livestock_only_ha | 426–433 |
| Max livestock share | Σ_a y_a ≤ max_livestock_share · total land | 435–440 |
| Storage capacity, each option `m` with `Cap_m ≠ null`, each fortnight | Σ_c s_{c,p,m} ≤ Cap_m (options with `Cap_m = null` get no row) | 442–455 |
| Credit line, each fortnight | D_p ≤ L | 457–460 |
| Route capacity (season) | Σ_{c,p} v_{c,p,r} (+ forward deliveries by that route) ≤ capacity_r | 464–477 |
| Shared leg capacity (season or month) | Σ over every route that uses the leg of Σ_{c,p} v_{c,p,r} ≤ capacity_leg | 480–551 |
| Min area (user constraint) | −x_c ≤ −ha | 557–562 |
| Max area (user constraint) | x_c ≤ ha | 563–568 |
| Min share (user constraint) | share·Σ_k x_k − x_c ≤ 0 | 569–577 |
| Payments by a date (user constraint, SPEC-19) | Σ_{p ≤ end of month} (payments per hectare on `x_c` and `z_{c,t}`) ≤ usd | 578–589 |
| Rotation | x_c ≤ max_crop_share · total land (bound) | 594 |
| End-of-season storage window | s_{c,T−1,m} = 0 for every `m` (bound) | 597 |
| Storage life (`max_months_m ≠ null`) | s_{c,p,m} = 0 for `p > h_c + 2·max_months_m` (bound) | 598–603 |
| Debt repaid | D_{T−1} = 0 unless `final_debt_allowed` (bound) | 604–605 |
| Land decisions | rent_in ≤ rent-in cap, rent_out ≤ H_own (if allowed), buy ≤ max_buy | 606–608 |
| Livestock land bounds | y_a ≤ total land, y_{low,a} ≥ 0 | 609–613 |

**Stated assumption — storage window.** Because the season has `T = 30` fortnights and `s_{c,T−1,m} = 0` leaves no grain at the end of fortnight 29, each crop's post-harvest storage window inside the model has `(T − 1 − h_c) / 2` months (for example, 3 months from late April to late July for soybean in Southeast Buenos Aires, 1 month from late June to late July for safrinha corn in Mato Grosso, and 8–8.5 months from October to June in Iowa). `evaluate_season` and `shadow_prices` report this window (`storage.window_by_crop`) alongside the end-of-window breakeven net price (`storage.breakeven_by_crop`, `dora/tools.py` lines 509–629) evaluated at `E_{c,m} = min(T − 1, ⌊h_c + 2·max_months_m⌋ + 1)` (the last fortnight in which grain can be sold out of option `m`, equal to `T − 1` when `max_months_m` does not bind earlier):

  breakeven_{c,m} = ( π_{c,h}·λ_h + fill_m·λ_h + Σ_{p=h}^{E_{c,m}−1} (monthly_m / 2)·λ_p·kept_{p,m} ) / ( λ_{E_{c,m}}·kept_{E_{c,m},m} )

where `kept_{p,m} = (1 − shrink_entry_m)·(1 − δ_m)^{p − h}` is the share of a tonne put in at harvest `h` still remaining at the end of fortnight `p`. Because `breakeven_{c,m}` uses the solution's own cash values `λ_p`, the comparison `π_{c,end} > breakeven_{c,m}` is strict only when capital is not scarce; when capital is scarce and the plan stores part of the harvest, `λ_p` adjusts until storing and selling at harvest are indifferent at the margin (`breakeven_{c,m} = π_{c,end}`). The agent never extrapolates beyond fortnight `T − 1`.

## Shadow prices (duals)
HiGHS returns, for each constraint, `∂(objective)/∂(right-hand side)`. The objective is −NPV, so **every dual changes sign** (lines 634–635).

- `λ_p`: value today of one more dollar available in `p` (cash equation). With no capital shortage, `λ_p = (1+r_i)^{−p}` and `λ_0 = 1`.
- Shadow price of capital: `λ_0 − 1`, what one more dollar of own capital is worth beyond investing it at the market rate.
- Internal rate between `p` and `p+1`: `λ_p / λ_{p+1} − 1`, annualized as `(λ_p/λ_{p+1})^{24} − 1`. Above the market rate means capital is scarce in that stretch.
- Land, storage (per finite-capacity option `m`, with `Result.storage_shadow_price` exposing `own_silo`'s duals or zeros when `own_silo` has no capacity row, lines 812–816 and 831–840) and credit: the duals of their rows, in USD today per extra hectare, tonne or dollar of credit line.
- User constraints: opportunity cost per unit of loosening the constraint (lines 641–657). For `min_area`, `max_area` and `max_payments_by`, the dual in USD/ha or USD; for `min_share`, the dual times sown land times 0.01 in USD/share point; for `forward_sale`, minus the dual of `f_k = tonnes` in USD/t.

## How each one is checked (`tests/test_engine.py`, `tests/test_storage.py`)
The NPV is concave in each resource. So each dual must lie between the right derivative and the left derivative, computed by solving again with one unit more and one unit less. Plus economic and accounting properties:
- With plenty of capital, the internal rate equals the market rate everywhere and no credit is used.
- For every crop, `harvest = sales + forward deliveries + shrink`.
- Without `storage_options`, the solution equals the legacy single-option formulation identically.
- When capital is not scarce (and no capacity limit binds), grain is stored until the end of the window iff the model's end-of-window net price exceeds `breakeven_{c,m}`; when capital is scarce and the plan stores grain, the endogenous cash values equalize `breakeven_{c,m}` and the end-of-window net price.
- Rotation is respected, and payment terms without a surcharge never lower the NPV.
