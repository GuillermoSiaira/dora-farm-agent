# SPEC-06: Regions (Southeast Buenos Aires and Iowa) and the field on a map

**Status:** to implement after SPEC-04. **Branch:** `spec-06-regions-map`. Do not merge into `main`; it gets reviewed first.

## Why
The model's structure is the same everywhere; only the coefficients change. Showing the same engine planning a farm in Balcarce and one in Iowa proves it. The farmer marks the field on a map. That gives the exact hectares, and the location picks the region and therefore its data.

## 1. Regions
- A new data file `dora/data/iowa_2026.json` with the same keys per crop as the MAGyP file: price, yield, marketing_harvest, field_operations, seed, crop_protection, fertilizer, overhead_owned, rent, overhead_rented.
  - Source: Iowa State University Extension, "Estimated Costs of Crop Production in Iowa – 2026" (Ag Decision Maker, file A1-20), for corn following soybeans and soybeans following corn, in USD per acre, converted to USD/ha (×2.4711).
  - Write the source and the conversion in `_source`.
  - If a value cannot be verified from the publication, mark the file `"placeholder": true`. **Never invent figures.**
  - Crops: corn and soybean.
- A new `region` field on `Scenario`: `"southeast_buenos_aires"` (the default) or `"iowa"`. It selects:
  - the data file;
  - the calendar: Iowa plants corn in late April or May and harvests in October; soybean is planted in May and harvested in late September or October;
  - `season_start`: `"2026-04"` for Iowa;
  - the crop list.

  Put the calendars in a `REGIONS` dict in `scenario.py`: each region with its data file, `CALENDAR` and `season_start`. The current `CALENDAR` becomes `REGIONS["southeast_buenos_aires"]["calendar"]`, keeping the name `CALENDAR` as an alias so existing code and tests still work.
- With `region="iowa"` and `price_curve_source="cbot_latest"`, the price is the CBOT curve plus an Iowa basis. Default basis: a value from a cited public source, or a placeholder flagged as such.
- `tools.py` and `schemas.py`: add `region` with its enum. `build_scenario` shows the region and the origin of each coefficient.

## 2. Field on a map
- `dora/geo.py`, with no new dependencies:
  - `polygon_area_ha(coords) -> float`: geodesic area of a lon/lat polygon, using the spherical excess formula on the WGS84 mean radius 6,371,008.8 m.
  - `region_for_point(lon, lat) -> str | None`: simple bounding boxes. Southeast Buenos Aires is roughly lon −61.5 to −56.5 and lat −39.5 to −36.0. Iowa is roughly lon −96.7 to −90.1 and lat 40.3 to 43.6. Outside both, return `None` with a clear message.
- A new tool `field_from_map(polygon)`:
  - It takes a GeoJSON polygon and returns `{"area_ha": ..., "region": ..., "centroid": [lon, lat]}`.
  - The agent then uses the area and the region in the scenario.
- In the SPEC-04 app, a **Map** step in the Scenario tab:
  - A Leaflet map in a Gradio HTML block, loading Leaflet 1.9.4 from cdnjs. Base layer: OpenStreetMap; an Esri World Imagery satellite layer as an option, with attribution.
  - The user draws the field (Leaflet.draw 1.0.4 from cdnjs). The polygon goes to `field_from_map`, and the area and region fill in the inputs.
  - **No Google Maps:** it needs billing.

## Acceptance tests (`tests/test_regions_map.py`), no network
1. A 1 km × 1 km square near Balcarce (about −58.25, −37.85) has an area of 100 ha ± 0.5%.
2. `region_for_point(-58.25, -37.85) == "southeast_buenos_aires"`, `region_for_point(-93.6, 42.0) == "iowa"`, `region_for_point(2.35, 48.85) is None`.
3. `Scenario(region="iowa")` uses Iowa's crops, calendar and season start. The engine solves it, and every shadow price passes the same perturbation check as `tests/test_engine.py`.
4. The default region gives exactly the same results as before (NPV rel 1e-12).
5. `field_from_map` through `run_tool` returns area and region for a valid polygon, and a clear error for a self-intersecting or open one.
6. All existing tests still pass.
