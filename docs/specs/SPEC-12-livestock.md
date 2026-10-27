# SPEC-12: Livestock as an alternative use of the land

**Status:** to implement after SPEC-11. **Branch:** `spec-12-livestock`. Do not merge into `main`; it gets reviewed first.

## Why
In Southeast Buenos Aires much of the land is better suited to cattle than to crops, and farmers decide every season how much to graze and how much to sow. Without livestock, DORA misses the main alternative use of the land in that region, and the land's shadow price is wrong there.

## Activities
Three livestock activities, per hectare and per year, competing for the same land as crops:
1. **Cow-calf (cría)** with an owned herd: sells weaned calves once a year.
2. **Cow-calf with a herd purchase:** the herd is bought at the start, which ties up capital, and is valued at the end of the season (parameter `herd_end_value`: replacement value, slaughter value, or a fraction of the purchase price).
3. **Steer fattening (invernada):** buys young steers and sells them finished.

## Data (`dora/data/livestock_<region>.json`, with sources)
- **Argentina:** MAGyP "Resultados económicos ganaderos" (the public monthly livestock margins bulletin). Use the Cuenca del Salado cow-calf model and the Pampas fattening model, in ARS per hectare, converted at the BCRA rate of the bulletin date. Cite the bulletin, the model and the date.
- Herd purchase price per hectare and calf and steer prices from the same bulletin or from the Mercado Agroganadero de Cañuelas public price reports.
- **Never invent figures:** mark unverified values as placeholders.
- Iowa and Mato Grosso: no livestock in this spec.

## Engine
- New activities enter like crops: a variable `y_a ≥ 0` (hectares under activity `a`), with:
  - **payments per hectare by fortnight**: inputs, health, supplementation, and for herd purchase or fattening the animal purchase;
  - **income per hectare in the selling fortnights**: calves in autumn, finished steers when the fattening cycle ends;
  - **no storage**: livestock income is not storable grain. Model the sale dates as fixed by the cycle; selling earlier or later is out of scope.
- **Land row:** Σ crops + Σ livestock ≤ available land (with SPEC-10's rent and buy terms).
- An optional **cattle-only land** pool (`livestock_only_ha`): land not suitable for crops (lowlands), usable only by livestock, with its own row and its own shadow price.
- **Herd capital:** for herd purchase, the purchase is an outflow at fortnight 0 and the end value an addition to final wealth, the same pattern as land purchase in SPEC-10.
- Keep the cash and land sign conventions in `docs/model.md`, and document the new rows there with their lines.

## Tools and UI
- Parameters: `livestock` (a list of activities allowed), `livestock_only_ha`, `herd_end_value`, `max_livestock_share` (optional).
- `evaluate_season` reports hectares per livestock activity, and the shadow price of cattle-only land when present.
- The modeling guide maps phrases: "tengo 200 ha de bajo que solo sirven para vacas" → `livestock_only_ha: 200`; "hago cría" → `livestock: ["cow_calf"]`; "compro la hacienda" → the herd-purchase activity.
- Demo: livestock checkboxes and the cattle-only area input, and livestock activities in the plan card and charts.

## Acceptance tests (`tests/test_livestock.py`), no network
1. Without livestock activities, results are identical to the current engine (NPV rel 1e-12).
2. With cattle-only land and cow-calf allowed, cow-calf uses that land. Its shadow price passes the perturbation check of `tests/test_engine.py`.
3. When crop margins fall below cow-calf's (for example a 40% soybean price cut), livestock takes more of the shared land.
4. Herd purchase ties up capital at fortnight 0: with scarce capital, raising `herd_end_value` makes herd purchase more attractive, and lowering it less.
5. Livestock income enters cash with the same sign convention as grain sales.
6. All existing tests still pass.
