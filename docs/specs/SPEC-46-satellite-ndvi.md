# SPEC-46: crop vigour from Sentinel-2 (NDVI of the farmer's field), into the plan

**Status:** ready (7/11), approved by Guillermo. Implement in **`D:\projects\dora-main`**, on branch `spec-46-satellite-ndvi` created from `spec-44-public-connector` (the latest stacked branch; if SPEC-45, the spreadsheet v2, is committed first, branch from it instead). Do not merge, do not push. Commit with messages starting `SPEC-46 implementation:`; write the handoff and Claude reviews. **Do not redeploy `serve_app.py` or `serve_mcp.py` before 10/11** (hackathon judging). No paid API, no account, no key: this spec must cost 0 USD.

Touch only: a new `dora/satellite.py`, `dora/tools.py` (one tool, and the re-plan helper moved out of `assess_field_image`), `dora/schemas.py` (its schema), `dora/verifier.py` (three small rules, section 5), `dora/modeling_guide.md` (one section), `dora/agent.py` (the field polygon in the screen context), `app.py` (Map tab button and the overlay in the chat), `mcp_server/server.py` (one tool), `tests/test_tools.py` and `tests/test_spec40.py` (tool lists only), a new `requirements-geo.txt`, a new `tests/test_spec46.py`, fixtures under `tests/fixtures/sentinel2/`, and the handoff.

**Why.** Today DORA plans with the region's average yield (MAGyP) or the one the farmer says. A farmer whose soybean is suffering knows it before the harvest, and so does the satellite: Sentinel-2 photographs every field in the Pampas every 2 to 5 days at 10 m, for free. NDVI (how green and dense the canopy is) of **his own field**, compared with **the same field in other years**, is a real measurement that can move the expected yield, and with it the sales, the storage, the credit and the cash of the plan. Like SAM's flooded area (SPEC-18), it is a number a tool measured, so the verifier can trace it; the language model never guesses it.

## 1. Data source: Element84 Earth Search (STAC) over the Sentinel-2 COGs on AWS

| Source | Account or key | Server-side statistics | What it would take |
|---|---|---|---|
| **Element84 Earth Search v1** (`https://earth-search.aws.element84.com/v1`, collection `sentinel-2-l2a`) | **none** | no: we read the pixels | `pystac-client` (or plain HTTP) + `rasterio` reading only the field's window of each COG |
| Microsoft Planetary Computer STAC | none for reading, but every asset URL must be signed with its token service | no | same as above plus the signing step; one more service that can change |
| Copernicus Data Space (Sentinel Hub Statistical API, openEO) | account and OAuth client | yes | registration and credentials in `.env`; free quota per month |

**Choice: Earth Search.** No registration, no key, no quota to watch, the same Sentinel-2 L2A (surface reflectance, already atmospherically corrected) as Copernicus, served as Cloud-Optimized GeoTIFFs on a public S3 bucket, so reading a 100 ha field downloads a few hundred kB with HTTP range requests, not a 1 GB scene. Copernicus would compute the statistics on its side but needs an account: keep it as the fallback if Earth Search goes down (section 9), not as the first option.

**Prototype that Claude ran on 7/11** (no key, Python 3.14, `rasterio 1.5.2` wheel for Windows, a made-up 100 ha square at lon −61.00, lat −33.90 near Pergamino, scripts in `D:\projects\tools\proto-geo-scripts\`):
- The STAC search returned 8 scenes of tile 20HPH between 1/9 and 7/11; reading red, NIR and the scene classification (SCL) for the field took **10 to 16 s per scene**.
- Field NDVI per scene: 2/10 0.583 (100 % clear), 22/9 0.537 (100 %), 17/9 0.519 (100 %), 29/9 0.417 (19.5 % clear), 19/10 0.275 (49.7 % clear), 17/10 no clear pixel.
- **The tile's cloud cover says little about the field:** 2/10 had 45 % cloud on the tile and the field fully clear; 29/9 had 14 % on the tile and the field 80 % covered. Filter by the field's own pixels (SCL), never by `eo:cloud_cover` alone.
- **Trap found:** every Earth Search item has `earthsearch:boa_offset_applied: true` (the −1000 offset of processing baseline ≥ 04.00 is already removed from the numbers) **and still declares** `raster:bands.offset = −0.1`. Applying that offset gave NDVI 1.43 (impossible). Reflectance is `DN × 0.0001` when `boa_offset_applied` is true; only otherwise, for baseline ≥ 04.00, `DN × 0.0001 − 0.1`. Test 3 pins this.
- Partly cloudy scenes read lower (19/10: 0.275 with half the field clear): cloud edges and shadows the SCL misses pull NDVI down. Hence the 70 % clear threshold and the one-pixel inward buffer of section 3.

## 2. The tool: `field_ndvi`
```python
field_ndvi(
    field: dict | list | None = None,     # GeoJSON Polygon/Feature/ring, as field_from_map; or {"lat": .., "lon": ..}
    scenario: dict | None = None,         # the farmer's scenario; needed for the yield proposal and the re-plan
    crop: str | None = None,              # the crop on that field now: wheat, corn, soybean, sunflower
    date: str | None = None,              # "YYYY-MM-DD", default today: look for the latest clear scene up to this date
    max_age_days: int = 30,               # do not use a scene older than this
    min_clear_share: float = 0.7,         # share of the field's pixels that must be clear
    same_crop_years: list[int] | None = None,   # years the farmer says he had the same crop on this field
    replan: bool = False,                 # True after the farmer confirms the yield (section 4)
    yield_t_ha: float | None = None,      # the yield he confirmed, when replan=True
    lang: str | None = None,
) -> dict
```
`{"lat", "lon"}` without a polygon: a square of `scenario.area_ha` centred there, with `field_note` "Lectura aproximada: dibujá el lote en el mapa para una lectura precisa." / en equivalent. Fields above 5,000 ha or below 1 ha → `ScenarioError` with what to do (split it; or "too small for 10 m pixels"). Outside the four regions: the reading works, the yield proposal does not (no regional table, section 4).

**Output** (all numbers rounded as shown; every one of them may appear in the answer):
```json
{
  "status": "ok",                         // or "no_clear_scene", "no_scene"
  "field_ha": 100.2, "centroid": [-61.0, -33.9], "region": "pampas_core",
  "scene_id": "S2B_20HPH_20261002_1_L2A", "scene_date": "2026-10-02",
  "scene_day": 2, "scene_month": 10, "scene_year": 2026, "days_old": 36,
  "clear_share_pct": 100.0, "pixels_clear": 10012,
  "ndvi_median": 0.58, "ndvi_p10": 0.41, "ndvi_p90": 0.71,
  "weak_share_pct": 12.4, "weak_ha": 12.4,          // pixels below 0.8 x the field's median
  "water_share_pct": 0.0,                            // SCL class 6 inside the field (flooding)
  "normal": {"ndvi_median": 0.69, "years_used": [2021, 2022, 2023, 2024, 2025],
             "per_year": {"2021": 0.71, "2022": 0.64, ...}, "window_days": 15},
  "anomaly_pct": -15.9,                              // (now / normal - 1) x 100
  "yield": {"crop": "wheat", "base_t_ha": 3.8, "base_source": "MAGyP pampas_core (o lo dijo el productor)",
            "ratio_used": 0.841, "proposed_t_ha": 3.2, "rule": "...", "needs_confirmation": true},
  "scenes_considered": [{"date": "2026-10-19", "clear_share_pct": 49.7, "used": false}, ...],
  "overlay_path": "...png",
  "history_note": "En años anteriores el lote pudo tener otro cultivo: si me decís en qué años tuvo trigo, comparo solo con esos.",
  "source": "Sentinel-2 L2A (ESA Copernicus), via Element84 Earth Search; NDVI computed by DORA",
  "checks": {"ndvi_in_range": true, "enough_pixels": true, "reflectance_rule": "boa_offset_applied"}
}
```
`scene_day`, `scene_month`, `scene_year` and `days_old` are numbers on purpose: the verifier only accepts numbers it finds in tool results, so "la imagen es del 2 de octubre" needs the 2 and the 10 there (section 5). With `status: "no_clear_scene"`: no NDVI, the list of scenes with their clear share, and the message "Las imágenes de los últimos 30 días tienen nubes sobre el lote; la próxima pasada es en 2 a 5 días." With `replan=True`: the same reading (from the cache, not downloaded again) plus `before`, `after`, `npv_change_usd`, `extra_credit_needed_usd`, exactly as `assess_field_image` returns them.

## 3. Computing NDVI (`dora/satellite.py`)
1. **Search** Earth Search with `intersects` = the field polygon, `collections=["sentinel-2-l2a"]`, `datetime` = `[date − max_age_days, date]`, sorted newest first. Earth Search may return the same date twice (a reprocessed `_1_L2A` and the original `_0_L2A`): keep the highest processing number per tile and date.
2. **Pick the scene:** newest first, read only the SCL band (20 m, the cheapest) over the field; the first scene with clear share ≥ `min_clear_share` wins. Clear = SCL 4 (vegetation) or 5 (bare soil). Cloud (8, 9, 10), cloud shadow (3), saturated (1), dark (2), unclassified (7) and snow (11) are not clear. Water (6) is reported apart (`water_share_pct`) and left out of NDVI.
3. **Pixels inside the field:** reproject the polygon to the scene's UTM (`proj:code`), rasterize it on the 10 m grid of B04 (`rasterio.features.geometry_mask`), and **shrink it one pixel** (binary erosion) so pixels shared with the road or the neighbour do not count. SCL is read on the same window resampled to 10 m with `nearest`.
4. **Reflectance** with the rule of section 1, then NDVI = (NIR − red) / (NIR + red) on clear pixels with both bands > 0. Fewer than 20 clear pixels → treat as no clear scene.
5. **Statistics:** median, p10, p90; weak share = clear pixels with NDVI < 0.8 × the field median; weak ha = weak share × field ha.
6. **Normal:** for each of the 5 previous years (or `same_crop_years`, when the farmer gave them), the clearest scene within ±15 days of the same day of the year (same steps 2–5); normal = median of the per-year medians. Fewer than 3 usable years → `normal: null`, no anomaly, no yield proposal, and say why.
7. **Overlay PNG** (Pillow, already a dependency): NDVI on a red–yellow–green scale, non-clear pixels grey, the field outline in white, a scale bar in hectares. Saved like `assess_field_image`'s overlay.
8. **Speed and cache.** Read the years in parallel (thread pool of 8, timeout 20 s per COG, total budget 90 s; past the budget return what is done with `status: "partial"`). Cache every per-scene result (scene id + polygon hash → statistics and the small NDVI array) as JSON + `.npy` in `DORA_CACHE_DIR` (on this machine `D:\projects\tools\dora-cache`, set in `.env`; never a default under `C:\Users`: when the variable is unset, use a temp dir and say it in the log). A second call for the same field and date answers in under 1 s; this is what makes the demo and `replan=True` instant.
9. **Network seam:** all HTTP goes through two functions, `search_scenes(...)` and `read_window(href, bounds, crs, out_shape=None)`, injectable as `_search` and `_reader` (like `_segmenter` in SPEC-18) so tests use fixtures. `DORA_OFFLINE=1` → `_search` raises `ScenarioError("Sin conexión: no puedo bajar la imagen satelital ahora.")` unless a fixture or cache answers.

Dependencies in a new `requirements-geo.txt`: `rasterio>=1.4` (Windows wheels include GDAL; 1.5.2 has a cp314 wheel), `pyproj`, `pystac-client` (optional: a plain POST to `/search` also works and is what the prototype did). The core `requirements.txt` does not change; `dora/satellite.py` imports rasterio inside the functions and the tool says "falta instalar requirements-geo.txt" when it is missing. Add `requirements-geo.txt` to the Modal image in `infra/modal/serve_app.py` and `serve_mcp.py` **without deploying** (deploy after 10/11, Guillermo decides).

## 4. From NDVI to the plan
**The yield proposal is a stated rule, not a model.** NDVI is related to yield, but the relation depends on the crop, the stage, the soil and the year; DORA does not have a calibrated model, and must not pretend to.
- Proposal only when the date falls in the crop's **reading window** (when the canopy already says something about grain), per region, in a table in `satellite.py` with source "supuesto DORA, a calibrar (SPEC-46)": pampas_core and southeast_buenos_aires — wheat 15/9 to 10/11, corn (early) 15/12 to 15/2, soybean (first) 15/1 to 15/3, sunflower 1/12 to 31/1; iowa — corn 1/7 to 31/8, soybean 15/7 to 31/8; mato_grosso — soybean 15/11 to 15/1. Outside it: the reading and the anomaly, and `yield.note` "Todavía es temprano (o tarde) para que el verde diga algo del rinde del <cultivo>."
- `ratio_used` = now / normal, **clipped to [0.5, 1.1]**; `proposed_t_ha` = base × ratio, rounded to 0.1. Base = the yield in the scenario (what the farmer said, else the region's). The `rule` text says it plainly: "Rinde propuesto = rinde normal × (verde de hoy ÷ verde normal del lote). Es una regla simple, no un modelo calibrado."
- **The farmer confirms.** The tool never changes the scenario on its own. The guide makes the agent show the reading and ask: "¿Uso 3,2 t/ha de trigo en vez de 3,8 para rehacer el plan?" On yes, the agent calls `field_ndvi(..., replan=True, yield_t_ha=3.2)`. If the farmer says another number ("pongele 3,5"), that one is used: it is his number.
- **Re-plan** = move the re-plan block of `assess_field_image` (sown hectares fixed at ±0.01 ha, `final_debt_allowed`, bisection for the extra credit) to one helper `_replan_with_yields(scenario, yields_after, crops)` used by both tools. `assess_field_image`'s output must not change: every existing test in `tests/test_field_image.py` passes untouched.
- **Before sowing** (no crop on the field yet): no yield proposal. The reading can still say the field is bare, flooded (`water_share_pct`) or has a winter crop. A field-specific yield potential from past seasons is future scope (section 9).

## 5. Verifier (`dora/verifier.py`)
1. Add `field_ndvi` to `SEASON_SOLVING_TOOLS` (its scenario is checked like any other when `replan=True`).
2. **Area from a measured field:** in `check_scenario` rule 1, `area_ha` is also accepted when it equals (within 1 %) a `field_ha` or `area_ha` returned by `field_from_map` or `field_ndvi` in this conversation's tool results. Today only the farmer's words count, so a field drawn on the map is flagged "area_ha missing" (test 12 shows it first, then the fix).
3. **Dates as numbers:** no new rule; the tool returns `scene_day`, `scene_month`, `scene_year`, `days_old`. Test 11 proves "La imagen es del 2 de octubre de 2026, de hace 36 días" verifies, and "del 5 de octubre" does not.
- Nothing in the verifier knows whether the soybean is really bad: it checks that every number came from the satellite reading, the farmer or the engine. Say so in the guide and in the handoff.

## 6. Agent, guide, app, MCP
- **Guide** (`modeling_guide.md`, new section "2c. The satellite"): when the farmer asks how a field or crop is doing, or mentions drought, a bad-looking crop or "cómo viene el lote", and there is a polygon (screen context or a drawn field) or coordinates, call `field_ndvi`. Say the image date and how old it is, the field's NDVI against its normal in words ("está 16 % menos verde que lo normal para esta fecha"), the weak hectares, and the yield proposal as a question. Never call NDVI "rinde". If there is no clear scene, say when the next pass is likely. Ask which past years had the same crop when the farmer seems to rotate. Do not use a reading older than 30 days to change the plan.
- **Screen context** (`dora/agent.py`): when a polygon was drawn on the Map tab, the screen context includes `"field_polygon": <GeoJSON>`; the agent can pass it as `field`. Coordinates are not checked as numbers (they are not scenario parameters).
- **App, Map tab:** button "Ver cómo viene el lote (satélite)" / "Check the field from the satellite", enabled when a polygon is drawn; shows the overlay, the date, NDVI now vs normal, weak ha, and the line "Sentinel-2 (ESA Copernicus), imagen del <fecha>". In the chat, the overlay appears under the answer exactly like `assess_field_image`'s (`overlay_path`, `app.py` around the current line 2944).
- **MCP** (`mcp_server/server.py`): `field_ndvi(field, scenario=None, crop=None, date=None, same_crop_years=None, replan=False, yield_t_ha=None, lang="es")` returns the output (overlay as an embedded PNG resource, base64) with `provenance`. Open to anonymous callers (SPEC-44), it costs only bandwidth; count it in the anonymous limit as any call.

## 7. Demo script (Telegraph hackathon; also for a Bolsa de Comercio de Rosario event)
Prepare the day before: pick a real wheat field in the Pampas (Guillermo chooses; a public one, not a farmer's private field without permission) whose NDVI this season is clearly below its normal, run the tool once to warm the cache (`DORA_CACHE_DIR`), and keep the overlay PNG as a slide in case the network fails. The numbers below are illustrative; the demo shows whatever the satellite says that day.
1. **Map tab.** "Este es un lote de trigo de 100 hectáreas cerca de Pergamino." Draw it (or load the saved GeoJSON). DORA shows 100.2 ha and the region.
2. **Button "Ver cómo viene el lote".** The NDVI map appears over the field: green, yellow, red. "Esto es Sentinel-2, el satélite europeo, gratis: pasa cada 2 a 5 días. La imagen es del 2 de octubre."
3. **Chat:** "¿Cómo viene el trigo?" DORA: "Está 16 % menos verde que lo normal para esta fecha en este lote (comparé con 2021 a 2025). Hay 12 hectáreas flojas, al norte. Si uso esa diferencia, el rinde esperado baja de 3,8 a 3,2 t/ha. ¿Rehago el plan con 3,2?" Point at the "verificado" badge: every number came from the satellite or from the engine.
4. "Sí." DORA re-plans: the sales schedule, the storage and the credit move; "el valor presente baja X USD y necesitás Y USD más de crédito en marzo".
5. Close: "La foto de la factura le dice a DORA cuánto gastaste; el satélite le dice cómo viene lo que sembraste. En los dos casos el número lo mide una herramienta y el verificador lo controla; el modelo de lenguaje solo explica."
Fallback without internet: the cached reading answers the same; say "esta lectura la bajé esta mañana".

## 8. Tests (`tests/test_spec46.py`, no network, no LLM, `DORA_OFFLINE=1`, fixtures in `tests/fixtures/sentinel2/`)
Fixtures: small synthetic arrays (red, NIR, SCL) with known NDVI written as GeoTIFFs in `tmp_path` by the test (rasterio) or as `.npy` + a fake transform, plus recorded STAC search JSON (trimmed) from the prototype. No real farmer data.
1. **NDVI arithmetic:** a 20 × 20 field with red 0.05 / NIR 0.45 → NDVI 0.80 exactly; a half-bare field → median and weak share as computed by hand.
2. **Clouds:** SCL with 40 % cloud and shadow → that scene is skipped and the older 100 % clear one is used; `scenes_considered` lists both with their clear share. All scenes below threshold → `status: "no_clear_scene"`, no NDVI, the message.
3. **Reflectance rule:** the same DNs with `boa_offset_applied: true` → reflectance = DN × 1e-4 (NDVI of the prototype's case stays ≤ 1); with `boa_offset_applied` missing and baseline `05.13` → offset −0.1 applied; baseline `03.01` → no offset.
4. **Duplicates:** `_0_L2A` and `_1_L2A` of the same date → only `_1` is read.
5. **Field mask:** a polygon covering half the window → only those pixels count; the one-pixel erosion removes the border (count checked); SCL water inside the field → `water_share_pct`.
6. **Normal and anomaly:** five fake years with medians 0.71, 0.64, 0.70, 0.69, 0.73 → normal 0.70; now 0.588 → anomaly −16.0 %. Two usable years → `normal: null`, no proposal. `same_crop_years=[2022, 2024]` → only those two, then `normal: null` with the reason (fewer than 3).
7. **Yield proposal:** wheat in pampas_core on 2/10 with base 3.8 and ratio 0.841 → 3.2; ratio 0.3 → clipped to 0.5 → 1.9; soybean on 2/10 (outside its window) → no proposal and the note; base from the farmer's `yields.wheat = 4.2` → 3.5.
8. **Re-plan:** `replan=True, yield_t_ha=3.2` → `before`/`after` equal to `_replan_with_yields` on the same scenario, sown hectares unchanged, NPV lower; the reading comes from the cache (the fake reader is called 0 times on the second call).
9. **`assess_field_image` unchanged:** run `tests/test_field_image.py` (must pass untouched) and compare one full output before/after the helper move.
10. **Errors the agent can act on:** no field and no coordinates; a self-intersecting polygon; 0.5 ha; 8,000 ha; unknown crop; `DORA_OFFLINE=1` with no cache; rasterio missing (monkeypatch the import).
11. **Verifier, dates:** with the tool output in the results, "La imagen es del 2 de octubre de 2026, de hace 36 días; está 16 % menos verde que lo normal" → no unsupported number; "del 5 de octubre" → 5 flagged.
12. **Verifier, area from the map:** `evaluate_season` with `area_ha=100.2` after a `field_from_map` result of 100.2 and no area in the farmer's words → no `area_ha` problem; with 120 → flagged.
13. **Agent (mocked model):** a turn where the model calls `field_ndvi` then answers with the proposal as a question passes the verifier; the overlay path reaches the app's chat output.
14. **Tools and MCP:** `field_ndvi` in `test_tools.py`'s list and through `run_tool`; in the MCP tool list (update `test_spec40.py`'s count); an MCP call with fixtures returns the PNG resource and `provenance`.
15. After the suite, `git status --porcelain dora/data observatory` is empty.

Then the full suite (`python -m pytest -q`), last line pasted in the handoff (0 failed).

**Live check (network, no cost; paste real output in the handoff):** the prototype's square (lon −61.00, lat −33.90, ±0.005°) on `date="2026-10-05"` → scene 2/10, clear 100 %, NDVI near 0.58 (the prototype's value; a different number means the mask or the reflectance rule differs: explain it). Time of the first and the cached call.

## 9. Future scope (write in the handoff what it would take)
- **Calibrating the rule** (research line, an experiment of its own): NDVI of many fields per partido against MAGyP's yields per department and season (Estimaciones Agrícolas), to replace "now ÷ normal, clipped" with a fitted relation per crop and stage, with its error. Until then the rule stays labelled as a rule.
- **Field potential before sowing:** the field's NDVI in past seasons against the region's, as a hint for the yield to plan with.
- **Copernicus fallback** (Sentinel Hub Statistical API) if Earth Search fails; needs an account, so only if Guillermo agrees.
- **Sentinel-1 radar** to see through clouds (flooding, emergence), and **historic flooding** with the SCL water class, joining SPEC-18.

## Handoff (`docs/handoff/spec-46-satellite-ndvi.md`)
What changed; the live check output (real); the cached-call time; the overlay PNG of the prototype field; test output and the full-suite line; the list of anything that behaved differently from this spec (Earth Search changes metadata without notice: say exactly what you saw). Do not mark anything as passed unless its output proves it.
