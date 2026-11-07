"""Crop vigour and NDVI from Sentinel-2 satellite imagery (SPEC-46).

Data source: Element84 Earth Search (STAC v1) over Sentinel-2 L2A COGs on AWS S3.
No account, no API key, zero cost.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import math
import os
import re
import tempfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date as dt_date
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
from scipy.ndimage import binary_erosion

# Dynamic import with fallback to local prototype directory
try:
    import pyproj
    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.warp import transform_geom
except ImportError:
    import sys
    proto = Path("D:/projects/tools/proto-geo")
    if proto.is_dir() and str(proto) not in sys.path:
        sys.path.insert(0, str(proto))
    try:
        import pyproj
        import rasterio
        from rasterio.features import geometry_mask
        from rasterio.warp import transform_geom
    except ImportError:
        rasterio = None
        pyproj = None
        geometry_mask = None
        transform_geom = None

from .geo import (
    parse_geojson_polygon,
    polygon_area_ha,
    region_for_point,
    validate_polygon_coords,
)
from .scenario import ScenarioError, load_region_data

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent

# Reading windows per region and crop (supuesto DORA, a calibrar - SPEC-46)
# ((start_month, start_day), (end_month, end_day))
READING_WINDOWS: dict[str, dict[str, tuple[tuple[int, int], tuple[int, int]]]] = {
    "pampas_core": {
        "wheat": ((9, 15), (11, 10)),
        "corn": ((12, 15), (2, 15)),
        "soybean": ((1, 15), (3, 15)),
        "sunflower": ((12, 1), (1, 31)),
    },
    "southeast_buenos_aires": {
        "wheat": ((9, 15), (11, 10)),
        "corn": ((12, 15), (2, 15)),
        "soybean": ((1, 15), (3, 15)),
        "sunflower": ((12, 1), (1, 31)),
    },
    "iowa": {
        "corn": ((7, 1), (8, 31)),
        "soybean": ((7, 15), (8, 31)),
    },
    "mato_grosso": {
        "soybean": ((11, 15), (1, 15)),
    },
}

CROP_NORMALIZE = {
    "trigo": "wheat",
    "wheat": "wheat",
    "maiz": "corn",
    "maíz": "corn",
    "corn": "corn",
    "soja": "soybean",
    "soybean": "soybean",
    "girasol": "sunflower",
    "sunflower": "sunflower",
    "cebada": "barley",
    "barley": "barley",
    "sorgo": "sorghum",
    "sorghum": "sorghum",
}


def in_reading_window(region: str | None, crop: str, date_str: str) -> bool:
    """Return True if date_str falls within the crop's reading window for that region."""
    if not region or region not in READING_WINDOWS:
        return False
    crop_norm = CROP_NORMALIZE.get(crop.lower(), crop.lower())
    windows = READING_WINDOWS[region]
    if crop_norm not in windows:
        return False

    dt = datetime.fromisoformat(date_str)
    m, d = dt.month, dt.day
    (sm, sd), (em, ed) = windows[crop_norm]

    if (sm, sd) <= (em, ed):
        return (sm, sd) <= (m, d) <= (em, ed)
    else:
        # Crosses year boundary (e.g. Dec 15 to Feb 15)
        return (m, d) >= (sm, sd) or (m, d) <= (em, ed)


def get_cache_dir() -> Path:
    """Return cache directory for satellite data from DORA_CACHE_DIR, or temp dir fallback."""
    cache_dir_str = os.environ.get("DORA_CACHE_DIR")
    if not cache_dir_str:
        env_path = ROOT / ".env"
        if env_path.is_file():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("DORA_CACHE_DIR="):
                        cache_dir_str = line.split("=", 1)[1].strip()
                        break
            except Exception:
                pass
    if cache_dir_str:
        p = Path(cache_dir_str)
        p.mkdir(parents=True, exist_ok=True)
        return p

    p = Path(tempfile.gettempdir()) / "dora-cache"
    p.mkdir(parents=True, exist_ok=True)
    logger.info(f"DORA_CACHE_DIR not set; using temp directory {p}")
    return p


# ---------------------------------------------------------------------------
# Network Seam Functions (Injectable as _search and _reader)
# ---------------------------------------------------------------------------


def search_scenes(
    polygon_geojson: dict,
    start_date: str,
    end_date: str,
    limit: int = 100,
) -> list[dict]:
    """Query Element84 Earth Search STAC v1 for Sentinel-2 L2A scenes."""
    if os.environ.get("DORA_OFFLINE") == "1":
        raise ScenarioError("Sin conexión: no puedo bajar la imagen satelital ahora.")

    url = "https://earth-search.aws.element84.com/v1/search"
    body = {
        "collections": ["sentinel-2-l2a"],
        "intersects": polygon_geojson,
        "datetime": f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
        "limit": limit,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "DORA/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
            return data.get("features", [])
    except Exception as e:
        raise ScenarioError(f"Error consultando Earth Search: {e}") from e


def read_window(
    href: str,
    bounds: tuple[float, float, float, float],
    crs: str,
    out_shape: tuple[int, int] | None = None,
) -> tuple[np.ndarray, Any]:
    """Read bounding box window from a GeoTIFF / Cloud-Optimized GeoTIFF."""
    if rasterio is None:
        raise ScenarioError("Falta instalar requirements-geo.txt (pip install -r requirements-geo.txt)")

    from rasterio.enums import Resampling
    from rasterio.windows import from_bounds

    with rasterio.open(href) as ds:
        w = from_bounds(*bounds, ds.transform).round_offsets().round_lengths()
        tr = ds.window_transform(w)
        if out_shape is not None:
            data = ds.read(1, window=w, boundless=True, out_shape=out_shape, resampling=Resampling.nearest)
        else:
            data = ds.read(1, window=w, boundless=True)
        return data, tr


def deduplicate_scenes(features: list[dict]) -> list[dict]:
    """Group scenes by tile and date, keeping the highest processing number."""
    best_per_group: dict[tuple[str, str], tuple[int, dict]] = {}
    for f in features:
        scene_id = f.get("id", "")
        dt_str = f.get("properties", {}).get("datetime", "")[:10]
        parts = scene_id.split("_")
        tile = parts[1] if len(parts) >= 5 else f.get("properties", {}).get("mgrs:tile_id", scene_id)
        try:
            proc_num = int(parts[3]) if len(parts) >= 5 else 0
        except ValueError:
            proc_num = 0
        date_key = dt_str.replace("-", "") if dt_str else (parts[2] if len(parts) >= 5 else scene_id)
        group_key = (tile, date_key)
        if group_key not in best_per_group or proc_num > best_per_group[group_key][0]:
            best_per_group[group_key] = (proc_num, f)

    deduped = [v[1] for v in best_per_group.values()]
    deduped.sort(key=lambda x: x.get("properties", {}).get("datetime", ""), reverse=True)
    return deduped


def get_reflectance_offset(properties: dict) -> tuple[float, str]:
    """Determine BOA reflectance offset rule according to SPEC-46 section 1."""
    if properties.get("earthsearch:boa_offset_applied") is True:
        return 0.0, "boa_offset_applied"

    baseline = str(properties.get("s2:processing_baseline") or properties.get("processing:version") or "")
    try:
        v = float(baseline)
        if v >= 4.0:
            return -0.1, "baseline_ge_0400"
        else:
            return 0.0, "baseline_lt_0400"
    except (ValueError, TypeError):
        return 0.0, "default_no_offset"


def generate_overlay(
    ndvi: np.ndarray,
    inside_mask: np.ndarray,
    clear_mask: np.ndarray,
    overlay_path: Path | str,
) -> str | None:
    """Generate color-mapped NDVI PNG overlay with grey non-clear pixels and white boundary."""
    try:
        from PIL import Image
    except ImportError:
        return None

    H, W = ndvi.shape
    rgba = np.zeros((H, W, 4), dtype=np.uint8)

    # Non-clear pixels inside field: grey
    non_clear_inside = inside_mask & ~clear_mask
    rgba[non_clear_inside] = [160, 160, 160, 200]

    # Clear pixels: colormap red (0.0) -> yellow (0.5) -> green (1.0)
    vals = np.clip(ndvi[clear_mask], 0.0, 1.0)
    r = np.zeros(len(vals), dtype=np.uint8)
    g = np.zeros(len(vals), dtype=np.uint8)
    b = np.zeros(len(vals), dtype=np.uint8)

    low_idx = vals < 0.5
    t_low = vals[low_idx] / 0.5
    r[low_idx] = (215 + t_low * (254 - 215)).astype(np.uint8)
    g[low_idx] = (48 + t_low * (224 - 48)).astype(np.uint8)
    b[low_idx] = (39 + t_low * (139 - 39)).astype(np.uint8)

    high_idx = ~low_idx
    t_high = (vals[high_idx] - 0.5) / 0.5
    r[high_idx] = (254 + t_high * (26 - 254)).astype(np.uint8)
    g[high_idx] = (224 + t_high * (152 - 224)).astype(np.uint8)
    b[high_idx] = (139 + t_high * (80 - 139)).astype(np.uint8)

    rgba[clear_mask, 0] = r
    rgba[clear_mask, 1] = g
    rgba[clear_mask, 2] = b
    rgba[clear_mask, 3] = 230

    # White border for field boundary
    boundary = inside_mask ^ binary_erosion(inside_mask)
    rgba[boundary] = [255, 255, 255, 255]

    img = Image.fromarray(rgba, mode="RGBA")
    img.save(str(overlay_path), format="PNG")
    return str(overlay_path)


# ---------------------------------------------------------------------------
# Core Scene Processing
# ---------------------------------------------------------------------------


def _process_candidate_scene(
    feat: dict,
    poly_geom: dict,
    field_ha: float,
    cache_dir: Path,
    poly_hash: str,
    reader: Any,
    min_clear_share: float = 0.7,
) -> tuple[dict | None, np.ndarray | None]:
    """Process a single scene candidate. Returns (stats_dict, ndvi_array) or (None, None)."""
    scene_id = feat.get("id", "scene")
    json_path = cache_dir / f"{scene_id}_{poly_hash}.json"
    npy_path = cache_dir / f"{scene_id}_{poly_hash}.npy"

    if json_path.is_file() and npy_path.is_file():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                stats = json.load(f)
            ndvi_arr = np.load(str(npy_path))
            return stats, ndvi_arr
        except Exception:
            pass

    if rasterio is None:
        raise ScenarioError("Falta instalar requirements-geo.txt (pip install -r requirements-geo.txt)")

    properties = feat.get("properties", {})
    assets = feat.get("assets", {})
    epsg = properties.get("proj:code") or f"EPSG:{properties.get('proj:epsg')}"

    # Reproject polygon
    g = transform_geom("EPSG:4326", epsg, poly_geom)
    xs = [p[0] for p in g["coordinates"][0]]
    ys = [p[1] for p in g["coordinates"][0]]
    bounds = (min(xs), min(ys), max(xs), max(ys))

    H10 = max(1, int(round((max(ys) - min(ys)) / 10.0)))
    W10 = max(1, int(round((max(xs) - min(xs)) / 10.0)))

    from rasterio.transform import from_bounds as tr_from_bounds
    tr10 = tr_from_bounds(*bounds, W10, H10)

    # 10 m mask and 1-pixel erosion
    inside = ~geometry_mask([g], (H10, W10), tr10)
    eroded_inside = binary_erosion(inside)
    total_px = int(eroded_inside.sum())
    if total_px == 0:
        return None, None

    # 1. Read SCL first
    scl_href = assets.get("scl", {}).get("href")
    if not scl_href:
        return None, None

    scl_res = reader(scl_href, bounds, epsg, out_shape=(H10, W10))
    scl10 = scl_res[0] if isinstance(scl_res, tuple) else scl_res

    clear_mask = eroded_inside & np.isin(scl10, [4, 5])
    clear_share = clear_mask.sum() / total_px
    clear_share_pct = round(100.0 * clear_share, 1)

    water_pixels = (eroded_inside & (scl10 == 6)).sum()
    water_share_pct = round(100.0 * water_pixels / total_px, 1)

    scene_date = properties.get("datetime", "")[:10]
    dt_val = datetime.fromisoformat(properties.get("datetime", "").replace("Z", "+00:00"))

    if clear_share < min_clear_share:
        return {
            "scene_id": scene_id,
            "scene_date": scene_date,
            "clear_share_pct": clear_share_pct,
            "used": False,
        }, None

    # 2. Scene passed clear threshold: read Red and NIR
    red_href = assets.get("red", {}).get("href")
    nir_href = assets.get("nir", {}).get("href")
    if not red_href or not nir_href:
        return None, None

    red_res = reader(red_href, bounds, epsg, out_shape=(H10, W10))
    red = red_res[0] if isinstance(red_res, tuple) else red_res
    nir_res = reader(nir_href, bounds, epsg, out_shape=(H10, W10))
    nir = nir_res[0] if isinstance(nir_res, tuple) else nir_res

    # Reflectance offset rule
    offset, rule_name = get_reflectance_offset(properties)
    r = red * 1e-4 + offset
    n = nir * 1e-4 + offset
    ndvi = (n - r) / (n + r + 1e-9)

    valid_mask = clear_mask & (red > 0) & (nir > 0)
    pixels_clear = int(valid_mask.sum())
    if pixels_clear < 20:
        return {
            "scene_id": scene_id,
            "scene_date": scene_date,
            "clear_share_pct": clear_share_pct,
            "used": False,
        }, None

    ndvi_vals = ndvi[valid_mask]
    ndvi_med = round(float(np.median(ndvi_vals)), 2)
    ndvi_p10 = round(float(np.percentile(ndvi_vals, 10)), 2)
    ndvi_p90 = round(float(np.percentile(ndvi_vals, 90)), 2)

    weak_thresh = 0.8 * float(np.median(ndvi_vals))
    weak_px = int(np.sum(ndvi_vals < weak_thresh))
    weak_share = weak_px / len(ndvi_vals) if len(ndvi_vals) > 0 else 0.0
    weak_share_pct = round(100.0 * weak_share, 1)
    weak_ha = round(weak_share * field_ha, 1)

    overlay_file = cache_dir / f"dora_ndvi_{scene_id}_{poly_hash}.png"
    overlay_path = generate_overlay(ndvi, inside, valid_mask, overlay_file)

    checks = {
        "ndvi_in_range": bool(np.all((ndvi[valid_mask] >= -1.0) & (ndvi[valid_mask] <= 1.0))),
        "enough_pixels": bool(pixels_clear >= 20),
        "reflectance_rule": rule_name,
    }

    stats = {
        "scene_id": scene_id,
        "scene_date": scene_date,
        "scene_day": dt_val.day,
        "scene_month": dt_val.month,
        "scene_year": dt_val.year,
        "clear_share_pct": clear_share_pct,
        "pixels_clear": pixels_clear,
        "ndvi_median": ndvi_med,
        "ndvi_median_raw": float(np.median(ndvi_vals)),
        "ndvi_p10": ndvi_p10,
        "ndvi_p90": ndvi_p90,
        "weak_share_pct": weak_share_pct,
        "weak_ha": weak_ha,
        "water_share_pct": water_share_pct,
        "overlay_path": overlay_path,
        "checks": checks,
        "used": True,
    }

    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(stats, f)
        np.save(str(npy_path), ndvi)
    except Exception as e:
        logger.warning(f"Failed to write cache for {scene_id}: {e}")

    return stats, ndvi


# ---------------------------------------------------------------------------
# Main Public Function: field_ndvi
# ---------------------------------------------------------------------------


def field_ndvi(
    field: dict | list | None = None,
    scenario: dict | None = None,
    crop: str | None = None,
    date: str | None = None,
    max_age_days: int = 30,
    min_clear_share: float = 0.7,
    same_crop_years: list[int] | None = None,
    replan: bool = False,
    yield_t_ha: float | None = None,
    lang: str | None = None,
    _search=None,
    _reader=None,
) -> dict:
    """Measure crop vigour and NDVI from Sentinel-2 satellite imagery (SPEC-46)."""
    search_fn = _search or search_scenes
    reader_fn = _reader or read_window

    clean_lang = (lang or (scenario.get("lang") if isinstance(scenario, dict) else None) or "es").strip().lower()
    is_es = clean_lang.startswith("es")

    if rasterio is None:
        raise ScenarioError("Falta instalar requirements-geo.txt (pip install -r requirements-geo.txt)")

    # 1. Parse and validate field geometry
    field_note = None
    if field is None:
        if isinstance(scenario, dict) and "lat" in scenario and "lon" in scenario:
            field = {"lat": float(scenario["lat"]), "lon": float(scenario["lon"])}
        else:
            raise ScenarioError("No se pasaron coordenadas ni polígono del lote." if is_es else "No field polygon or coordinates provided.")

    if isinstance(field, dict) and "lat" in field and "lon" in field:
        lat = float(field["lat"])
        lon = float(field["lon"])
        area_ha_target = float(scenario.get("area_ha") or 100.0) if isinstance(scenario, dict) else 100.0
        # Centred square of area_ha_target
        # s in meters = 100 * sqrt(area_ha)
        side_m = 100.0 * math.sqrt(area_ha_target)
        half_m = side_m / 2.0
        dlat = half_m / 111320.0
        cos_lat = math.cos(math.radians(lat))
        dlon = half_m / (111320.0 * (cos_lat if abs(cos_lat) > 1e-4 else 1.0))
        coords = [
            [round(lon - dlon, 6), round(lat - dlat, 6)],
            [round(lon + dlon, 6), round(lat - dlat, 6)],
            [round(lon + dlon, 6), round(lat + dlat, 6)],
            [round(lon - dlon, 6), round(lat + dlat, 6)],
            [round(lon - dlon, 6), round(lat - dlat, 6)],
        ]
        field_note = (
            "Lectura aproximada: dibujá el lote en el mapa para una lectura precisa."
            if is_es
            else "Approximate reading: draw the field on the map for an accurate reading."
        )
    else:
        coords = parse_geojson_polygon(field)

    validate_polygon_coords(coords)
    field_ha = round(polygon_area_ha(coords), 1)

    if field_ha < 1.0:
        raise ScenarioError("El lote es demasiado chico para píxeles de 10 m (mínimo 1 ha)." if is_es else "Field too small for 10 m pixels (minimum 1 ha).")
    if field_ha > 5000.0:
        raise ScenarioError("El lote supera las 5.000 ha: dividilo en lotes más chicos." if is_es else "Field exceeds 5,000 ha: split it into smaller fields.")

    pts = coords[:-1]
    centroid_lon = sum(p[0] for p in pts) / len(pts)
    centroid_lat = sum(p[1] for p in pts) / len(pts)
    centroid = [round(centroid_lon, 5), round(centroid_lat, 5)]
    region = region_for_point(centroid_lon, centroid_lat)

    poly_geojson = {"type": "Polygon", "coordinates": [coords]}
    poly_hash = hashlib.sha256(json.dumps([[round(c[0], 6), round(c[1], 6)] for c in coords]).encode()).hexdigest()[:12]
    cache_dir = get_cache_dir()

    # Normalize crop
    crop_norm = None
    if crop is not None:
        crop_clean = crop.strip().lower()
        if crop_clean in CROP_NORMALIZE:
            crop_norm = CROP_NORMALIZE[crop_clean]
        else:
            raise ScenarioError(f"Cultivo desconocido: {crop}." if is_es else f"Unknown crop: {crop}.")

    # 2. Date handling
    today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    date_ref_str = date or today_iso
    try:
        date_ref = datetime.fromisoformat(date_ref_str).date()
    except ValueError as e:
        raise ScenarioError(f"Fecha inválida: {date_ref_str}") from e



    start_date_str = (date_ref - timedelta(days=max_age_days)).strftime("%Y-%m-%d")

    # 3. Search Earth Search
    raw_scenes = search_fn(poly_geojson, start_date_str, date_ref_str)
    scenes = deduplicate_scenes(raw_scenes)

    if not scenes:
        return {
            "status": "no_scene",
            "field_ha": field_ha,
            "centroid": centroid,
            "region": region,
            "scenes_considered": [],
            "message": "No se encontraron escenas satelitales para las fechas solicitadas." if is_es else "No satellite scenes found for the requested dates.",
            "source": "Sentinel-2 L2A (ESA Copernicus), via Element84 Earth Search; NDVI computed by DORA",
        }

    # 4. Pick winning scene
    winning_stats: dict | None = None
    winning_ndvi: np.ndarray | None = None
    scenes_considered: list[dict] = []

    for feat in scenes:
        st, arr = _process_candidate_scene(
            feat,
            poly_geojson,
            field_ha,
            cache_dir,
            poly_hash,
            reader_fn,
            min_clear_share=min_clear_share,
        )
        if st is None:
            continue
        scenes_considered.append({
            "date": st["scene_date"],
            "clear_share_pct": st["clear_share_pct"],
            "used": bool(st.get("used", False)),
        })
        if st.get("used") and winning_stats is None:
            winning_stats = st
            winning_ndvi = arr
            break

    if winning_stats is None:
        return {
            "status": "no_clear_scene",
            "field_ha": field_ha,
            "centroid": centroid,
            "region": region,
            "scenes_considered": scenes_considered,
            "message": (
                "Las imágenes de los últimos 30 días tienen nubes sobre el lote; la próxima pasada es en 2 a 5 días."
                if is_es
                else "Images from the last 30 days have clouds over the field; next pass in 2 to 5 days."
            ),
            "source": "Sentinel-2 L2A (ESA Copernicus), via Element84 Earth Search; NDVI computed by DORA",
        }

    scene_date_obj = dt_date(winning_stats["scene_year"], winning_stats["scene_month"], winning_stats["scene_day"])
    days_old = max(0, (date_ref - scene_date_obj).days)

    # 5. Historical normal
    # 5 previous years or same_crop_years
    curr_year = winning_stats["scene_year"]
    if same_crop_years:
        target_years = sorted(list(same_crop_years))
    else:
        target_years = [curr_year - 5 + i for i in range(5)]

    def _fetch_year_normal(y: int) -> tuple[int, float | None]:
        # Window of +/- 15 days around same day of year
        try:
            target_dt = dt_date(y, winning_stats["scene_month"], winning_stats["scene_day"])
        except ValueError:
            target_dt = dt_date(y, winning_stats["scene_month"], winning_stats["scene_day"] - 1)

        y_start = (target_dt - timedelta(days=15)).strftime("%Y-%m-%d")
        y_end = (target_dt + timedelta(days=15)).strftime("%Y-%m-%d")

        try:
            y_raw = search_fn(poly_geojson, y_start, y_end)
            y_scenes = deduplicate_scenes(y_raw)
        except Exception:
            return y, None

        best_med: float | None = None
        best_clear_pct: float = -1.0

        for y_feat in y_scenes:
            y_st, _ = _process_candidate_scene(
                y_feat,
                poly_geojson,
                field_ha,
                cache_dir,
                poly_hash,
                reader_fn,
                min_clear_share=min_clear_share,
            )
            if y_st and y_st.get("used"):
                if y_st["clear_share_pct"] > best_clear_pct:
                    best_clear_pct = y_st["clear_share_pct"]
                    best_med = y_st["ndvi_median"]

        return y, best_med

    per_year: dict[str, float] = {}
    with ThreadPoolExecutor(max_workers=min(8, len(target_years) or 1)) as pool:
        futures = {pool.submit(_fetch_year_normal, y): y for y in target_years}
        for fut in as_completed(futures):
            try:
                y, med = fut.result(timeout=25)
                if med is not None:
                    per_year[str(y)] = med
            except Exception:
                pass

    normal_dict: dict | None = None
    anomaly_pct: float | None = None
    if len(per_year) >= 3:
        normal_med = round(float(np.median(list(per_year.values()))), 2)
        normal_dict = {
            "ndvi_median": normal_med,
            "years_used": sorted([int(y) for y in per_year.keys()]),
            "per_year": {k: per_year[k] for k in sorted(per_year.keys())},
            "window_days": 15,
        }
        curr_med = winning_stats.get("ndvi_median_raw", winning_stats["ndvi_median"])
        if normal_med > 1e-6:
            raw_anomaly = (curr_med / normal_med - 1.0) * 100.0
            anomaly_pct = round(raw_anomaly, 1)
        else:
            anomaly_pct = 0.0

    # 6. Yield proposal
    yield_dict: dict | None = None
    if crop_norm is not None and normal_dict is not None and region is not None:
        if in_reading_window(region, crop_norm, winning_stats["scene_date"]):
            curr_med = winning_stats.get("ndvi_median_raw", winning_stats["ndvi_median"])
            norm_med_val = normal_dict["ndvi_median"]
            ratio_raw = (curr_med / norm_med_val) if norm_med_val > 1e-6 else 1.0
            ratio_used = round(float(np.clip(ratio_raw, 0.5, 1.1)), 3)

            base_source = None
            base_t_ha = None
            if isinstance(scenario, dict) and "yields" in scenario and crop_norm in scenario["yields"]:
                base_t_ha = float(scenario["yields"][crop_norm])
                base_source = f"lo dijo el productor ({crop_norm}={base_t_ha})" if is_es else f"farmer specified ({crop_norm}={base_t_ha})"
            elif region:
                try:
                    reg_crops = load_region_data(region).get("crops", {})
                    if crop_norm in reg_crops:
                        base_t_ha = float(reg_crops[crop_norm]["yield"])
                        base_source = f"MAGyP {region}"
                except Exception:
                    pass

            if base_t_ha is not None:
                proposed_t_ha = round(base_t_ha * ratio_used, 1)
                rule_text = (
                    "Rinde propuesto = rinde normal × (verde de hoy ÷ verde normal del lote). Es una regla simple, no un modelo calibrado."
                    if is_es
                    else "Proposed yield = normal yield × (today's greenness ÷ normal greenness). Simple rule, not a calibrated model."
                )
                yield_dict = {
                    "crop": crop_norm,
                    "base_t_ha": round(base_t_ha, 2),
                    "base_source": base_source,
                    "ratio_used": ratio_used,
                    "proposed_t_ha": proposed_t_ha,
                    "rule": rule_text,
                    "needs_confirmation": True,
                }
        else:
            yield_dict = {
                "crop": crop_norm,
                "note": (
                    f"Todavía es temprano (o tarde) para que el verde diga algo del rinde del {crop_norm}."
                    if is_es
                    else f"It is too early (or too late) for greenness to reflect {crop_norm} yield."
                ),
            }

    history_note = (
        "En años anteriores el lote pudo tener otro cultivo: si me decís en qué años tuvo trigo, comparo solo con esos."
        if is_es
        else "In past years the field may have had another crop: if you tell me which years had wheat, I will compare only with those."
    )
    if crop_norm and crop_norm != "wheat":
        crop_name_note = crop if is_es else crop_norm
        history_note = (
            f"En años anteriores el lote pudo tener otro cultivo: si me decís en qué años tuvo {crop_name_note}, comparo solo con esos."
            if is_es
            else f"In past years the field may have had another crop: if you tell me which years had {crop_name_note}, I will compare only with those."
        )

    out: dict[str, Any] = {
        "status": "ok",
        "field_ha": field_ha,
        "centroid": centroid,
        "region": region,
        "scene_id": winning_stats["scene_id"],
        "scene_date": winning_stats["scene_date"],
        "scene_day": winning_stats["scene_day"],
        "scene_month": winning_stats["scene_month"],
        "scene_year": winning_stats["scene_year"],
        "days_old": days_old,
        "clear_share_pct": winning_stats["clear_share_pct"],
        "pixels_clear": winning_stats["pixels_clear"],
        "ndvi_median": winning_stats["ndvi_median"],
        "ndvi_p10": winning_stats["ndvi_p10"],
        "ndvi_p90": winning_stats["ndvi_p90"],
        "weak_share_pct": winning_stats["weak_share_pct"],
        "weak_ha": winning_stats["weak_ha"],
        "water_share_pct": winning_stats["water_share_pct"],
        "normal": normal_dict,
        "anomaly_pct": anomaly_pct,
        "yield": yield_dict,
        "scenes_considered": scenes_considered,
        "overlay_path": winning_stats["overlay_path"],
        "history_note": history_note,
        "source": "Sentinel-2 L2A (ESA Copernicus), via Element84 Earth Search; NDVI computed by DORA",
        "checks": winning_stats["checks"],
    }
    if field_note:
        out["field_note"] = field_note

    # 7. Re-plan if requested
    if replan and scenario:
        from .tools import _replan_with_yields
        target_crop = crop_norm or (list(scenario.get("crops", []))[0] if scenario.get("crops") else "wheat")
        confirmed_yield = yield_t_ha if yield_t_ha is not None else (yield_dict.get("proposed_t_ha") if yield_dict else None)
        if confirmed_yield is not None:
            replan_res = _replan_with_yields(
                scenario,
                yields_after={target_crop: confirmed_yield},
                crops=[target_crop],
                lang=clean_lang,
            )
            out["before"] = replan_res["before"]
            out["after"] = replan_res["after"]
            out["npv_change_usd"] = replan_res["npv_change_usd"]
            out["extra_credit_needed_usd"] = replan_res["extra_credit_needed_usd"]
            if "credit_line_usd" in replan_res:
                out["credit_line_usd"] = replan_res["credit_line_usd"]



    return out
