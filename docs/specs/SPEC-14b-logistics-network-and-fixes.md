# SPEC-14b: Logistics as a network (shared legs), route data and comparison fixes

**Status:** to implement. **Branch:** `spec-14b-network` from `main`. Do not merge into `main`; it gets reviewed first.

SPEC-14 was implemented from the version of the spec before the section "Logistics is a network" was added (commit 282f4f8). Read `docs/specs/SPEC-14-freight-routes.md` again in full; this spec lists what is still missing and what the review found.

## 1. Capacity per shared leg (missing)
- Legs in `routes_<region>.json` get a `leg_id` when they are a physical facility that several routes can share (a port terminal, a rail line, a barge fleet, trucks at harvest).
- Optional `capacity_t` (per season) or `capacity_t_by_month` on a leg.
- Engine: for every leg id with a capacity, one inequality row: the sum of `sell[c, p, r]` over every crop, fortnight and route **that contains that leg** ≤ capacity (per month when monthly). Keep the per-route capacity that exists today.
- Report every leg's shadow price with its mode and name in `evaluate_season` and `shadow_prices` (`leg_shadow_prices`).
- Test: two routes share one leg whose capacity is below the harvest. Tonnes on that leg = capacity; its shadow price passes the perturbation check (capacity ± 1 t).

## 2. Route data that does not describe the region's farmer
- `routes_pampas_core.json`, route `barge_hidrovia`: a farm in Pergamino does not load barges at the farm. The Paraná-Paraguay barges carry grain from Paraguay and Bolivia to Rosario. Remove this route from Pampas Core, or replace it with a real chain (truck to a river terminal, barge, transshipment) only if a public source describes it for this zone.
- Every route file keeps `"placeholder": true` until each figure is read in its source. Add a `source` and `date` per leg, not only one citation per file.

## 3. Mato Grosso freight share of 54%
- The comparison shows a freight share of 53.6% for Mato Grosso, against 6–10% elsewhere. Find out whether it is real (Sorriso to Santos is about 2,000 km by road, so freight is a large share) or a computation error: price used as denominator, ocean legs counted twice, or Mato Grosso using `basis_iowa.json` (`REGIONS["mato_grosso"]["basis_file"]` points to the Iowa basis file).
- Mato Grosso needs its own basis file (placeholder until checked), not Iowa's.
- Test: freight share = inland legs ÷ farm-gate gross price, computed by hand for one region, equals the reported value.

## 4. `route_capacity_shadow_prices` only reports positive values
- `summary()` drops shadow prices ≤ 1e-4. Report zeros too when the route has a capacity, so the agent can say "the rail allocation is not binding".

## 5. Demo startup time
- `build_app()` takes about 17 seconds. Find what runs at build time (probably the observatory or a comparison run) and make it lazy: compute when the tab is opened or the button pressed. Target: under 5 seconds.

## Acceptance tests (`tests/test_routes_network.py`), no network
1. Shared-leg capacity: as in section 1.
2. A leg capacity that is not binding has a shadow price of 0 and appears in the output.
3. Freight share for one region equals the hand computation.
4. Mato Grosso no longer reads `basis_iowa.json`.
5. `build_app()` builds in under 5 seconds (skip the test on CI if it is flaky; keep it locally).
6. All existing tests still pass.
