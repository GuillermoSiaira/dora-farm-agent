# The engine, equation by equation

Each equation is stated in math, then pointed to the line of `dora/engine.py` that writes it, with its sign. The solver (`scipy.optimize.linprog`, HiGHS) **minimizes** and takes every constraint as `A x = b` or `A x ≤ b`, so equations are written with all variables on the left.

## Indices and data
- `p = 0 … T−1`: fortnights, `T = 30`. Fortnight 0 is the first half of the season's first month (May in Argentina and Mato Grosso, April in Iowa).
- `c`: crop. `a`: livestock activity. `r`: route to the buyer. `k`: forward sale.
- `h_c`: harvest fortnight of crop `c` (`REGIONS[...]["calendar"]` in `scenario.py`).
- `e_{c,p}`: USD per hectare paid in fortnight `p` (`Scenario.payments_per_ha`): field operations and seed at sowing, fertilizer and crop protection on their dates, overhead spread until harvest. Rent is **not** in it (it is paid by `rent_in`).
- `y_c`: yield, t/ha. `π_{c,p,r}`: net price, USD/t, for a sale in `p` by route `r` (below).
- `a_s`: storage cost, USD per tonne per fortnight. `r_i`, `r_c`: fortnightly rates on cash surplus and on credit.
- `K`: own capital. `L`: credit line. `Cap`: storage capacity. `H_own`: owned land. `R`: regional rent, USD/ha. `P_land`: land price, USD/ha.
- `τ`: tax per cash movement (Argentina's transaction tax); `g`: gross receipts tax rate.

| Coefficient | Default source |
|---|---|
| `y_c`, costs, price at harvest, marketing and harvest costs | MAGyP "Márgenes y Resultados", June 2026 (Argentina); ISU A1-20 2026 (Iowa); IMEA (Mato Grosso, provisional) |
| Payment and harvest calendar | Assumption (`REGIONS[...]["calendar"]`) |
| Monthly price rise after harvest, storage cost, rates | Assumptions (`Scenario` defaults) |
| Price curve | CBOT futures plus each region's basis, or MAGyP's port quotes (`feeds.py`) |
| `R`, `P_land` | `land_<region>.json` |
| Routes and freight | `routes_<region>.json` (provisional); without routes, one truck leg (below) |

### Net price (SPEC-17: every cost counted once)
Each data source declares its **price point**, the place where its price is quoted:
- `"port"` (MAGyP: Bolsa de Cereales quotes at Rosario or Bahía Blanca). The source's marketing and harvest cost includes the freight `F` to that port, so `F` is taken out of marketing and carried by the route.
- `"local_elevator"` (Iowa and Mato Grosso: CBOT plus local basis). The basis already discounts the trip onward, so the reference route adds its inland legs back.

  gross_{c,p} = curve price + basis, or the source's price × (1 + monthly rise)^{months after harvest}
  destination_{c,p} = gross_{c,p} + [inland legs of route 1 if the price is local] + port and ocean legs of route 1
  farm-gate_{c,p,r} = destination_{c,p} − all legs of r − g·gross − τ·gross
  π_{c,p,r} = farm-gate_{c,p,r} − (marketing_c / y_c − F·[price point = port])

Without routes, route 1 is one truck leg of `F` (the farmer's `freight_usd_t` when given). For a port price, the net price is then exactly the source's price minus its whole marketing cost, as before SPEC-17, but the freight is shown as its own line (`farm_gate_decomposition`). With routes, the route's legs replace `F`; they are never added to it.

## Variables
- `x_c ≥ 0`: hectares of crop `c`. `y_a`, `y_{low,a} ≥ 0`: hectares of livestock on shared land and on cattle-only land.
- `rent_in`, `rent_out`, `buy ≥ 0`: hectares rented in, rented out and bought.
- `v_{c,p,r} ≥ 0`: tonnes of crop `c` sold in fortnight `p` via route `r`.
- `s_{c,p} ≥ 0`: tonnes in storage at the end of `p` (only for `p ≥ h_c`).
- `S_p ≥ 0`: cash surplus at the end of `p`. `D_p ≥ 0`: credit used at the end of `p`.
- `f_k ≥ 0`: tonnes delivered under forward sale `k` in fortnight `p_k`.
- `z_{c,t} ≥ 0` (only with `payment_options`, SPEC-19): hectares of crop `c` whose seed, fertilizer and crop protection are paid under supplier term `t` (the base term or an option); `Σ_t z_{c,t} = x_c`.

## Objective
Maximize the present value of final wealth, plus what the bought land and the herd are worth at the end:

  max (S_{T−1} − D_{T−1})·(1+r_i)^{−(T−1)} + buy·P_land·(1 + appreciation)^{T/24}·(1+r_i)^{−(T−1)} + Σ_a herd end value·y_a·(1+r_i)^{−(T−1)}

Line 224 sets the discount factor; lines 226–239 the coefficients, **with the sign flipped** because the solver minimizes. Income tax is applied after solving (line 589): it scales the result and the after-tax shadow prices but does not change the plan.

## Cash, every fortnight (equality)

  S_p − D_p = (1+r_i)·S_{p−1} − (1+r_c)·D_{p−1}
             + Σ_{c,r} π_{c,p,r}·v_{c,p,r} + Σ_k π_k·f_k·[p = p_k]
             − Σ_c e_{c,p}·x_c − a_s·Σ_c s_{c,p}
             − [p = 0]·( R·(1+τ)·rent_in − R·(1−τ)·rent_out + (P_land·(1+τ) + land tax)·buy )
             − livestock payments and herd purchase + livestock sales
             + [p = 0]·(K − land tax·H_own)

Everything moved to the left, as in the code:

| Term | Coefficient | Line |
|---|---|---|
| `S_p`, `D_p` | +1, −1 | 250 |
| `S_{p−1}`, `D_{p−1}` | −(1+r_i), +(1+r_c) | 252 |
| `x_c` (costs leave cash; `e_{c,p}` already includes `τ`) | +e_{c,p} | 254 |
| `x_c`, `z_{c,t}` with `payment_options`: fixed payments (operations, overhead) on `x_c`, each term's input payments (delayed, with surcharge, in installments) on `z_{c,t}` | +e^{fixed}_{c,p}, +e^{t}_{c,p} | `add_payments` |
| `s_{c,p}` (storage costs cash) | +a_s | 256 |
| `v_{c,p,r}` (sales bring cash) | −π_{c,p,r} | 259 |
| `f_k` (forward sale brings cash in `p_k`): contract price − marketing without `F` − freight of route 1 if the price point is the port − taxes | −π_k | 261–272 |
| `rent_in` (rent paid up front in `p = 0`) | +R·(1+τ) | 276 |
| `rent_out` (rent received in `p = 0`) | −R·(1−τ) | 278 |
| `buy` (price plus the year's land tax in `p = 0`) | +P_land·(1+τ) + land tax | 280 |
| `y_a`, `y_{low,a}` (livestock payments in `p`) | +payments_{a,p} | 287–290 |
| `y_a`, `y_{low,a}` (herd purchase in `p = 0`) | +herd price·(1+τ) | 292–298 |
| `y_a`, `y_{low,a}` (livestock sale) | −net income_a | 300–303 |
| right-hand side | K − land tax·H_own in `p = 0`, else 0 | 306–310 |

Rent is paid in full in fortnight 0, as is usual in Argentina. Iowa's cash rent is often paid in two installments; the dates are not yet read in a source, so the model keeps one payment and says so here.

## Grain stock, every crop and fortnight from harvest (equality)

  s_{c,p} = s_{c,p−1} + y_c·x_c·[p = h_c] − Σ_r v_{c,p,r} − Σ_k f_k·[crop_k = c, p = p_k]

In the code: `s` and every `v_{c,p,r}` with +1 (lines 316–318), `f_k` with +1 at `p = p_k` (line 321); at harvest `x_c` enters with −y_c (line 323), afterwards `s_{c,p−1}` with −1 (line 325). Right-hand side 0. Forward deliveries are fixed: `f_k = tonnes_k` (line 334).

## Limits (inequalities and bounds)

| Constraint | Math | Line |
|---|---|---|
| Land (shared arable) | Σ_c x_c + Σ_a y_a − rent_in − buy + rent_out ≤ H_own | 340–349 |
| Cattle-only land (lowlands) | Σ_a y_{low,a} ≤ livestock_only_ha | 351–359 |
| Max livestock share | Σ_a y_a ≤ max_livestock_share · total land | 361–366 |
| Storage, each fortnight | Σ_c s_{c,p} ≤ Cap | 368–374 |
| Credit line, each fortnight | D_p ≤ L | 375–379 |
| Route capacity (season) | Σ_{c,p} v_{c,p,r} (+ forward deliveries by that route) ≤ capacity_r | 381–396 |
| Shared leg capacity (season or month) | Σ over every route that uses the leg of Σ_{c,p} v_{c,p,r} ≤ capacity_leg | 398–470 |
| Payments by a date (user constraint, SPEC-19) | Σ_{p ≤ end of month} (payments per hectare on `x_c` and `z_{c,t}`) ≤ usd | `max_payments_by` |
| Min area (user constraint) | −x_c ≤ −ha | 475–481 |
| Max area (user constraint) | x_c ≤ ha | 482–487 |
| Min share (user constraint) | share·Σ_k x_k − x_c ≤ 0 | 488–496 |
| Rotation | x_c ≤ max_crop_share · total land (bound) | 500 |
| No grain left, debt repaid | s_{c,T−1} = 0, D_{T−1} = 0 (bounds) | 501–502 |
| Land decisions | rent_in ≤ rent-in cap, rent_out ≤ H_own (if allowed), buy ≤ max_buy | 503–505 |
| Livestock land bounds | y_a ≤ total land, y_{low,a} ≥ 0 | 506–510 |

The credit line, cattle-only land, route and leg capacities and user constraints are rows, not bounds, so their duals come out directly.

## Shadow prices (duals)
HiGHS returns, for each constraint, `∂(objective)/∂(right-hand side)`. The objective is −NPV, so **every dual changes sign** (lines 529–530).

- `λ_p`: value today of one more dollar available in `p` (cash equation). With no capital shortage, `λ_p = (1+r_i)^{−p}` and `λ_0 = 1`.
- Shadow price of capital: `λ_0 − 1`, what one more dollar of own capital is worth beyond investing it at the market rate.
- Internal rate between `p` and `p+1`: `λ_p / λ_{p+1} − 1`, annualized as `(λ_p/λ_{p+1})^{24} − 1`. Above the market rate means capital is scarce in that stretch.
- Land, storage and credit: the duals of their rows, in USD today per extra hectare, tonne or dollar of credit line.
- User constraints: opportunity cost per unit of loosening the constraint (lines 533–550). For `min_area` and `max_area`, the dual in USD/ha; for `min_share`, the dual times sown land times 0.01 in USD/share point; for `forward_sale`, minus the dual of `f_k = tonnes` in USD/t.

## How each one is checked (`tests/test_engine.py`)
The NPV is concave in each resource. So each dual must lie between the right derivative and the left derivative, computed by solving again with one unit more and one unit less. Plus some economic properties:
- With plenty of capital, the internal rate equals the market rate everywhere and no credit is used.
- Everything harvested gets sold.
- Rotation is respected.
- Payment terms without a surcharge never lower the NPV.
