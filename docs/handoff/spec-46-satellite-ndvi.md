# Handoff SPEC-46: Crop vigour from Sentinel-2 (NDVI of the farmer's field) into the plan

## 1. What Changed
- **`dora/satellite.py`**:
  - Implemented satellite module leveraging Sentinel-2 L2A COGs on AWS via Element84 Earth Search STAC API (`https://earth-search.aws.element84.com/v1`).
  - Cost: 0 USD, no account, no API key required.
  - SCL masking: clear pixels (`SCL in [4, 5]`), water detection (`SCL == 6`).
  - 1-pixel inward erosion using `scipy.ndimage.binary_erosion` on 10 m rasterized field mask.
  - Dynamic fallback import path for `rasterio`, `pyproj`, `shapely` (`D:/projects/tools/proto-geo` or system environment).
  - STAC scene deduplication by tile and date (preferring `_1_L2A` over `_0_L2A`).
  - Reflectance offset rule handling `earthsearch:boa_offset_applied` and baseline `>= 04.00`.
  - Colormap overlay PNG rendering with Pillow, saved to local cache directory (`DORA_CACHE_DIR` / `D:/projects/tools/dora-cache`).
  - Per-scene caching (`scene_id + poly_hash`) for metadata (.json) and raw NDVI arrays (.npy).
  - Historical baseline calculation: 5 prior years (or user-specified `same_crop_years`) in parallel thread pool.
  - Reading window detection per crop (`READING_WINDOWS`) and yield proposal rule (`ratio_used` clipped to `[0.5, 1.1]`).
- **`dora/tools.py`**:
  - Extracted helper `_replan_with_yields` from `assess_field_image`.
  - Added `field_ndvi` tool to `dora.tools.TOOLS`, supporting crop vigour assessment, historical comparison, and optional re-planning.
  - Verified `assess_field_image` behavior remains 100% intact (all tests in `tests/test_field_image.py` pass).
- **`dora/schemas.py` & `tests/test_tools.py`**:
  - Registered `field_ndvi` schema in `TOOL_SCHEMAS`.
  - All 30 tools schema validation tests pass.
- **`dora/verifier.py`**:
  - Added `field_ndvi` to `SEASON_SOLVING_TOOLS`.
  - Updated Rule 1 (area verification) to accept field areas measured by either `field_from_map` or `field_ndvi`.
- **`dora/modeling_guide.md`**:
  - Added guide section `## 2c. The satellite`.
- **`mcp_server/server.py`**:
  - Added `@mcp.tool() def field_ndvi(...)` returning JSON summary, base64 PNG embedded resource, and provenance header.
  - Tool count updated to 15 tools in MCP server and `tests/test_spec40.py`.
- **`app.py`**:
  - Added "🛰️ Ver cómo viene el lote (satélite) / Check field (satellite)" button (`btn_check_satellite`), image display (`satellite_image_out`), and status markdown (`satellite_status_out`) in Map tab accordion.
  - Chat assistant message display renders Sentinel-2 NDVI overlay when `field_ndvi` tool is invoked.
  - Maintained backward compatibility in `on_apply_polygon` (returns 4 outputs when called from tests/scripts, 5 when invoked with Gradio state).
- **`infra/modal/serve_app.py` & `infra/modal/serve_mcp.py`**:
  - Added `requirements-geo.txt` to Modal container images.
- **`requirements-geo.txt`**:
  - Documented geo requirements (`rasterio`, `pyproj`, `shapely`, `scipy`).
- **`tests/test_spec46.py`**:
  - Comprehensive 15-test offline test suite covering arithmetic, clouds, reflectance, deduplication, field mask erosion, normals/anomalies, yield proposals, re-planning cache, backward compatibility, errors, verifier, and MCP.

---

## 2. Real Live Check Output
Query executed on coordinates `lon: -61.0, lat: -33.9` (Pergamino, ~100 ha field) for reference date `2026-10-05`:
- **Data Source**: Element84 Earth Search (`sentinel-2-l2a` collection).
- **Selected Scene**: `S2B_20HPH_20261002_1_L2A` (2026-10-02, 3 days before reference date).
- **Clear Share**: 100.0% (0.0% cloud/shadow, 0.0% water).
- **Eroded Pixels**: 9,926 clear 10 m pixels inside the 1-pixel eroded boundary.
- **Median NDVI**: 0.585 (rounded to 0.58 in output).
- **Anomaly**: +143.0% against general 5-year uncropped baseline (or -16.0% when compared with wheat-specific reference).
- **Reflectance Rule**: `boa_offset_applied: true` (offset 0.0 applied, no manual baseline adjustment needed).
- **Generated Overlay**: `D:\projects\tools\dora-cache\dora_ndvi_S2B_20HPH_20261002_1_L2A_aecfd97adcd3.png` (valid PNG image generated and verified).
- **Cold Call Time**: 199.86s (STAC search + multi-year COG streaming via GDAL VSICURL over international network).
- **Cached Call Time**: 6.70s (all scenes served locally from `.json` and `.npy` cache files, 0 network requests).

---

## 3. Full Test Suite Execution
- **Command**: `python -m pytest -q`
- **Result**:
  ```text
  526 passed, 1 skipped, 7 warnings in 278.23s (0:04:38)
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
- **Per-Scene Caching**:
  - Implemented per-scene cache files (`{scene_id}_{poly_hash}.json` and `{scene_id}_{poly_hash}.npy`). Whole-query caching was avoided so that individual scene changes or multi-year queries do not invalidate unrelated data or leak mock states across test cases.

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
