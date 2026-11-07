# SPEC-47: drone mission over the field (flown in a simulator) and what the photos show

**Status:** ready (7/11), approved by Guillermo. (Renumbered 7/11: the cattle-count evaluation is **E13**; E12 is the "LLM mechanic" pilot, `docs/investigacion/2026-11-07-mecanico-de-llm.md` on branch `claude/keen-wilson-695e01`.) Implement **after SPEC-45 is committed**, in **`D:\projects\dora-main`**, on branch `spec-47-drone-mission` created from `spec-45-spreadsheet-v2` (order decided 7/11: 46, then 45, then 47; all touch `tools.py`, `schemas.py`, `app.py` and the MCP server; stacking avoids conflicts). Do not merge, do not push. Commit with messages starting `SPEC-47 implementation:`; write the handoff and Claude reviews. **Do not redeploy `serve_app.py` or `serve_mcp.py` before 10/11.** No paid service. The SAM 3.1 calls of section 5 use Meta's API credits: **ask Guillermo before the live evaluation** (section 8) and say how many calls it needs.

Touch only: new `dora/drone.py` (mission geometry and file formats), new `dora/drone_vision.py` (counting and green cover), `dora/field_image.py` (one concept list and a function that returns instances, no change to `measure_damage`), `dora/tools.py` (two tools), `dora/schemas.py`, `dora/verifier.py` (one line), `dora/modeling_guide.md` (one section), `app.py` (the mission on the map, downloads, the photo overlay), `mcp_server/server.py` (two tools), `tests/test_tools.py` and `tests/test_spec40.py` (tool lists only), new `infra/sitl/` (simulator harness), new `eval/e13_drone/` (dataset subset script and evaluation), new `tests/test_spec47.py`, new `tests/test_spec47_sitl.py`, `requirements-geo.txt` (`pymavlink`), `docs/licenses/` (dataset attribution), and the handoff.

**Why.** A drone sees what the satellite cannot: individual cows, the state of the grass in a paddock, a patch of the crop at 2 cm per pixel. Two things keep farmers from using one: planning the flight (lines, height, overlap, batteries) and turning hundreds of photos into a number. DORA can do both, and the number goes into the plan like any other measurement: the herd the drone counted becomes `cow_herd_heads` (SPEC-30) after the farmer confirms it. We prove the flight in a free simulator, without a drone, and analyse public drone photos; a real or toy drone is a later choice (section 9).

## 1. Simulator: ArduPilot SITL (ArduCopter), native on Windows
- **PX4 SITL** needs Linux (WSL2 or Docker); this machine has neither (checked 7/11). **ArduPilot SITL** ships a Windows build: the same files Mission Planner downloads, at `https://firmware.ardupilot.org/Tools/MissionPlanner/sitl/CopterStable/` (`ArduCopter.elf`, which is a Windows PE executable despite the name, plus the Cygwin DLLs). Claude downloaded them on 7/11 to `D:\projects\tools\sitl\copter\` (11 MB + DLLs, `git.txt` has the commit) **but did not run them** (not allowed in its session). Antigravity runs them; if Windows Defender or SmartScreen asks, Guillermo approves.
- **Viewer for the demo:** Mission Planner, portable zip (`https://firmware.ardupilot.org/Tools/MissionPlanner/MissionPlanner-latest.zip`, 116 MB) unzipped to `D:\projects\tools\MissionPlanner\` (nothing installed on C:). Its Simulation tab can also start SITL by itself. QGroundControl reads the same `.plan` and is an alternative viewer; not needed.
- The format the simulator flies is MAVLink, so a mission that works in SITL is the same file a real ArduPilot or PX4 drone loads. DJI drones use their own format (KMZ/WPML) and no simulator we can run; out of v1 (section 9).

## 2. The mission tool: `plan_drone_mission`
```python
plan_drone_mission(
    field: dict | list,                    # GeoJSON Polygon/Feature/ring, as field_from_map
    purpose: str = "count_cattle",         # "count_cattle", "pasture", "crop_scouting"
    altitude_m: float | None = None,       # above take-off; default by purpose (table below); max 120
    camera: str = "mavic3e_wide",          # key of CAMERAS in drone.py
    speed_m_s: float = 10.0,               # 2 to 15
    front_overlap: float | None = None,    # default by purpose
    side_overlap: float | None = None,
    battery_min: float = 20.0,             # usable minutes per battery, after the reserve
    home: dict | None = None,              # {"lat", "lon"}; default: the polygon vertex nearest the centroid
    lang: str | None = None,
) -> dict
```
| purpose | altitude | front / side overlap | why |
|---|---|---|---|
| `count_cattle` | 60 m | 0.20 / 0.20 | low overlap so few cows appear twice; at 60 m a cow is ~100 px long |
| `pasture` | 80 m | 0.30 / 0.30 | a sample of the paddock, not a map |
| `crop_scouting` | 60 m | 0.30 / 0.30 | same; a stitched orthomosaic (0.75 / 0.70) is future scope |

`CAMERAS` (in `drone.py`, values checked against the maker's spec sheet and cited in a comment; Antigravity confirms them): `mavic3e_wide` sensor 17.3 × 13.0 mm, focal 12.29 mm, 5280 × 3956 px; `mavic3m_rgb` same sensor; `generic_1in` 13.2 × 8.8 mm, 8.8 mm, 5472 × 3648 px (Phantom 4 class). Pointing straight down.

**Geometry** (pure Python, like `dora/geo.py`; no shapely):
1. Project the polygon to local metres (equirectangular around the centroid; error below 0.1 % for fields under 10 km across; a test checks the area against `polygon_area_ha` within 0.5 %).
2. Footprint: width = altitude × sensor_w / focal, height = altitude × sensor_h / focal. GSD (cm/px) = 100 × altitude × sensor_w / (focal × image_w_px).
3. Line spacing = width × (1 − side_overlap); photo interval = height × (1 − front_overlap).
4. Sweep direction: try every heading from 0° to 175° in 5° steps and keep the one with the fewest lines (ties: shortest total path). Lines start half a spacing inside the edge. Clip each line to the polygon with scanline intersections; a concave field gives several segments per line, each flown as its own leg. Order legs boustrophedon (alternate direction), next leg = nearest end.
5. Photos per leg = floor(leg length / interval) + 1, evenly spaced, both ends included.
6. Time = path length (legs + transits, including home → first and last → home) / speed + 6 s per turn + climb and descent at 3 m/s.
7. **Sorties:** if the time exceeds `battery_min`, split the legs in order into sorties that each fit (each starts and ends at home). One file set per sortie.
8. **Coverage check** (inside the tool, not only in tests): sample a 5 m grid of points in the polygon; share covered by at least one photo footprint ≥ 0.99, else raise a `ScenarioError` naming the gap (a bug, never a farmer error).

**Files** (written to a temp dir; paths in the output):
- **QGroundControl `.plan`** (JSON): `fileType: "Plan"`, `version: 1`, `groundStation: "QGroundControl"`, `mission: {version: 2, firmwareType: 3 (ArduPilot), vehicleType: 2 (quadrotor), cruiseSpeed, hoverSpeed, plannedHomePosition: [lat, lon, 0], items: [...]}`, `geoFence: {circles: [], polygons: [{inclusion: true, polygon: <field buffered by 30 m>, version: 1}], version: 2}`, `rallyPoints: {points: [], version: 2}`. Items are `SimpleItem` with `frame: 3` (relative altitude), `autoContinue: true`, consecutive `doJumpId`: `MAV_CMD_NAV_TAKEOFF` (22) to the altitude, `MAV_CMD_DO_CHANGE_SPEED` (178), then per leg `MAV_CMD_NAV_WAYPOINT` (16) at the leg start, `MAV_CMD_DO_SET_CAM_TRIGG_DIST` (206) = interval, waypoint at the leg end, `DO_SET_CAM_TRIGG_DIST` = 0; finally `MAV_CMD_NAV_RETURN_TO_LAUNCH` (20).
- **`.waypoints`** (QGC WPL 110 text, what Mission Planner loads): the same items, home as item 0. Must load with `pymavlink.mavwp.MAVWPLoader().load(path)` and give the same item count.
- **`.kml`** for Google Earth: the field, the flight path and the photo points.
- **`path_geojson`** inline in the output (LineString per sortie, Points for photos) for the app's map.

**Output:**
```json
{"purpose": "count_cattle", "field_ha": 100.2, "altitude_m": 60, "gsd_cm": 1.6,
 "footprint_m": [84.5, 63.5], "line_spacing_m": 67.6, "photo_interval_m": 50.8,
 "heading_deg": 0, "legs": 15, "photos": 300, "path_km": 16.1, "flight_min": 28.9,
 "sorties": 2, "sortie_min": [19.5, 9.4], "coverage_pct": 99.8,
 "files": {"plan": ["...sortie1.plan", "...sortie2.plan"], "waypoints": [...], "kml": "..."},
 "path_geojson": {...},
 "safety_note": "Es un borrador de misión para un piloto habilitado. DORA no controla drones reales: revisá la zona (ANAC), el clima y los obstáculos antes de volar.",
 "checks": {"inside_fence": true, "altitude_ok": true, "coverage_ok": true}}
```
(The numbers are the hand calculation for a 1 km × 1 km square; tests compute them from the formulas, not from this example.) Every number in the output may appear in the answer. Above 120 m → `ScenarioError` "120 m es el techo habitual para drones chicos (en Argentina lo fija ANAC); confirmá la norma vigente". Fields above 2,000 ha → error "más de un día de vuelo: dividí el campo".

## 3. Simulator harness (`infra/sitl/`, not part of the app)
`infra/sitl/fly_mission.py --waypoints <file> --home lat,lon,alt,heading [--speedup 5] [--watch-port 5762]`:
1. Starts `ArduCopter.elf` from `DORA_SITL_DIR` (`D:\projects\tools\sitl\copter`) with `--model quad --home ... --speedup ... -w --defaults copter.parm` (the default parameter file from the ArduPilot repository at the commit in `git.txt`, downloaded once into the same folder), and a second TCP port so Mission Planner can watch while the script flies (`--serial1 tcp:...`; confirm the exact flag and port in the handoff).
2. Connects with `pymavlink` (`tcp:127.0.0.1:5760`), waits for the heartbeat and a 3D GPS fix and EKF ready.
3. Uploads the mission with the MAVLink mission protocol (`MISSION_COUNT`, answers `MISSION_REQUEST_INT` with `MISSION_ITEM_INT`), reads it back and compares item by item.
4. GUIDED, arm, AUTO, `MAV_CMD_MISSION_START`. Records `GLOBAL_POSITION_INT` (lat, lon, relative alt, time) at 4 Hz and `CAMERA_FEEDBACK` if the simulated camera sends it, until disarmed after RTL. Timeout = 3 × the planned sortie time / speedup.
5. Writes `track.geojson` and a report JSON: items uploaded = read back, max cross-track distance from the planned legs (m), share of the track inside the geofence, simulated flight time vs `sortie_min`, camera triggers (from `CAMERA_FEEDBACK`, or computed from the track when absent; say which).
Pass criteria (test 14): read back identical, max cross-track ≤ 5 m on the legs, 100 % inside the fence, flight time within 25 % of the plan.

## 4. Photos: real ones from the farmer, or a public dataset for the simulated flight
SITL flies but takes no pictures. For the demo and the evaluation, the "photos of the flight" come from **public drone datasets**, and the demo says so on screen ("fotos de ejemplo de un dataset público, no de este lote").
- **Cattle:** *Drone images and their annotations of grazing cows*, Institut de l'Élevage (Helary, Lebreton et al.), Zenodo `10.5281/zenodo.11048412` (v2, April 2024), **CC-BY 4.0** (checked 7/11 on the Zenodo API), 1,385 images from DJI Mavic 3 Enterprise / Thermal with 4,941 cow bounding boxes. The zip is 16.6 GB, but Zenodo serves byte ranges (checked: HTTP 206): `eval/e13_drone/fetch_subset.py` reads the zip's central directory and extracts only ~40 images and their annotations (Python `zipfile` over a ranged-HTTP file object, or the `remotezip` package) into `D:\projects\tools\datasets\cattle_zenodo_11048412\` (outside the repo). Attribution in `docs/licenses/DATASETS.md`.
- **Crops:** *A Multispectral UAV Imagery Dataset of Wheat, Soybean and Barley Crops in East Kazakhstan* (MDPI *Data* 8(5):88, 2023), on Zenodo, reported CC-BY 4.0 with RGB orthomosaics per crop. **Antigravity confirms the license and the RGB content on the Zenodo record before using it**; if it does not hold, pick another CC-BY RGB crop dataset and write down which and why.
- The tool also accepts the farmer's own photos sent in the chat (as `assess_field_image` does), so a real drone works the day there is one.
- No dataset image enters the repository except up to 6 small, downscaled test fixtures with their attribution (CC-BY allows it).

## 5. The analysis tool: `analyze_drone_photos`
```python
analyze_drone_photos(
    purpose: str,                      # "count_cattle", "pasture", "crop_scouting"
    images: list[int] | None = None,   # positions of the farmer's photos; default all
    scenario: dict | None = None,      # for count_cattle: compares with cow_herd_heads
    altitude_m: float | None = None,   # if known (EXIF/XMP or the mission), for areas
    lang: str | None = None,
    _images: list[str] | None = None,  # IMAGE_TOOLS: the agent passes the photos
    _segmenter=None,
) -> dict
```
Add it to `IMAGE_TOOLS`. For the simulated demo the app passes the dataset subset as `_images` (the "Fotos del vuelo simulado" button, section 6).

**count_cattle.** SAM 3.1 with concepts `["cow", "cattle"]` (new `CONCEPTS["cattle"]` in `field_image.py`, next to `DAMAGE_CONCEPTS`). New function `find_objects(image, concepts, segmenter)` returns the instances (box, score, mask area) from `parse_image_output`. Instances of the two concepts are the same cow when their boxes overlap with IoU ≥ 0.5: count once. Drop instances with score < 0.5 and boxes smaller than 0.2 × or larger than 5 × the median box (calves are fine; a shed is not). Count per photo, total, and an overlay PNG per photo with numbered boxes.
- **Double counting across photos:** when every photo has GPS position and relative altitude (DJI writes them in EXIF/XMP), keep only the cows whose box centre falls in the photo's own cell (the interval × spacing rectangle around its trigger point, from the mission); otherwise sum per photo and add `overlap_warning` "Si las fotos se superponen, una vaca puede contarse dos veces; con la misión de DORA (20 % de superposición) el error es chico pero existe." Cows move while the drone flies: say it once in the guide.
- With `scenario.cow_herd_heads`: `difference_heads` = counted − declared. The count enters the plan only after the farmer confirms: the agent asks "Conté 377 vacas. ¿Uso 377 en el plan en vez de 400?"; on yes it calls `evaluate_season` with `cow_herd_heads: 377`, which the verifier accepts because 377 is in this tool's result.

**pasture / crop_scouting.** No model: **green cover** per pixel with the ExG − ExR index on chromatic coordinates (Meyer and Neto, 2008: green if 3g − 2.4r − b > 0 with r, g, b = R, G, B divided by their sum), which needs no threshold to tune. Per photo: green cover %, bare or dry %, and the mean VARI ((G − R) / (G + R − B)) as a second number. Average over photos, and the photos with the lowest cover listed first. Overlay: non-green pixels tinted red. v1 does not turn grass cover into stocking rate or yield: the output says "es una medición de cobertura verde, no de kilos de pasto"; that conversion is future scope.

Output (count_cattle):
```json
{"purpose": "count_cattle", "photos": 12, "cows_total": 377, "per_photo": [31, 28, ...],
 "declared_heads": 400, "difference_heads": -23, "dedup": "per-photo cell" | "none",
 "overlap_warning": "...", "overlay_paths": [...], "model": "SAM 3.1 (Meta) finds each cow; DORA counts them",
 "source": "fotos del productor" | "dataset público (Institut de l'Élevage, CC-BY 4.0): fotos de ejemplo, no de este lote"}
```

## 6. Verifier, guide, app, MCP
- **Verifier:** add `analyze_drone_photos` to `SEASON_SOLVING_TOOLS` only if it ever re-plans; v1 does not, so no change there. `plan_drone_mission` returns `field_ha`: include it in the measured-area rule of SPEC-46 section 5 (one line). Nothing else: every mission and count number is a tool result.
- **Guide** (`modeling_guide.md`, "2d. Drone"): when the farmer asks to fly a drone, count cattle, check a paddock or scout a crop, call `plan_drone_mission` with the field polygon and say lines, photos, minutes, batteries and GSD in plain words, plus the safety note; offer the files. When he sends drone photos, call `analyze_drone_photos`; give the count as a measurement ("SAM contó"), mention the overlap warning, and ask before using the count in the plan. Never say the drone "will fly": DORA writes the mission; a pilot flies it.
- **App, Map tab:** after `plan_drone_mission`, draw `path_geojson` over the field (Leaflet polyline and photo dots, one colour per sortie) and offer three downloads: "Misión QGroundControl (.plan)", "Misión Mission Planner (.waypoints)", "Google Earth (.kml)". A button "Fotos del vuelo simulado (dataset público)" runs `analyze_drone_photos` on the local subset (only when `DORA_DRONE_DATASET_DIR` exists; hidden otherwise, e.g. on Modal) and shows the overlays in a gallery.
- **MCP:** `plan_drone_mission(field, purpose, ...)` returns the output with the `.plan` and `.waypoints` as embedded text resources; `analyze_drone_photos(purpose, images_base64: list[str], scenario=None)` (max 20 photos, 10 MB each) with `provenance`. Both open to anonymous callers; `analyze_drone_photos` spends SAM credits, so anonymous callers get at most 3 photos per call and the daily anonymous cap of SPEC-44 applies.

## 7. Demo script (Telegraph; Bolsa de Comercio de Rosario)
Prepare: Mission Planner portable and SITL in `D:\projects\tools\`, the dataset subset downloaded, a pasture polygon saved (any public paddock; the photos are the dataset's anyway), the SITL flight recorded once with `infra/video/record.py` as a fallback clip.
1. **Map tab:** "Este es un potrero de 100 hectáreas con vacas." Chat: "Quiero contar las vacas con un dron." DORA draws the mission on the map: "15 pasadas a 60 metros, 300 fotos, 29 minutos en dos baterías; cada píxel es 1,6 cm." Download the `.waypoints`.
2. **Mission Planner** (next window), connected to SITL: load the file, Write, Arm, Auto. The simulated drone takes off and flies the lawnmower over the satellite map of that same potrero (speedup ×5). "Este archivo es el mismo que carga un dron real con ArduPilot."
3. **Back in DORA:** "Fotos del vuelo simulado". "Como el simulador no saca fotos, uso fotos reales de vacas tomadas con dron, de un dataset público francés." The gallery shows the numbered boxes; DORA: "SAM contó 377 vacas en 12 fotos. Vos me dijiste 400: faltan 23. ¿Uso 377 en el plan?" "Sí" → the plan moves (herd value, calves to sell in March), every number verified.
4. Close: "Satélite para todo el campo cada pocos días, dron para el detalle; en los dos, el número lo mide una herramienta y DORA lo controla antes de decírtelo."
Fallback: the recorded SITL clip and the cached SAM results (`analyze_drone_photos` caches per image hash in `DORA_CACHE_DIR`, so the demo does not spend credits twice).

## 8. Tests
**`tests/test_spec47.py`** (no network, no LLM, no simulator, `DORA_OFFLINE=1`, fake segmenter):
1. **Projection:** local-metre area of three polygons (square, L-shaped, a real-looking 7-vertex field) within 0.5 % of `polygon_area_ha`.
2. **Footprint and GSD** for `mavic3e_wide` at 60 m: width 84.5 m, height 63.5 m, GSD 1.6 cm (hand calculation in the test).
3. **Lines:** a 1 km square at 60 m, side overlap 0.2 → spacing 67.6 m, 15 legs, first leg 33.8 m inside the edge; the 5° search picks 0° or 90°.
4. **Concave field:** an L-shaped field gives split legs, none crossing outside the polygon (every leg segment's midpoint inside), and coverage ≥ 99 %.
5. **Photos and time:** photos per leg and total, path length and flight time equal the formulas of section 2; sorties split when `battery_min=10`, each sortie under 10 min, all legs flown exactly once.
6. **Coverage:** the 5 m grid check passes for the three polygons and every purpose; forcing spacing larger than the footprint (monkeypatch) raises the error.
7. **Files:** `.plan` parses as JSON with the fields of section 2, item commands in the order TAKEOFF, CHANGE_SPEED, (WAYPOINT, CAM_TRIGG_DIST, WAYPOINT, CAM_TRIGG_DIST=0) × legs, RTL; `doJumpId` consecutive; the fence polygon closed. `.waypoints` loads with `MAVWPLoader` with the same count; `.kml` parses with `xml.etree`.
8. **Limits:** altitude 150 → error with the message; 3,000 ha → error; speed 20 → error; self-intersecting polygon → error.
9. **Counting:** fake SAM output with 5 cows as "cow" and 4 of them again as "cattle" (IoU 0.8) plus one shed-sized box → 5 cows. Score 0.3 dropped.
10. **Dedup by cell:** two overlapping photos with GPS, a cow in the overlap appears in both → counted once; without GPS → counted twice and `overlap_warning` present.
11. **Green cover:** a synthetic image half green (0, 160, 0) half soil (150, 110, 70) → 50.0 % green; VARI of the green half computed by hand.
12. **Into the plan:** with `cow_herd_heads=400` and 377 counted → `difference_heads=-23`; the verifier accepts "Conté 377 vacas, 23 menos de las 400 que me dijiste" and `evaluate_season` with `cow_herd_heads: 377` passes `check_scenario`.
13. **Tools and MCP:** both tools in `test_tools.py`'s list and through `run_tool` (images passed as for `assess_field_image`); in the MCP list (update `test_spec40.py`'s count); anonymous MCP `analyze_drone_photos` with 4 photos → error asking for a key or fewer photos.
14. After the suite, `git status --porcelain dora/data observatory` is empty.

**`tests/test_spec47_sitl.py`** (marked `sitl`, skipped unless `DORA_SITL_DIR` is set and has `ArduCopter.elf`):
15. Plan the 1 km square near lon −61.00, lat −33.90 with `battery_min=60` (one sortie), fly it with `fly_mission.py --speedup 5`, and check the pass criteria of section 3. Paste the report JSON in the handoff with a screenshot of Mission Planner showing the track.

Then the full suite (`python -m pytest -q`; the SITL test runs only on Guillermo's machine) and paste the last line.

**Evaluation E13 (after asking Guillermo about Meta credits):** `eval/e13_drone/run.py` runs `analyze_drone_photos(count_cattle)` on 30 images of the subset and compares with the dataset's boxes: count error per image, mean absolute error, and how often it is off by more than 10 %. Here the grader knows the true count; in production nothing does, so the result goes in `docs/experimentos/` as the measured error of the tool, and the guide quotes it ("en fotos de prueba SAM se equivocó en X vacas cada 100"). 30 images × 2 concepts = 60 SAM calls; with the cache, a rerun costs 0.

## 9. Optional: a physical demo with a toy drone (Guillermo decides)
A Ryze/DJI **Tello** (about 100 USD, programmable from Python with `djitellopy` over Wi-Fi) has no GPS and a forward camera: it cannot fly a GPS mission. What it can do indoors: fly the same lawnmower scaled to a printed field map on the floor (relative `go x y z speed` commands from the mission's local metres, scale 1:500), with a clip-on mirror to look down, taking photos of toy cows that SAM counts. It is a stage trick, honest if said as such. Not in this spec; if Guillermo buys one, a short SPEC-47b adds `export_tello_script`. Real drones (ArduPilot/PX4 with a companion computer, or DJI with its WPML format and SDK) are later, with a licensed pilot.

## Handoff (`docs/handoff/spec-47-drone-mission.md`)
What changed; the mission of the 1 km square drawn over the map (screenshot); the SITL report and Mission Planner screenshot (or why it did not run, exactly); the dataset subset (which images, size, license check); test output and the full-suite line; the exact steps for the demo of section 7 on Guillermo's machine. Do not mark anything as passed unless its output proves it.
