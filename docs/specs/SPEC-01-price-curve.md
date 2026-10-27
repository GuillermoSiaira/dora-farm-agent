# SPEC-01: Price curve from futures markets

**Status:** to implement. **Branch:** `spec-01-price-curve`. Do not merge into `main`; it gets reviewed first.

## Why
DORA is a *dynamic* planner: when to sell and how much to store depend on how prices move over the season. Today `net_price` assumes a flat monthly rise (`monthly_price_rise`), which is a free assumption. Prices must come from markets:
- **Argentina:** Bolsa de Comercio de Rosario (spot "pizarra" prices) and Bolsa de Cereales de Buenos Aires.
- **United States:** CBOT futures (CME Group).

## Scope
1. A scenario can carry a **price curve** per crop: USD/t by calendar month. Between months, the price is interpolated linearly by fortnight.
2. Price curves are loaded from **snapshot files**: dated, with their source, filled from public delayed quotes. No live fetching in this spec; there are no licenses for redistributing exchange data.
3. Optional **basis** per crop: local price = curve price + basis (USD/t, can be negative). It is used for an Iowa elevator or a Rosario port price against CBOT.
4. The tools expose the curve and its origin.

Out of scope: hedging with futures or options, live feeds, Iowa costs (that is SPEC-03).

## Changes

### `dora/scenario.py`
- New fields on `Scenario`:
  - `season_start: str = "2026-05"`: the calendar month of fortnight 0, as `"YYYY-MM"`.
  - `price_curve: dict[str, dict[str, float]] = {}`: crop → {"YYYY-MM": USD/t}.
  - `basis_usd_t: dict[str, float] = {}`: crop → USD/t.
- New function `fortnight_month(season_start, p) -> str`: the `"YYYY-MM"` of fortnight `p`.
- New method `curve_price(c, p) -> float | None`:
  - `None` if the crop has no curve.
  - Otherwise, the price at fortnight `p`. Each month's value applies at the **first** fortnight of that month; fortnights in between are interpolated linearly.
  - Before the first month, use the first value; after the last, use the last value.
- `price(c)`: if the crop has a curve, return `curve_price(c, harvest) + basis`; otherwise as today.
- `net_price(c, p)`: if the crop has a curve, `curve_price(c, p) + basis − marketing_per_t`, ignoring `monthly_price_rise`; otherwise as today.
- **Do not change** `payments_per_ha` or anything in `engine.py`: the curve only changes coefficients, not the structure.

### `dora/prices.py` (new)
- `BUSHELS_PER_TONNE = {"corn": 39.368, "soybean": 36.744, "wheat": 36.744}`.
- `cents_per_bushel_to_usd_per_tonne(crop, cents) -> float`.
- `load_curve(path) -> dict`: reads a snapshot file and returns `{"curve": {crop: {"YYYY-MM": USD/t}}, "source": str, "as_of": "YYYY-MM-DD"}`, converting CBOT quotes to USD/t when `"unit": "cents/bu"`.
- `available_curves() -> list[str]`: snapshot names in `dora/data/price_curves/`.

### `dora/data/price_curves/` (new)
Two snapshot files with this format. G fills in the real numbers; the files can start with placeholder values clearly marked `"placeholder": true`.
```json
{
  "source": "CBOT settlement prices, delayed, cmegroup.com",
  "as_of": "2026-10-27",
  "unit": "cents/bu",
  "placeholder": true,
  "curve": {"corn": {"2026-12": 430.0, "2027-03": 445.0, "2027-05": 452.0, "2027-07": 458.0},
            "soybean": {"2027-01": 1010.0, "2027-03": 1022.0, "2027-05": 1034.0, "2027-07": 1041.0},
            "wheat": {"2026-12": 545.0, "2027-03": 560.0, "2027-05": 568.0, "2027-07": 575.0}}
}
```
- `cbot_2026-10-27.json` (unit `cents/bu`).
- `rosario_2026-10-27.json` (unit `usd/t`, crops wheat/corn/soybean/sunflower).

### `dora/tools.py`
- New parameters in `PARAMETERS`:
  - `price_curve_source` (string, one of `available_curves()`): loads that snapshot into `price_curve`.
  - `basis_usd_t` (dict crop → number, between −200 and 200).
- Validation: unknown snapshot → error listing the available ones. Months not in `YYYY-MM` format or prices ≤ 0 inside a snapshot → error at load time.
- `build_scenario`: for crops with a curve, `price_<crop>` has origin `"<source>, as of <as_of>"`, plus `placeholder` if the snapshot is a placeholder. Add `price_curve_<crop>` with the monthly values used.
- `sensitivity` does not need to support the curve.

### `dora/schemas.py`
Add the two parameters: `price_curve_source` as an enum of `available_curves()`, and `basis_usd_t` like `yields`.

### `docs/model.md`
In the coefficient table, add that `π_{c,p}` comes from the curve when there is one, with the interpolation rule.

## Acceptance tests (`tests/test_prices.py`)
1. **Conversion:** 1000 cents/bu of soybean = 367.44 USD/t (rel 1e-6).
2. **Interpolation:** with a curve {May: 300, Jul: 320} starting in May, fortnight 0 = 300, fortnight 2 (early Jun) = 310, fortnight 4 = 320, fortnight 10 = 320.
3. **Equivalence:** a flat curve equal to the MAGyP price for every crop gives the same NPV as `monthly_price_rise=0` (rel 1e-9).
4. **Storage responds to the curve:**
   - With plenty of capital, a soybean curve that rises 15 USD/t per month after harvest, and `storage_capacity_t=200`: storage is used and the total storage shadow price is > 0.
   - With a flat curve, storage is not used.
5. **Basis:** a basis of −20 on soybean lowers `net_price` by exactly 20 at every fortnight.
6. **Validation:** an unknown `price_curve_source` returns an error naming the available ones; a basis out of range is rejected.
7. **All existing tests still pass** (`pytest -q`).

## Rules
- Code, names and comments in English, in the style of the existing modules.
- No new dependencies. No network access in code or tests.
- Do not change the signs or the structure of the equations in `engine.py`.
- Small commits on the branch, with clear messages. Do not push to `main`.
