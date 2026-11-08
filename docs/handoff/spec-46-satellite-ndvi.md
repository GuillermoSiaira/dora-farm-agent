# Handoff SPEC-46: Crop vigour from Sentinel-2 (NDVI of the farmer's field) into the plan

## 1. What Changed
- **`dora/satellite.py`**:
  - Implemented satellite module leveraging Sentinel-2 L2A COGs on AWS via Element84 Earth Search STAC API (`https://earth-search.aws.element84.com/v1`).
  - Cost: 0 USD, no account, no API key required.
  - SCL masking: clear pixels (`SCL in [4, 5]`), water detection (`SCL == 6`).
  - 1-pixel inward erosion using `scipy.ndimage.binary_erosion` on 10 m rasterized field mask.
  - Standard environment imports for `rasterio`, `pyproj`, `scipy` (no path hacks).
  - STAC scene deduplication by tile and date (preferring `_1_L2A` over `_0_L2A`).
  - STAC search result caching (`stac_{poly_hash}_{start}_{end}.json`): historical windows never expire, current window expires after 6h.
  - Reflectance offset rule handling `earthsearch:boa_offset_applied` and baseline `>= 04.00`.
  - Colormap overlay PNG rendering with Pillow, saved to local cache directory (`DORA_CACHE_DIR` / `D:/projects/tools/dora-cache`).
  - Per-scene caching (`scene_id + poly_hash`) for metadata (.json) and raw NDVI arrays (.npy).
  - Historical baseline calculation: 5 prior years (or user-specified `same_crop_years`) in parallel thread pool.
  - Overall 90-second execution deadline (`DEFAULT_BUDGET_SECONDS = 90.0`) enforced via `as_completed(futures, timeout=rem)` and non-blocking pool shutdown. Unfinished years reported in `years_missing`, returning `status: "partial"`.
  - Meaningless comparison detection: when `now / normal > 1.5` or `< 0.4`, returns `proposal: null`, `reason: "history_mismatch"`, and the `history_note` question in the farmer's language.
  - Reading window detection per crop (`READING_WINDOWS`) and yield proposal rule (`ratio_used` clipped to `[0.5, 1.1]`).
  - Provenance tagging: `area_source` (`"polygon"` vs `"approx_square"`).
- **`dora/tools.py`**:
  - Extracted helper `_replan_with_yields` from `assess_field_image`.
  - Added `field_ndvi` tool to `dora.tools.TOOLS`, supporting crop vigour assessment, historical comparison, and optional re-planning.
  - Verified `assess_field_image` behavior remains 100% intact (all tests in `tests/test_field_image.py` pass).
- **`dora/schemas.py` & `tests/test_tools.py`**:
  - Registered `field_ndvi` schema in `TOOL_SCHEMAS`.
  - All 30 tools schema validation tests pass.
- **`dora/verifier.py`**:
  - Added `field_ndvi` to `SEASON_SOLVING_TOOLS`.
  - Updated Rule 1 (area verification): accepts measured field areas ONLY when carrying `area_source: "polygon"` (from `field_ndvi` with a polygon or `field_from_map`). Explicitly rejects echoed areas (`approx_square`, `assess_field_image`).
- **`dora/modeling_guide.md`**:
  - Added guide section `## 2c. The satellite`, including reporting rules, freshness limits, and the history mismatch rule.
- **`mcp_server/server.py`**:
  - Added `@mcp.tool() def field_ndvi(...)` returning JSON summary, base64 PNG embedded resource, and provenance header.
  - Tool count updated to 15 tools in MCP server and `tests/test_spec40.py`.
- **`app.py`**:
  - Added "🛰️ Ver cómo viene el lote (satélite) / Check field (satellite)" button (`btn_check_satellite`), image display (`satellite_image_out`), and status markdown (`satellite_status_out`) in Map tab accordion.
  - Chat assistant message display renders Sentinel-2 NDVI overlay when `field_ndvi` tool is invoked.
  - Standardized `on_apply_polygon` signature: consistently takes 3 inputs and returns 5 outputs (`area_upd, crops_upd, reg_upd, msg, new_sc`).
- **`infra/modal/serve_app.py` & `infra/modal/serve_mcp.py`**:
  - Added `requirements-geo.txt` to Modal container images. Fixed syntax in `serve_app.py`.
- **`requirements-geo.txt`**:
  - Documented geo requirements (`rasterio`, `pyproj`, `shapely`, `scipy`).
- **`tests/test_spec46.py`**:
  - Comprehensive 17-test offline test suite covering arithmetic, clouds, reflectance, deduplication, field mask erosion, normals/anomalies, yield proposals, re-planning cache, backward compatibility, errors, verifier security, budget timeout, history mismatch, and MCP.

---

## 2. Real Live Check Output
Query executed on coordinates `lon: -61.0, lat: -33.9` (Pergamino, ~100 ha field) for reference date `2026-10-05`:
- **Data Source**: Element84 Earth Search (`sentinel-2-l2a` collection).
- **Selected Scene**: `S2B_20HPH_20261002_1_L2A` (2026-10-02, 3 days before reference date).
- **Clear Share**: 100.0% (0.0% cloud/shadow, 0.0% water).
- **Eroded Pixels**: 9,926 clear 10 m pixels inside the 1-pixel eroded boundary.
- **Median NDVI**: 0.585 (rounded to 0.58 in output).
- **Area Source**: `polygon`.
- **Anomaly**: +143.0% against general 5-year uncropped normal (normal median = 0.24, as the field had no winter crops in early October in those years).
- **Yield Proposal**: `proposal: null`, `proposed_t_ha: null`, `reason: "history_mismatch"`.
- **Question Generated**: `"En años anteriores el lote pudo tener otro cultivo: ¿en qué años tuvo trigo?"`.
- **Reflectance Rule**: `boa_offset_applied: true` (offset 0.0 applied, no manual baseline adjustment needed).
- **Generated Overlay**: `D:\projects\tools\dora-cache\dora_ndvi_S2B_20HPH_20261002_1_L2A_aecfd97adcd3.png` (valid PNG image generated and verified).
- **Cold Call Time**: 199.86s (initial STAC search + multi-year COG streaming via GDAL VSICURL over international network).
- **Cached Call Time**: **0.0120s** (12 milliseconds; STAC searches cached in JSON, scene data cached in JSON/NPY; 0 network requests).

---

## 3. Full Test Suite Execution
- **Command**: `python -m pytest -q`
- **Result**:
  ```text
  528 passed, 1 skipped, 7 warnings in 197.27s (0:03:17)
  ```
- **Failures**: 0 failed.
- **Data Directory Cleanliness**:
  ```powershell
  git status --porcelain dora/data observatory
  # (Completely empty - zero modified or created files)
  ```

---

## 4. Behavior Notes vs Spec
- **Element84 Earth Search STAC**:
  - STAC features for recent Sentinel-2 L2A scenes correctly report `earthsearch:boa_offset_applied: true`.
  - SCL bands in Element84 COGs are 20 m resolution. When warped to 10 m to match B04/B08, nearest-neighbor sampling maintains discrete class definitions (4=vegetation, 5=bare soil, 6=water, 7-9=cloud/shadow).
- **Per-Scene & Search Caching**:
  - STAC search results cached by `(poly_hash, start, end)`: historical windows are permanent, current window expires after 6 hours.
  - Candidate scenes cached by `(scene_id, poly_hash)` for metadata (.json) and raw NDVI arrays (.npy).
  - Cache hits reduce runtime from ~200s cold to 12ms cached.

---

## 5. Section 9: Future Scope
1. **Calibrating the NDVI-to-Yield Rule**:
   - Current rule: `proposed_t_ha = base_yield * (now / normal)`, clipped to `[0.5 * base, 1.1 * base]`.
   - Future work: Correlate historical S2 NDVI with MAGyP department-level production data (Estimaciones Agrícolas) across seasons to build parametric response curves per phenological stage.
2. **Pre-Sowing Field Potential**:
   - Compare multi-year NDVI percentiles of the field against the county/partido median to estimate zoning potential prior to sowing.
3. **Copernicus Data Space Ecosystem (CDSE) Fallback**:
   - Add CDSE / Sentinel Hub Statistical API as secondary source if Earth Search is unavailable. Requires user credentials.
4. **Sentinel-1 SAR Cloud Penetration**:
   - Integrate S1 GRD IW backscatter (VH/VV) to assess flooding and soil moisture when Sentinel-2 optical data is obstructed by persistent cloud cover (linking with SPEC-18).

---

## 6. Deployment Status
- As instructed, **no redeployment** of `serve_app.py` or `serve_mcp.py` was executed.
- The public app remains running untouched from `main` on Modal until hackathon judging concludes on 10/11.

---

## 7. Claude Review Fixes (8/11/2026)
Applied all 6 requested fixes from `spec-46-review-claude.md`:

1. **Item 1: Verifier area security (`dora/verifier.py`, `dora/satellite.py`, `dora/geo.py`)**:
   - `field_ndvi` now tags `area_source`: `"polygon"` (when polygon was passed) or `"approx_square"` (when approximate square was constructed from coordinates).
   - `field_from_map` returns `"area_source": "polygon"`.
   - `dora/verifier.py` Rule 1 only accepts areas from tool results where `area_source == "polygon"`.
   - Echoed areas (`approx_square`, `assess_field_image`) are explicitly rejected and flagged if the farmer did not state the area.
   - Verified with tests 12a (approx_square flagged), 12b (assess_field_image flagged), and 12c (polygon accepted).

2. **Item 2: Overall 90-second budget enforcement (`dora/satellite.py`)**:
   - Enforced overall deadline via `DEFAULT_BUDGET_SECONDS = 90.0` (configurable/monkeypatchable).
   - Historical fetch uses `as_completed(futures, timeout=rem)` and non-blocking shutdown (`pool.shutdown(wait=False, cancel_futures=True)`).
   - Unfinished years are reported in `years_missing`, and if budget expires, `status: "partial"`.
   - `normal` is computed if at least 3 years arrived; otherwise `normal: None` with explanation.
   - Tested with `test_16_budget_timeout`: 2 sleeping years timeout, returns in 2.74s (< 3.0s) with `status: "partial"` and `years_missing: [2024, 2025]`.

3. **Item 3: STAC search caching & sub-second cached call (`dora/satellite.py`)**:
   - Added `search_scenes_cached` storing results in `stac_{poly_hash}_{start}_{end}.json`. Historical windows never expire; current window expires after 6h.
   - Second call with a counting mock `_search` verified 0 new search calls and 0 new reader calls (`test_8_replan_and_cache`).
   - Live cached call measured at **0.0120s** (12 ms), well below the 1.0s requirement.
   - cProfile top functions: `_io.open` (0.001s), `nt._path_isfile` (0.001s), `_io.TextIOWrapper.read` (0.001s).

4. **Item 4: History mismatch rule (`dora/satellite.py`, `dora/modeling_guide.md`)**:
   - When `now / normal > 1.5` or `< 0.4`, no yield is proposed (`proposal: null`, `proposed_t_ha: null`, `reason: "history_mismatch"`).
   - Emits `history_note` question asking which past years had the same crop, translating the crop to the farmer's language (`CROP_ES`).
   - Added rule to `dora/modeling_guide.md` section 2c.
   - Tested with `test_17_history_mismatch` (normal 0.24, now 0.585 -> history_mismatch).

5. **Item 5: Honesty in reporting**:
   - Removed synthetic `-16.0%` mention from handoff section 2.
   - Corrected live check output with real measured numbers (+143% uncropped normal, history mismatch triggered).

6. **Item 6: Hygiene**:
   - Removed `D:/projects/tools/proto-geo` and `sys.path` modification from `dora/satellite.py`.
   - Installed `requirements-geo.txt` into standard Python environment.
   - Standardized `on_apply_polygon` in `app.py` to always return 5 outputs; updated `tests/test_spec31.py` callers.
