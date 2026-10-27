# The engine, equation by equation

Each equation is stated in math, then pointed to the line of `dora/engine.py` that writes it, with its sign. The solver (`scipy.optimize.linprog`, HiGHS) **minimizes** and takes every constraint as `A x = b` or `A x ≤ b`, so equations are written with all variables on the left.

## Indices and data
- `p = 0 … T−1`: fortnights, `T = 30`. Fortnight 0 is the first half of May.
- `c`: crop (wheat, corn, soybean, sunflower).
- `h_c`: harvest fortnight of crop `c` (`CALENDAR` in `scenario.py`).
- `e_{c,p}`: USD per hectare paid in fortnight `p` (`Scenario.payments_per_ha`).
- `y_c`: yield, t/ha. `π_{c,p}`: net price, USD/t, for a sale in `p` (`Scenario.net_price`).
- `a`: storage cost, USD per tonne per fortnight. `r_i`, `r_c`: fortnightly rates on cash surplus and on credit.
- `K`: own capital. `L`: credit line. `Cap`: storage capacity. `H`: land.

| Coefficient | Default source |
|---|---|
| `y_c`, costs, price at harvest | MAGyP margins report, Southeast Buenos Aires, June 2026 |
| Payment and harvest calendar | Assumption (`CALENDAR`) |
| Monthly price rise after harvest, storage cost, rates | Assumptions (`Scenario` defaults) |
| Net price `π_{c,p}` | When a price curve is given for crop `c`, `π_{c,p}` comes from the curve (monthly quotes apply at the first fortnight of each month, interpolated linearly by fortnight, with basis added and marketing costs subtracted). Otherwise, MAGyP harvest price with monthly price rise assumption. |


## Variables
- `x_c ≥ 0`: hectares of crop `c`.
- `v_{c,p} ≥ 0`: tonnes sold in `p`. `s_{c,p} ≥ 0`: tonnes in storage at the end of `p` (only for `p ≥ h_c`).
- `S_p ≥ 0`: cash surplus at the end of `p`. `D_p ≥ 0`: credit used at the end of `p`.
- `f_k ≥ 0`: tonnes delivered under forward sale commitment `k` in fortnight `p_k`.

## Objective
Maximize the present value of final wealth:

  max (S_{T−1} − D_{T−1}) · (1+r_i)^{−(T−1)}

Line 121 sets the discount factor and line 123 the coefficients, **with the sign flipped** (−discount on `S`, +discount on `D`) because the solver minimizes.

## Cash, every fortnight (equality)

  S_p − D_p = (1+r_i) S_{p−1} − (1+r_c) D_{p−1} + Σ_c π_{c,p} v_{c,p} + Σ_k (price_k − m_k) f_k·[p=p_k] − Σ_c e_{c,p} x_c − a Σ_c s_{c,p} + K·[p=0]

Everything moved to the left, as in the code:

| Term | Coefficient | Line |
|---|---|---|
| `S_p`, `D_p` | +1, −1 | 130 |
| `S_{p−1}`, `D_{p−1}` | −(1+r_i), +(1+r_c) | 132 |
| `x_c` (costs leave cash) | +e_{c,p} | 134 |
| `v_{c,p}` (sales bring cash) | −π_{c,p} | 136 |
| `s_{c,p}` (storage costs cash) | +a | 137 |
| `f_k` (forward sale brings cash in `p_k`) | −(price_k − marketing_k) | 143 |
| right-hand side | K in `p = 0`, else 0 | 145 |

## Grain stock, every crop and fortnight from harvest (equality)

  s_{c,p} = s_{c,p−1} + y_c x_c·[p = h_c] − v_{c,p} − Σ_k f_k·[crop_k = c, p = p_k]

In the code (line 151: `s` and `v` with +1; line 154: `f_k` with +1 for forward deliveries at `p = p_k`): at harvest, `x_c` enters with −y_c (line 156); afterwards, `s_{c,p−1}` enters with −1 (line 158). Right-hand side 0.

Forward sale delivery commitments are fixed equalities: `f_k = tonnes_k` (lines 163–169).

## Limits (inequalities and bounds)

| Constraint | Math | Line |
|---|---|---|
| Land | Σ_c x_c ≤ H | 173–176 |
| Storage, each fortnight | Σ_c s_{c,p} ≤ Cap | 178–183 |
| Credit line, each fortnight | D_p ≤ L | 185–188 |
| Min area (user constraint) | −x_c ≤ −ha | 195–199 |
| Max area (user constraint) | x_c ≤ ha | 200–204 |
| Min share (user constraint) | share·Σ_k x_k − x_c ≤ 0 | 205–214 |
| Rotation | x_c ≤ f·H (bound, `max_crop_share`) | 218 |
| No grain left, debt repaid | s_{c,T−1} = 0, D_{T−1} = 0 (bounds) | 219–220 |

The credit line and user constraints are written as constraint rows, not as simple bounds, so their duals come out directly.

## Shadow prices (duals)
HiGHS returns, for each constraint, `∂(objective)/∂(right-hand side)`. The objective is −NPV, so **every dual changes sign** (lines 239–240).

- `λ_p`: value today of one more dollar available in `p` (cash equation). With no capital shortage, `λ_p = (1+r_i)^{−p}` and `λ_0 = 1`.
- Shadow price of capital: `λ_0 − 1`, what one more dollar of own capital is worth beyond investing it at the market rate.
- Internal rate between `p` and `p+1`: `λ_p / λ_{p+1} − 1`, annualized as `(λ_p/λ_{p+1})^{24} − 1`. Above the market rate means capital is scarce in that stretch.
- Land, storage and credit: the duals of their rows, in USD today per extra hectare, tonne or dollar of credit line.
- User constraints: opportunity cost per unit of loosening the constraint (lines 244–260). For `min_area` and `max_area`, the dual in USD/ha; for `min_share`, the dual times sown land times 0.01 in USD/share point; for `forward_sale`, minus the dual of `f_k = tonnes` in USD/t.

## How each one is checked (`tests/test_engine.py`)
The NPV is concave in each resource. So each dual must lie between the right derivative and the left derivative, computed by solving again with one unit more and one unit less. Plus some economic properties:
- With plenty of capital, the internal rate equals the market rate everywhere and no credit is used.
- Everything harvested gets sold.
- Rotation is respected.
- Payment terms without a surcharge never lower the NPV.
