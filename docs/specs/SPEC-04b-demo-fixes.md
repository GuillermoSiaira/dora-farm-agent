# SPEC-04b: Fixes to the demo after review

**Branch:** keep working on `spec-04-demo-ui`. It gets merged after these fixes.

Reviewed in the browser with the "Capital restringido" example. The numbers match the engine, but four things need fixing.

## 1. Chart A is unreadable: one spike flattens everything
The annualized internal rate reaches about 1,400% in one fortnight, and every other fortnight looks like 0.
- **Replace the plotted series:** plot the **value today of one dollar available in each fortnight** (`λ_p`, the cash dual) against the same value if money were not scarce, `(1 + r)^(−p)` with `r` the fortnightly deposit rate.
  - The gap between the two lines is the scarcity.
  - Shade the area where `λ_p` is above the market line.
  - Title: "¿Cuánto vale un dólar en cada quincena?"
  - Caption: "Si la línea verde está arriba de la gris, en esa quincena la plata vale más que en el banco: el capital escasea."
- Expose `λ_p` in `shadow_prices`: add `"usd_today_per_dollar": round(cash_value[p], 4)` to each `by_fortnight` row (from `Result.cash_value`).
- Keep the annualized internal rate only as hover text, not as the plotted line.

## 2. Chart B mixes units on one axis
USD per dollar (capital, credit), USD per hectare (land) and USD per tonne (storage) cannot share an axis: a land value of 46 would flatten the others. Show:
- a small bar chart only for the two **per-dollar** values (capital, credit line);
- **two value cards** for land (USD/ha) and storage (USD/t), each with "no es una restricción activa" when the value is 0.

## 3. Spanish formatting
In Spanish mode:
- Numbers use the Argentine format: `88.186,60` and `100.000`.
- Fortnight labels are in Spanish: "1ª quincena de dic", "2ª quincena de mar (año 2)". Build them in the UI from the fortnight index; the engine keeps the English names.
- Crop names are in Spanish: trigo, maíz, soja, girasol, including the crop checkboxes.

## 4. Shorter origins on the plan card
Instead of repeating the full source after every crop, show one line per source used, for example "Rindes y precios: MAGyP, márgenes jun-2026, sudeste de Buenos Aires", and mark only the values given by the farmer.

## Tests
- `shadow_prices` rows include `usd_today_per_dollar`, and with plenty of capital it equals `(1+r)^(−p)` (rel 1e-9).
- The Spanish number formatter: `88186.6` → `"88.186,60"`, `100000` → `"100.000"`.
- The Spanish fortnight name for index 15 is `"2ª quincena de dic"`.
- All existing tests still pass.
