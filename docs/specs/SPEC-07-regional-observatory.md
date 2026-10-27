# SPEC-07: Regional observatory and freight to port

**Status:** to implement after SPEC-06. **Branch:** `spec-07-observatory`. Do not merge into `main`; it gets reviewed first.

## Why
DORA should do more than answer one farmer. It should keep watching the main grain regions the way an expert analyst would, and publish a reference:
- How much does capital earn in each region this season?
- When is it scarce?
- What is each resource worth?

Freight to port is part of that: the same port price is worth less on a farm far from the port. It changes where storage pays and when to sell.

## 1. Freight to port (engine coefficient)
- A new `Scenario` field `freight_usd_t: float = 0.0`: the cost of trucking one tonne from the farm to the selling point.
- `net_price(c, p)` subtracts it: port price + basis − freight − marketing per tonne.
  - This is a coefficient change only; `engine.py` does not change.
  - With a price curve, the curve is a **port** price (FOB or FAS at the port), so freight applies. With MAGyP's farm-gate margin data, `freight_usd_t` defaults to 0, because the report's marketing item already includes freight.
- Each region carries a default freight with its source:
  - **Argentina:** distance to the port × the reference rate per km of the public freight table (CATAC/FADEEAC reference rates).
  - **United States:** USDA AMS Grain Transportation Report, truck rates.
  - **Brazil:** ESALQ-LOG freight indicators.

  If a figure cannot be verified from a public source, mark it as a placeholder. **Never invent figures.**

## 2. Regions in the observatory
| Region | Data | Port | Notes |
|---|---|---|---|
| Southeast Buenos Aires (Balcarce) | MAGyP margins, Southeast | Quequén (about 120 km) | already in the engine |
| Pampas core (Pergamino) | MAGyP margins, "Zona Núcleo" (same report) | Up-River Rosario (about 110 km) | new data file |
| Iowa (central) | Iowa State University, SPEC-06 | Mississippi River terminals | from SPEC-06 |
| Mato Grosso, Brazil (Sorriso) | IMEA cost of production (public) | Santos/Paranaguá or northern ports (about 1,000+ km) | stretch goal; placeholder until verified |

## 3. Observatory run
- `dora/observatory.py` with `run_observatory(regions, scenario_template) -> dict`:
  - For each region, it solves the same standard farm: 500 ha, its usual crops, a fixed capital and credit ratio per hectare, and the region's prices from SPEC-03 plus its freight.
  - It collects, per region:
    - NPV per ha and the rate of return on capital (final wealth over capital committed, annualized);
    - the capital shadow price and the scarce fortnights;
    - the land and storage shadow prices;
    - the crop mix.
- Output `observatory/latest.json`, plus a dated copy `observatory/<date>.json` to build history.
- The same fallback rules as SPEC-03: if a price feed fails, use the last good snapshot and say so in the output.
- **Optional commentary by the model:** when `DORA_API_KEY` is set, the agent writes a 120-word summary of the comparison. The verifier checks it: any unsupported number blocks publication of the commentary, and the numbers alone are published.
- Command line `python -m dora.observatory` for a scheduled daily or weekly run.

## 4. Visual (in the SPEC-04 app, new tab "Regions")
- A **map** (Leaflet, same setup as SPEC-06) with one marker per region. The marker color is the return on capital, using a sequential scale with a legend.
- A **comparison table**, one row per region: crop mix, NPV/ha, return on capital, capital shadow price, land shadow price, freight, price source and date.
- A **small-multiples chart**: one line per region of the internal rate by fortnight against its market rate, all on the same axes. Each region's season starts in a different month, so label calendar months.
- A **"Published reference" link** to `observatory/latest.json`, with its date.

## Acceptance tests (`tests/test_observatory.py`), no network
1. `freight_usd_t = 10` lowers `net_price` by exactly 10 at every fortnight, for a crop with and without a price curve.
2. With all else equal, a region with higher freight has a lower or equal NPV.
3. `run_observatory` over Southeast and Pergamino with mocked prices returns both regions with every field.
4. The output JSON is valid and has a date and the source of every price.
5. With the scripted model, a commentary with an invented number is not published, and the numbers still are.
6. All existing tests still pass.
