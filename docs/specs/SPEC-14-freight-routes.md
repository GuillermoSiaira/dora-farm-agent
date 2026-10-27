# SPEC-14: Freight routes to the buyer: truck, rail, barge and ship

**Status:** to implement after SPEC-13 (or in parallel on its own branch). **Branch:** `spec-14-routes`. Do not merge into `main`; it gets reviewed first.

## Why
Today each region has one number, `default_freight_usd_t`, for trucking to one port. That hides the main difference between the regions that compete for the same buyer:
- **United States:** corn and soybeans from Iowa go by truck to a river elevator, then by **barge** down the Mississippi to the Gulf (New Orleans), or by **rail** to the Pacific Northwest, then by ship to Asia.
- **Brazil:** from Mato Grosso, mostly **truck** over long distances, to Santos or Paranaguá, or north to the river terminals of Miritituba and onward by **barge** to the Amazon ports (the "Arco Norte"). Some **rail** (Rondonópolis to Santos).
- **Argentina:** mostly **truck** to the Up-River terminals around Rosario or to Quequén and Bahía Blanca; little **rail**. Ocean vessels load at Rosario on the Paraná river, but the draft limits loads, so many top off at Bahía Blanca or Quequén. **Barges** on the Paraná-Paraguay waterway bring grain from Paraguay and Bolivia down to Rosario.
- The main buyer for soybeans is China, so the fair comparison is the **landed price at the destination**, minus every leg back to the farm.

## 1. Data: `dora/data/routes_<region>.json`
Each region has one or more routes. A route is a list of legs; each leg has a mode, a from and to, a cost in USD/t, a source and a date.

```json
{
  "region": "iowa",
  "routes": [
    {"id": "gulf_barge", "name": "Truck to river elevator, barge to the Gulf, ship to China",
     "legs": [
       {"mode": "truck", "from": "farm", "to": "Mississippi river elevator", "usd_t": 0.0, "source": "...", "date": "..."},
       {"mode": "barge", "from": "St. Louis", "to": "New Orleans (Gulf)", "usd_t": 0.0, "source": "...", "date": "..."},
       {"mode": "port", "from": "Gulf", "to": "vessel", "usd_t": 0.0, "source": "...", "date": "..."},
       {"mode": "ocean", "from": "US Gulf", "to": "China", "usd_t": 0.0, "source": "...", "date": "..."}
     ]},
    {"id": "pnw_rail", "name": "Rail to the Pacific Northwest, ship to China", "legs": ["..."]}
  ],
  "placeholder": true
}
```

Public sources (each figure cites one; anything unverified gets `"placeholder": true`, as before):
- **United States:** USDA AMS *Grain Transportation Report* (weekly). It includes barge rates by river segment, rail tariffs, and ocean rates from the Gulf and the Pacific Northwest to Japan and China.
- **Brazil:** USDA AMS *Brazil Soybean Transportation* (quarterly). It includes truck rates from Mato Grosso to each port, the Miritituba barge route, and ocean rates to Shanghai. Also ESALQ-LOG.
- **Argentina:** CATAC truck reference tariff; rail tariffs where published; ocean rates from Up-River to China from public market reports. Port elevation (fobbing) from public reports.

## 2. Engine
- The **farm-gate price** of a sale is built backwards from the destination price, for the chosen route:
  farm-gate price = destination price − Σ legs (USD/t) − taxes.
- Two ways to get the destination price, both shown:
  - from the FOB or FAS price we already have, adding back the legs from farm to port (this keeps today's numbers when the route matches today's single freight figure);
  - from a destination quote, when one is available (CFR China), for the "landed price" comparison.
- **The route is a decision.** Sale variables split by route: `v_{c,p,r}`. In the cash equation each route has its own net price. A route may have a capacity in tonnes per season (`capacity_t`, optional, for example a rail allocation), which becomes a row with its own shadow price: "one more tonne of rail capacity is worth X".
- **Logistics is a network, and its capacities have shadow prices.** Routes are paths through shared nodes and arcs: farm → country elevator or rail terminal → river port → ocean port → vessel. Several routes can share an arc (two routes that both end at the same Rosario terminal, for example). So capacity is defined **per leg**, not only per route: each leg in the routes file may carry an id (`leg_id`) and a `capacity_t` (per season) or `capacity_t_by_month`. For every leg with a capacity there is one row:
  Σ over crops, fortnights and routes that use that leg of `v_{c,p,r}` ≤ capacity of the leg (in that month, if monthly).
  Its dual is the **shadow price of that piece of logistics**: what one more tonne of rail allocation, barge slot, port elevation or truck availability at harvest is worth to this farm. Report every leg's shadow price, with its mode, in `evaluate_season` and `shadow_prices`.
- **Combined modes** are just routes with legs of different modes (truck + rail + ship, truck + barge + ship). No special case.
- **Draft limits on the Paraná** enter as data, not as a new constraint type: a route "Up-River, partial load, top off at Bahía Blanca" has a higher ocean leg cost per tonne than a full-load route.
- With one route and the same total cost as today's `default_freight_usd_t`, the results are identical to today (backward compatible).
- Seasonality: a leg may have a cost per month (barge rates on the Mississippi change a lot in autumn with low water). Optional field `usd_t_by_month`.

## 3. Outputs and demo
- `evaluate_season` reports tonnes sold by route and the farm-gate decomposition per crop: destination price, each leg, taxes, farm-gate price.
- Demo, plan card: "your corn goes by barge to the Gulf; rail to the Pacific Northwest would pay X USD/t less".
- Comparison tab (SPEC-13), chart C: the stacked bar per region, from destination price down to farm-gate price, with each leg colored by mode (truck, rail, barge, port, ocean).
- A map layer in the observatory: each region's route drawn as a line to its port, colored by mode. Coordinates of ports and river terminals in the routes file.

## 4. Agent
Modeling guide phrases: "¿me conviene mandar por tren?", "¿cuánto me come el flete?", "¿qué pasa si baja el río?" → routes, a capacity, or a higher barge cost, then compare.

## Acceptance tests (`tests/test_routes.py`), no network
1. One route whose legs sum to today's freight gives the same plan and NPV as today, for every region.
2. Two routes with different costs and no capacity: all sales go by the cheaper route.
3. With a capacity on the cheaper route below the harvest, the cheaper route is used up to its capacity, the rest goes by the other, and the capacity's shadow price equals the cost difference between the routes, within tolerance, and passes the perturbation check.
4. A monthly barge cost that rises in autumn moves barge sales to other months or to the other route when the difference exceeds the storage cost.
5. Two routes share one leg with a capacity below the harvest: the sum of both routes' tonnes on that leg equals the capacity, and the leg's shadow price passes the perturbation check (capacity ± 1 t).
6. The decomposition adds up: destination − legs − taxes = farm-gate price, for every crop and route.
7. All existing tests still pass.
