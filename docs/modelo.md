# The engine, equation by equation

Each equation is stated in math, then pointed to the line of `dora/motor.py` that writes it, with its sign. The solver (`scipy.optimize.linprog`, HiGHS) **minimizes** and takes every constraint as `A x = b` or `A x ≤ b`, so equations are written with all variables on the left.

## Indices and data
- `p = 0 … T−1`: fortnights, `T = 30`. Fortnight 0 is the first half of May.
- `c`: crop (wheat, maize, soybean, sunflower).
- `h_c`: harvest fortnight of crop `c` (`CALENDARIO` in `escenario.py`).
- `e_{c,p}`: USD per hectare paid in fortnight `p` (`Escenario.egresos_ha`).
- `y_c`: yield, t/ha. `π_{c,p}`: net price, USD/t, for a sale in `p` (`Escenario.precio_neto`).
- `a`: storage cost, USD per tonne per fortnight. `r_i`, `r_c`: fortnightly rates on cash surplus and on credit.
- `K`: own capital. `L`: credit line. `Cap`: storage capacity. `H`: land.

| Coefficient | Default source |
|---|---|
| `y_c`, costs, price at harvest | MAGyP margins report, Southeast Buenos Aires, June 2026 |
| Payment and harvest calendar | Assumption (`CALENDARIO`) |
| Monthly price rise after harvest, storage cost, rates | Assumptions (`Escenario` defaults) |

## Variables
- `x_c ≥ 0`: hectares of crop `c`.
- `v_{c,p} ≥ 0`: tonnes sold in `p`. `s_{c,p} ≥ 0`: tonnes in storage at the end of `p` (only for `p ≥ h_c`).
- `S_p ≥ 0`: cash surplus at the end of `p`. `D_p ≥ 0`: credit used at the end of `p`.

## Objective
Maximize the present value of final wealth:

  max (S_{T−1} − D_{T−1}) · (1+r_i)^{−(T−1)}

Line 90 sets the discount factor and line 92 the coefficients, **with the sign flipped** (−discount on `S`, +discount on `D`) because the solver minimizes.

## Cash, every fortnight (equality)

  S_p − D_p = (1+r_i) S_{p−1} − (1+r_c) D_{p−1} + Σ_c π_{c,p} v_{c,p} − Σ_c e_{c,p} x_c − a Σ_c s_{c,p} + K·[p=0]

Everything moved to the left, as in the code:

| Term | Coefficient | Line |
|---|---|---|
| `S_p`, `D_p` | +1, −1 | 99 |
| `S_{p−1}`, `D_{p−1}` | −(1+r_i), +(1+r_c) | 101 |
| `x_c` (costs leave cash) | +e_{c,p} | 103 |
| `v_{c,p}` (sales bring cash) | −π_{c,p} | 105 |
| `s_{c,p}` (storage costs cash) | +a | 106 |
| right-hand side | K in `p = 0`, else 0 | 108 |

## Grain stock, every crop and fortnight from harvest (equality)

  s_{c,p} = s_{c,p−1} + y_c x_c·[p = h_c] − v_{c,p}

In the code (line 113: `s` and `v` with +1): at harvest, `x_c` enters with −y_c (line 115); afterwards, `s_{c,p−1}` enters with −1 (line 117). Right-hand side 0.

## Limits (inequalities and bounds)

| Constraint | Math | Line |
|---|---|---|
| Land | Σ_c x_c ≤ H | 123–126 |
| Storage, each fortnight | Σ_c s_{c,p} ≤ Cap | 128–133 |
| Credit line, each fortnight | D_p ≤ L | 135–138 |
| Rotation | x_c ≤ f·H (bound, `max_fraccion_cultivo`) | 142 |
| No grain left, debt repaid | s_{c,T−1} = 0, D_{T−1} = 0 (bounds) | 143–144 |

The credit line is written as a constraint row, not as a bound, so its dual comes out directly.

## Shadow prices (duals)
HiGHS returns, for each constraint, `∂(objective)/∂(right-hand side)`. The objective is −NPV, so **every dual changes sign** (lines 153–154).

- `λ_p`: value today of one more dollar available in `p` (cash equation). With no capital shortage, `λ_p = (1+r_i)^{−p}` and `λ_0 = 1`.
- Shadow price of capital: `λ_0 − 1`, what one more dollar of own capital is worth beyond investing it at the market rate.
- Internal rate between `p` and `p+1`: `λ_p / λ_{p+1} − 1`, annualized as `(λ_p/λ_{p+1})^{24} − 1`. Above the market rate means capital is scarce in that stretch.
- Land, storage and credit: the duals of their rows, in USD today per extra hectare, tonne or dollar of credit line.

## How each one is checked (`tests/test_motor.py`)
The NPV is concave in each resource. So each dual must lie between the right derivative and the left derivative, computed by solving again with one unit more and one unit less. Plus some economic properties:
- With plenty of capital, the internal rate equals the market rate everywhere and no credit is used.
- Everything harvested gets sold.
- Rotation is respected.
- Payment terms without a surcharge never lower the NPV.
