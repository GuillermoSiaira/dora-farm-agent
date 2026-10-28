# SPEC-17: Freight and rent counted once

**Status:** to implement (Claude, Friday 30/10). **Branch:** `spec-17-count-once` from `main`. Do not merge into `main`; it gets reviewed first.

## Why
The math review of 28/10 (vault note "DORA - mapa del código", section 7) found two costs that enter the model by two paths at once.

1. **Freight.**
   - MAGyP's marketing costs (`marketing_harvest`, about 58 USD/t for wheat in Southeast Buenos Aires) already include the trip from the farm to the port: short and long freight, commission, drying and other items.
   - When a scenario has routes (`compare_regions` always does), `farm_gate_decomposition` (`scenario.py` l. 506–508) subtracts the route's legs **and** the whole MAGyP marketing cost, so Argentine freight is subtracted twice.
   - A single-farm evaluation has the opposite problem: freight is inside one lump number, and the farmer never sees "freight to Rosario: X USD/t".
2. **Rent.**
   - With `rented_land = True`, `payments_per_ha` (`scenario.py` l. 573) adds the data file's rent to every sown hectare.
   - When `regional_rent_usd_ha` is also set (`compare_regions` sets it from `land_*.json`), the `rent_in` variable pays rent again.
   - Measured on 28/10 with 500 rented ha and 50,000 USD in Iowa: one rent gives 79 ha of corn and 8,245 USD of profit; both rents give no crop and only the deposit interest (2,427 USD).
   - Side effect: with `rented_land`, the engine reports 500 ha rented in while sowing 79, because idle rented land costs nothing.

## 1. One price rule per data source
Every region data file (`magyp_*.json`, `iowa_2026.json`, `mato_grosso_2026.json`) gets two fields, each with its source:
- `price_point`: where the reference price is quoted, either `"port"` (MAGyP: Rosario or Quequén) or `"local_elevator"` (Iowa: CBOT plus local basis).
- `freight_in_marketing_usd_t` per crop: the part of `marketing_harvest` that is freight from the farm to the price point.
  - **MAGyP:** read it from the breakdown of the same report. If the report does not break it down, use the region's CATAC reference freight (already in `REGIONS[...]["default_freight_usd_t"]`) and set `"placeholder": true` on that field.
  - **Iowa:** the ISU haul is to the local elevator, which is the price point, so it stays inside marketing and the route legs start at the elevator.

`marketing_ex_freight_usd_t = marketing_harvest / yield − freight_in_marketing_usd_t`.

## 2. Net price
- **Without routes:** the engine builds the default route from `freight_in_marketing_usd_t` (truck, farm to price point), not from `freight_usd_t = 0`.
  - The net price is unchanged against today: `price − freight − marketing_ex_freight − taxes`.
  - The freight now shows as its own line in `farm_gate_decomposition` and in `evaluate_season`, with its source.
- **With routes:** `net = destination price − legs − taxes − marketing_ex_freight`. The route replaces MAGyP's freight; it is never added to it.
- **Forward sales** (`engine.py` l. 278–286) use the same rule: price at the price point minus `marketing_ex_freight` minus taxes, minus freight when delivery is at the farm.
- `freight_usd_t` given by the farmer replaces `freight_in_marketing_usd_t` for the default route.

## 3. Rent through one variable
- `payments_per_ha` no longer adds `d["rent"]`. Rent is paid only by `rent_in`, at `regional_rent_usd_ha`.
- If `rented_land` is true and `regional_rent_usd_ha` is not given:
  - use `land_<region>.json` when it has a value;
  - otherwise use the data file's `rent`, as today.
- `rent_in` costs money, so the solver no longer rents idle land: rented hectares ≤ sown hectares.
- The overhead choice stays as today (`overhead_rented` when `rented_land`, else `overhead_owned`).
- Rent timing per region, in `land_<region>.json` as `rent_schedule` (share per fortnight).
  - Argentina: 100% at fortnight 0, as today.
  - Iowa: two payments, with the dates from the ISU source; if the dates are not in a source, keep 100% at fortnight 0 and say so in `docs/model.md`.

## 4. `docs/model.md`
Rewrite the cash equation table from the code as it is after this spec, with these terms: land (`rent_in`, `rent_out`, `buy`, its end value in the objective), taxes (`tx_pay`, `tx_rec`, gross receipts, income tax after solving), routes (`sell[c,p,r]`, route and leg capacities), livestock, and freight. Every term keeps its sign and line.

## Acceptance tests (`tests/test_count_once.py`), no network
1. **Rent once.** Iowa, 500 ha, 50,000 USD:
   - `rented_land=True` with `regional_rent_usd_ha=677.1` gives the same plan and NPV as `owned_ha=0, max_rent_in_ha=500, regional_rent_usd_ha=677.1`, with ±0.01 tolerance;
   - in both, `rent_in_ha` = sown hectares.
2. **Rent once, in the comparison.** `compare_regions` with a rented farm gives, for each region, the same NPV as test 1's single-farm setup with that region's rent.
3. **Freight once.** Southeast Buenos Aires, wheat, one route whose only leg costs `freight_in_marketing_usd_t`: the net price equals today's single-farm net price, ±0.01.
4. **Freight visible.** `evaluate_season` for Southeast Buenos Aires reports the freight per crop, with its value and source.
5. **Decomposition adds up.** For every region and crop: destination price − legs − taxes − marketing_ex_freight = net price.
6. **Forward sale.** A forward sale at the port price nets the same as a spot sale in the same fortnight.
7. **Changed numbers.** Existing tests whose expected numbers change are listed in the PR with the old and new values and the reason. No silent edits.
8. All other tests still pass.

## After the merge
- Claude reruns the live evaluation. Questions 35 and 36 (freight) should pass now.
- Rerun the four-region comparison. The finding "renting out beats farming in all four regions" is checked again with freight and rent counted once.
