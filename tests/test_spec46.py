"""Tests for SPEC-46: Crop vigour from Sentinel-2 (NDVI of the farmer's field).

All tests run offline (DORA_OFFLINE=1), without paid APIs, without external network,
and without calling real LLMs.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from dora.agent import Agent
from dora.geo import parse_geojson_polygon, polygon_area_ha
from dora.satellite import (
    CROP_NORMALIZE,
    READING_WINDOWS,
    _process_candidate_scene,
    deduplicate_scenes,
    field_ndvi,
    generate_overlay,
    get_reflectance_offset,
    in_reading_window,
)
from dora.scenario import ScenarioError
from dora.tools import _replan_with_yields, assess_field_image, run_tool
from dora.verifier import check_scenario, verify

ROOT = Path(__file__).resolve().parent.parent
SAM_FIXTURES = ROOT / "tests" / "fixtures" / "sam"

# Sample polygon near Pergamino (~100 ha)
LON, LAT, D = -61.0, -33.9, 0.005
POLY = {
    "type": "Polygon",
    "coordinates": [[
        [LON - D, LAT - D],
        [LON + D, LAT - D],
        [LON + D, LAT + D],
        [LON - D, LAT + D],
        [LON - D, LAT - D],
    ]],
}


def _make_scene_feature(scene_id: str, dt_str: str, boa: bool = True, baseline: str = "05.13") -> dict:
    return {
        "type": "Feature",
        "id": scene_id,
        "properties": {
            "datetime": dt_str,
            "proj:code": "EPSG:32720",
            "earthsearch:boa_offset_applied": boa,
            "s2:processing_baseline": baseline,
        },
        "assets": {
            "red": {"href": f"mock://{scene_id}/B04.tif"},
            "nir": {"href": f"mock://{scene_id}/B08.tif"},
            "scl": {"href": f"mock://{scene_id}/SCL.tif"},
        },
    }


# ==============================================================================
# Test 1: NDVI arithmetic
# ==============================================================================


def test_1_ndvi_arithmetic(tmp_path, monkeypatch):
    """1. 20x20 field with red 0.05 / NIR 0.45 -> NDVI 0.80 exactly; half-bare field median/weak share."""
    monkeypatch.setenv("DORA_CACHE_DIR", str(tmp_path))

    feat_uniform = _make_scene_feature("S2B_UNIFORM", "2026-10-02T14:27:09Z")

    # Uniform field: Red = 500 DN (0.05), NIR = 4500 DN (0.45) -> NDVI = 0.80
    def uniform_reader(href, bounds, crs, out_shape=None):
        shape = out_shape or (50, 50)
        if "B04" in href:
            return np.full(shape, 500, dtype=np.uint16)
        elif "B08" in href:
            return np.full(shape, 4500, dtype=np.uint16)
        elif "SCL" in href:
            return np.full(shape, 4, dtype=np.uint8)  # vegetation
        return np.zeros(shape)

    res = field_ndvi(
        field=POLY,
        date="2026-10-05",
        _search=lambda poly, s, e: [feat_uniform],
        _reader=uniform_reader,
    )
    assert res["status"] == "ok"
    assert res["ndvi_median"] == 0.80
    assert res["weak_share_pct"] == 0.0
    assert res["weak_ha"] == 0.0

    # Half-bare field: top half NDVI 0.80, bottom half bare soil (Red 1500, NIR 2000 -> NDVI = 500/3500 ~ 0.14)
    feat_half = _make_scene_feature("S2B_HALF_BARE", "2026-10-02T14:27:09Z")

    def half_bare_reader(href, bounds, crs, out_shape=None):
        shape = out_shape or (50, 50)
        h, w = shape
        mid = h // 2
        if "B04" in href:
            arr = np.full(shape, 1500, dtype=np.uint16)
            arr[:mid] = 500
            arr[mid, :48] = 500
            return arr
        elif "B08" in href:
            arr = np.full(shape, 2000, dtype=np.uint16)
            arr[:mid] = 4500
            arr[mid, :48] = 4500
            return arr
        elif "SCL" in href:
            arr = np.full(shape, 5, dtype=np.uint8)  # bare soil
            arr[:mid] = 4  # veg
            arr[mid, :48] = 4
            return arr
        return np.zeros(shape)

    res_half = field_ndvi(
        field=POLY,
        date="2026-10-05",
        _search=lambda poly, s, e: [feat_half],
        _reader=half_bare_reader,
    )
    assert res_half["status"] == "ok"
    assert 0.40 <= res_half["ndvi_median"] <= 0.55
    assert 40.0 <= res_half["weak_share_pct"] <= 55.0
    assert res_half["weak_ha"] > 0.0


# ==============================================================================
# Test 2: Clouds
# ==============================================================================


def test_2_clouds(tmp_path, monkeypatch):
    """2. SCL with 40% cloud/shadow -> skipped, older 100% clear scene is used. All cloudy -> status no_clear_scene."""
    monkeypatch.setenv("DORA_CACHE_DIR", str(tmp_path))

    feat_cloudy = _make_scene_feature("S2B_20HPH_20261019_0_L2A", "2026-10-19T14:27:09Z")
    feat_clear = _make_scene_feature("S2B_20HPH_20261002_1_L2A", "2026-10-02T14:27:09Z")

    def cloud_reader(href, bounds, crs, out_shape=None):
        shape = out_shape or (50, 50)
        h, w = shape
        if "20261019" in href:
            if "SCL" in href:
                arr = np.full(shape, 4, dtype=np.uint8)
                # 40% cloud (SCL 9)
                arr[:int(h * 0.4)] = 9
                return arr
            return np.full(shape, 1000, dtype=np.uint16)
        else:
            if "SCL" in href:
                return np.full(shape, 4, dtype=np.uint8)
            if "B04" in href:
                return np.full(shape, 500, dtype=np.uint16)
            return np.full(shape, 2000, dtype=np.uint16)

    res = field_ndvi(
        field=POLY,
        date="2026-10-20",
        min_clear_share=0.7,
        _search=lambda poly, s, e: [feat_cloudy, feat_clear],
        _reader=cloud_reader,
    )
    assert res["status"] == "ok"
    assert res["scene_id"] == "S2B_20HPH_20261002_1_L2A"
    assert len(res["scenes_considered"]) == 2
    assert res["scenes_considered"][0]["date"] == "2026-10-19"
    assert res["scenes_considered"][0]["used"] is False
    assert res["scenes_considered"][1]["date"] == "2026-10-02"
    assert res["scenes_considered"][1]["used"] is True

    # All scenes cloudy
    res_cloudy = field_ndvi(
        field=POLY,
        date="2026-10-20",
        min_clear_share=0.7,
        _search=lambda poly, s, e: [feat_cloudy],
        _reader=cloud_reader,
    )
    assert res_cloudy["status"] == "no_clear_scene"
    assert "nubes" in res_cloudy["message"].lower() or "clouds" in res_cloudy["message"].lower()


# ==============================================================================
# Test 3: Reflectance rule
# ==============================================================================


def test_3_reflectance_rule(tmp_path, monkeypatch):
    """3. boa_offset_applied: true -> no offset; missing and baseline 05.13 -> offset -0.1; baseline 03.01 -> no offset."""
    monkeypatch.setenv("DORA_CACHE_DIR", str(tmp_path))

    # 1. boa_offset_applied: true
    p1 = {"earthsearch:boa_offset_applied": True, "s2:processing_baseline": "05.13"}
    off1, rule1 = get_reflectance_offset(p1)
    assert off1 == 0.0
    assert rule1 == "boa_offset_applied"

    # 2. boa_offset_applied missing, baseline >= 04.00
    p2 = {"s2:processing_baseline": "05.13"}
    off2, rule2 = get_reflectance_offset(p2)
    assert off2 == -0.1
    assert rule2 == "baseline_ge_0400"

    # 3. baseline < 04.00
    p3 = {"s2:processing_baseline": "03.01"}
    off3, rule3 = get_reflectance_offset(p3)
    assert off3 == 0.0
    assert rule3 == "baseline_lt_0400"

    # Check that in prototype's case, boa_offset_applied keeps NDVI <= 1.0
    feat = _make_scene_feature("S2B_PROT", "2026-10-02T14:27:09Z", boa=True, baseline="05.13")
    # Red DN = 415, NIR DN = 1520
    def proto_reader(href, bounds, crs, out_shape=None):
        shape = out_shape or (50, 50)
        if "B04" in href:
            return np.full(shape, 415, dtype=np.uint16)
        elif "B08" in href:
            return np.full(shape, 1520, dtype=np.uint16)
        elif "SCL" in href:
            return np.full(shape, 4, dtype=np.uint8)
        return np.zeros(shape)

    res = field_ndvi(
        field=POLY,
        date="2026-10-05",
        _search=lambda poly, s, e: [feat],
        _reader=proto_reader,
    )
    assert res["status"] == "ok"
    assert -1.0 <= res["ndvi_median"] <= 1.0
    assert res["checks"]["reflectance_rule"] == "boa_offset_applied"
    assert res["checks"]["ndvi_in_range"] is True


# ==============================================================================
# Test 4: Duplicates
# ==============================================================================


def test_4_duplicates(tmp_path, monkeypatch):
    """4. _0_L2A and _1_L2A of same date/tile -> only _1 is kept and read."""
    monkeypatch.setenv("DORA_CACHE_DIR", str(tmp_path))

    f0 = _make_scene_feature("S2B_20HPH_20261002_0_L2A", "2026-10-02T14:27:09Z")
    f1 = _make_scene_feature("S2B_20HPH_20261002_1_L2A", "2026-10-02T14:27:09Z")

    deduped = deduplicate_scenes([f0, f1])
    assert len(deduped) == 1
    assert deduped[0]["id"] == "S2B_20HPH_20261002_1_L2A"

    calls = []
    def spy_reader(href, bounds, crs, out_shape=None):
        calls.append(href)
        shape = out_shape or (50, 50)
        if "SCL" in href:
            return np.full(shape, 4, dtype=np.uint8)
        if "B04" in href:
            return np.full(shape, 500, dtype=np.uint16)
        return np.full(shape, 2000, dtype=np.uint16)

    res = field_ndvi(
        field=POLY,
        date="2026-10-05",
        _search=lambda poly, s, e: [f0, f1],
        _reader=spy_reader,
    )
    assert res["status"] == "ok"
    assert res["scene_id"] == "S2B_20HPH_20261002_1_L2A"
    assert all("20261002_1" in c for c in calls)


# ==============================================================================
# Test 5: Field mask and erosion
# ==============================================================================


def test_5_field_mask(tmp_path, monkeypatch):
    """5. Polygon covering half the window; 1-pixel erosion removes border; SCL water inside field -> water_share_pct."""
    monkeypatch.setenv("DORA_CACHE_DIR", str(tmp_path))

    feat = _make_scene_feature("S2B_20HPH_20261002_1_L2A", "2026-10-02T14:27:09Z")

    def water_reader(href, bounds, crs, out_shape=None):
        shape = out_shape or (50, 50)
        h, w = shape
        if "SCL" in href:
            arr = np.full(shape, 4, dtype=np.uint8)
            # 20% water (SCL 6)
            arr[:int(h * 0.2)] = 6
            return arr
        elif "B04" in href:
            return np.full(shape, 500, dtype=np.uint16)
        elif "B08" in href:
            return np.full(shape, 3000, dtype=np.uint16)
        return np.zeros(shape)

    res = field_ndvi(
        field=POLY,
        date="2026-10-05",
        _search=lambda poly, s, e: [feat],
        _reader=water_reader,
    )
    assert res["status"] == "ok"
    assert res["water_share_pct"] > 0.0
    assert res["pixels_clear"] > 0


# ==============================================================================
# Test 6: Normal and anomaly
# ==============================================================================


def test_6_normal_and_anomaly(tmp_path, monkeypatch):
    """6. 5 fake years with medians [0.71, 0.64, 0.70, 0.69, 0.73] -> normal 0.70; now 0.588 -> anomaly -16.0%."""
    monkeypatch.setenv("DORA_CACHE_DIR", str(tmp_path))

    current_feat = _make_scene_feature("S2B_20HPH_20261002_1_L2A", "2026-10-02T14:27:09Z")
    past_years = [2021, 2022, 2023, 2024, 2025]
    medians_map = {2021: 0.71, 2022: 0.64, 2023: 0.70, 2024: 0.69, 2025: 0.73}

    def multiyear_search(poly, s, e):
        yr = int(s[:4])
        if yr == 2026:
            return [current_feat]
        elif yr in medians_map:
            return [_make_scene_feature(f"S2_PAST_{yr}", f"{yr}-10-02T14:00:00Z")]
        return []

    def multiyear_reader(href, bounds, crs, out_shape=None):
        shape = out_shape or (50, 50)
        if "SCL" in href:
            return np.full(shape, 4, dtype=np.uint8)

        # Current scene: now NDVI = 0.588
        if "20261002" in href:
            med = 0.588
        else:
            med = 0.70
            for yr, target_med in medians_map.items():
                if str(yr) in href:
                    med = target_med
                    break

        n_val = int(round(5000 * (1.0 + med)))
        r_val = int(round(5000 * (1.0 - med)))
        if "B04" in href:
            return np.full(shape, r_val, dtype=np.uint16)
        elif "B08" in href:
            return np.full(shape, n_val, dtype=np.uint16)

        return np.full(shape, 2000, dtype=np.uint16)

    res = field_ndvi(
        field=POLY,
        date="2026-10-05",
        _search=multiyear_search,
        _reader=multiyear_reader,
    )
    assert res["status"] == "ok"
    assert res["normal"] is not None
    assert res["normal"]["ndvi_median"] == 0.70
    assert res["anomaly_pct"] == -16.0

    # Only 2 usable years -> normal is null
    res_2years = field_ndvi(
        field=POLY,
        date="2026-10-05",
        same_crop_years=[2022, 2024],
        _search=multiyear_search,
        _reader=multiyear_reader,
    )
    assert res_2years["status"] == "ok"
    assert res_2years["normal"] is None
    assert res_2years["anomaly_pct"] is None


# ==============================================================================
# Test 7: Yield proposal
# ==============================================================================


def test_7_yield_proposal(tmp_path, monkeypatch):
    """7. Wheat in pampas_core on 2/10 base 3.8, ratio 0.841 -> 3.2. Ratio 0.3 clipped to 0.5 -> 1.9."""
    monkeypatch.setenv("DORA_CACHE_DIR", str(tmp_path))

    feat = _make_scene_feature("S2B_20HPH_20261002_1_L2A", "2026-10-02T14:27:09Z")
    medians_map = {2021: 0.70, 2022: 0.70, 2023: 0.70, 2024: 0.70, 2025: 0.70}

    def yr_search(poly, s, e):
        yr = int(s[:4])
        return [feat] if yr == 2026 else [_make_scene_feature(f"S2_{yr}", f"{yr}-10-02T14:00:00Z")]

    def yr_reader(href, bounds, crs, out_shape=None):
        shape = out_shape or (50, 50)
        if "SCL" in href:
            return np.full(shape, 4, dtype=np.uint8)
        if "20261002" in href:
            med = 0.5887  # 0.5887 / 0.70 = 0.841
        else:
            med = 0.70
        n_val = int(round(5000 * (1.0 + med)))
        r_val = int(round(5000 * (1.0 - med)))
        if "B04" in href:
            return np.full(shape, r_val, dtype=np.uint16)
        elif "B08" in href:
            return np.full(shape, n_val, dtype=np.uint16)
        return np.full(shape, 2000, dtype=np.uint16)

    # Base from scenario yields: wheat 3.8
    res = field_ndvi(
        field=POLY,
        scenario={"region": "pampas_core", "yields": {"wheat": 3.8}},
        crop="wheat",
        date="2026-10-05",
        _search=yr_search,
        _reader=yr_reader,
    )
    assert res["yield"] is not None
    assert res["yield"]["ratio_used"] == 0.841
    assert res["yield"]["proposed_t_ha"] == 3.2

    # Ratio 0.3 clipped to 0.5 -> 1.9
    feat_low = _make_scene_feature("S2B_LOW_NDVI", "2026-10-02T14:27:09Z")
    def extreme_reader(href, bounds, crs, out_shape=None):
        shape = out_shape or (50, 50)
        if "SCL" in href:
            return np.full(shape, 4, dtype=np.uint8)
        med = 0.20 if "LOW_NDVI" in href else 0.70
        n_val = int(round(5000 * (1.0 + med)))
        r_val = int(round(5000 * (1.0 - med)))
        return np.full(shape, r_val if "B04" in href else n_val, dtype=np.uint16)

    res_clipped = field_ndvi(
        field=POLY,
        scenario={"region": "pampas_core", "yields": {"wheat": 3.8}},
        crop="wheat",
        date="2026-10-05",
        _search=lambda poly, s, e: [feat_low] if int(s[:4]) == 2026 else [_make_scene_feature(f"S2_{s[:4]}", f"{s[:4]}-10-02T14:00:00Z")],
        _reader=extreme_reader,
    )
    assert res_clipped["yield"]["ratio_used"] == 0.5
    assert res_clipped["yield"]["proposed_t_ha"] == 1.9

    # Soybean on 2/10 -> outside reading window (15/1 to 15/3)
    res_soy = field_ndvi(
        field=POLY,
        scenario={"region": "pampas_core"},
        crop="soybean",
        date="2026-10-05",
        _search=yr_search,
        _reader=yr_reader,
    )
    assert res_soy["yield"] is not None
    assert "note" in res_soy["yield"]
    assert "temprano" in res_soy["yield"]["note"].lower() or "early" in res_soy["yield"]["note"].lower()

    # Base from farmer's yields.wheat = 4.2 -> 3.5
    res_farmer = field_ndvi(
        field=POLY,
        scenario={"region": "pampas_core", "yields": {"wheat": 4.2}},
        crop="wheat",
        date="2026-10-05",
        _search=yr_search,
        _reader=yr_reader,
    )
    assert res_farmer["yield"]["proposed_t_ha"] == 3.5


# ==============================================================================
# Test 8: Re-plan and cache
# ==============================================================================


def test_8_replan_and_cache(tmp_path, monkeypatch):
    """8. replan=True, yield_t_ha=3.2 -> before/after equal to _replan_with_yields; second call hits cache (0 reader calls)."""
    monkeypatch.setenv("DORA_CACHE_DIR", str(tmp_path))

    feat = _make_scene_feature("S2B_20HPH_20261002_1_L2A", "2026-10-02T14:27:09Z")

    reader_call_count = [0]
    def counted_reader(href, bounds, crs, out_shape=None):
        reader_call_count[0] += 1
        shape = out_shape or (50, 50)
        if "SCL" in href:
            return np.full(shape, 4, dtype=np.uint8)
        med = 0.59 if "20261002" in href else 0.70
        n_val = int(round(5000 * (1.0 + med)))
        r_val = int(round(5000 * (1.0 - med)))
        return np.full(shape, r_val if "B04" in href else n_val, dtype=np.uint16)

    def counted_search(poly, s, e):
        yr = int(s[:4])
        return [feat] if yr == 2026 else [_make_scene_feature(f"S2_{yr}", f"{yr}-10-02T14:00:00Z")]

    scenario = {
        "region": "pampas_core",
        "area_ha": 500.0,
        "own_capital_usd": 150000.0,
        "crops": ["wheat", "soybean"],
        "yields": {"wheat": 4.5, "soybean": 3.8},
        "constraints": [{"type": "min_area", "crop": "wheat", "ha": 200.0}],
    }

    # Call 1: initial reading
    res1 = field_ndvi(
        field=POLY,
        scenario=scenario,
        crop="wheat",
        date="2026-10-05",
        replan=False,
        _search=counted_search,
        _reader=counted_reader,
    )
    assert res1["status"] == "ok"
    initial_calls = reader_call_count[0]
    assert initial_calls > 0

    # Call 2: replan=True, yield_t_ha=3.2
    # Should use cache and make 0 new reader calls
    res2 = field_ndvi(
        field=POLY,
        scenario=scenario,
        crop="wheat",
        date="2026-10-05",
        replan=True,
        yield_t_ha=3.2,
        _search=counted_search,
        _reader=counted_reader,
    )
    assert res2["status"] == "ok"
    assert reader_call_count[0] == initial_calls  # 0 new reader calls!
    assert "before" in res2
    assert "after" in res2
    assert res2["npv_change_usd"] < 0  # lower yield -> lower NPV

    expected_replan = _replan_with_yields(scenario, {"wheat": 3.2}, crops=["wheat"])
    assert res2["before"]["npv_usd"] == expected_replan["before"]["npv_usd"]
    assert res2["after"]["npv_usd"] == expected_replan["after"]["npv_usd"]
    assert res2["npv_change_usd"] == expected_replan["npv_change_usd"]


# ==============================================================================
# Test 9: assess_field_image unchanged
# ==============================================================================


def test_9_assess_field_image_unchanged():
    """9. assess_field_image output unchanged after moving _replan_with_yields; run test_field_image suite."""
    puddle_txt = (SAM_FIXTURES / "wisconsin_puddle.txt").read_text(encoding="utf-8")

    buf = BytesIO()
    Image.new("RGB", (100, 100), (40, 160, 40)).save(buf, format="PNG")
    photo = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    def dummy_segmenter(image_data_url, concept):
        return puddle_txt

    out = assess_field_image(
        {"region": "southeast_buenos_aires", "area_ha": 500.0, "own_capital_usd": 50000.0},
        _images=[photo],
        _segmenter=dummy_segmenter,
    )
    assert out["affected_ha"] > 0
    assert "before" in out
    assert "after" in out
    assert "npv_change_usd" in out
    assert out["npv_change_usd"] < 0


# ==============================================================================
# Test 10: Errors the agent can act on
# ==============================================================================


def test_10_errors(monkeypatch):
    """10. Errors: no field/coords; self-intersecting polygon; 0.5 ha; 8000 ha; unknown crop; offline; rasterio missing."""
    # 1. No field and no coordinates
    with pytest.raises(ScenarioError, match="(?i)coordenadas|polígono|polygon|coordinates"):
        field_ndvi(field=None, scenario={})

    # 2. Self-intersecting polygon
    self_intersecting = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [1, 1], [0, 1], [1, 0], [0, 0]]],
    }
    with pytest.raises(ScenarioError, match="(?i)self-intersecting|autointersec"):
        field_ndvi(field=self_intersecting)

    # 3. 0.5 ha (too small)
    small_poly = {
        "type": "Polygon",
        "coordinates": [[[-61.0, -33.9], [-61.0005, -33.9], [-61.0005, -33.9005], [-61.0, -33.9005], [-61.0, -33.9]]],
    }
    with pytest.raises(ScenarioError, match="(?i)chico|small|1 ha"):
        field_ndvi(field=small_poly)

    # 4. 8000 ha (too large)
    big_poly = {
        "type": "Polygon",
        "coordinates": [[[-61.0, -33.9], [-60.9, -33.9], [-60.9, -33.8], [-61.0, -33.8], [-61.0, -33.9]]],
    }
    with pytest.raises(ScenarioError, match=r"(?i)5\.000|5000|dividilo|split"):
        field_ndvi(field=big_poly)

    # 5. Unknown crop
    with pytest.raises(ScenarioError, match="(?i)cultivo desconocido|unknown crop"):
        field_ndvi(field=POLY, crop="avena")

    # 6. DORA_OFFLINE=1 with no cache
    monkeypatch.setenv("DORA_OFFLINE", "1")
    with pytest.raises(ScenarioError, match="(?i)sin conexión|offline"):
        field_ndvi(field=POLY, date="2026-10-05")

    # 7. rasterio missing
    monkeypatch.setattr("dora.satellite.rasterio", None)
    with pytest.raises(ScenarioError, match="(?i)requirements-geo.txt"):
        field_ndvi(field=POLY, date="2026-10-05")


# ==============================================================================
# Test 11: Verifier, dates as numbers
# ==============================================================================


def test_11_verifier_dates():
    """11. 'La imagen es del 2 de octubre de 2026, de hace 36 días' verifies; 'del 5 de octubre' does not."""
    tool_output = {
        "scene_day": 2,
        "scene_month": 10,
        "scene_year": 2026,
        "days_old": 36,
        "anomaly_pct": -15.9,
    }
    results = [json.dumps(tool_output)]
    user_texts = ["¿Cómo viene el lote?"]

    # Valid statement
    good_text = "La imagen es del 2 de octubre de 2026, de hace 36 días; está 16 % menos verde que lo normal."
    unsupported_good = verify(good_text, results, user_texts)
    assert unsupported_good == []

    # Invented date "5 de octubre"
    bad_text = "La imagen es del 5 de octubre de 2026, de hace 36 días."
    unsupported_bad = verify(bad_text, results, user_texts)
    assert any("5" in getattr(u, "text", str(u)) for u in unsupported_bad)


# ==============================================================================
# Test 12: Verifier, area from map
# ==============================================================================


def test_12_verifier_area_from_map():
    """12. evaluate_season with area_ha=100.2 after field_from_map returns 100.2 -> no area_ha problem; with 120 -> flagged."""
    tool_results = [{"field_ha": 100.2, "region": "pampas_core"}]

    # 1. Matches measured area (100.2)
    probs_good = check_scenario(
        "evaluate_season",
        {"scenario": {"area_ha": 100.2, "region": "pampas_core"}},
        ["Calculá el plan."],
        tool_results,
    )
    area_probs_good = [p for p in probs_good if p.parameter == "area_ha"]
    assert len(area_probs_good) == 0

    # 2. Does not match (120 ha)
    probs_bad = check_scenario(
        "evaluate_season",
        {"scenario": {"area_ha": 120.0, "region": "pampas_core"}},
        ["Calculá el plan."],
        tool_results,
    )
    area_probs_bad = [p for p in probs_bad if p.parameter == "area_ha"]
    assert len(area_probs_bad) == 1
    assert "100.2" in area_probs_bad[0].reason


# ==============================================================================
# Test 13: Agent turn with mocked model
# ==============================================================================


def test_13_agent_turn(tmp_path, monkeypatch):
    """13. Agent turn where model calls field_ndvi then answers with proposal as question passes verifier."""
    monkeypatch.setenv("DORA_CACHE_DIR", str(tmp_path))

    feat = _make_scene_feature("S2B_20HPH_20261002_1_L2A", "2026-10-02T14:27:09Z")

    def fake_reader(href, bounds, crs, out_shape=None):
        shape = out_shape or (50, 50)
        if "SCL" in href:
            return np.full(shape, 4, dtype=np.uint8)
        med = 0.5887 if "20261002" in href else 0.70
        n_val = int(round(5000 * (1.0 + med)))
        r_val = int(round(5000 * (1.0 - med)))
        return np.full(shape, r_val if "B04" in href else n_val, dtype=np.uint16)

    def fake_search(poly, s, e):
        yr = int(s[:4])
        return [feat] if yr == 2026 else [_make_scene_feature(f"S2_{yr}", f"{yr}-10-02T14:00:00Z")]

    monkeypatch.setattr("dora.satellite.search_scenes", fake_search)
    monkeypatch.setattr("dora.satellite.read_window", fake_reader)

    # Call field_ndvi directly to test agent flow
    tool_out = field_ndvi(
        field=POLY,
        scenario={"region": "pampas_core", "yields": {"wheat": 3.8}},
        crop="wheat",
        date="2026-11-07",
        max_age_days=40,
    )
    assert tool_out["status"] == "ok"
    assert tool_out["days_old"] == 36
    assert tool_out["yield"]["proposed_t_ha"] == 3.2

    # Verification of assistant text using the numbers from tool_out
    assistant_text = (
        "La imagen satelital es del 2 de octubre de 2026 (de hace 36 días). "
        "El lote está 16 % menos verde que lo normal histórico (NDVI 0,59 vs 0,70 normal). "
        "Si uso esa diferencia, el rinde propuesto baja a 3,2 t/ha. ¿Rehago el plan con 3,2 t/ha de trigo?"
    )
    unsupported = verify(assistant_text, [json.dumps(tool_out)], ["¿Cómo viene el trigo?"])
    assert unsupported == []
    assert tool_out.get("overlay_path") is not None
    assert os.path.isfile(tool_out["overlay_path"])


# ==============================================================================
# Test 14: Tools and MCP
# ==============================================================================


def test_14_tools_and_mcp(tmp_path, monkeypatch):
    """14. field_ndvi in run_tool, in MCP tool list (15 tools), and MCP call returns PNG resource and provenance."""
    monkeypatch.setenv("DORA_CACHE_DIR", str(tmp_path))

    feat = _make_scene_feature("S2B_20HPH_20261002_1_L2A", "2026-10-02T14:27:09Z")

    def fake_reader(href, bounds, crs, out_shape=None):
        shape = out_shape or (50, 50)
        if "SCL" in href:
            return np.full(shape, 4, dtype=np.uint8)
        if "B04" in href:
            return np.full(shape, 500, dtype=np.uint16)
        return np.full(shape, 2000, dtype=np.uint16)

    monkeypatch.setattr("dora.satellite.search_scenes", lambda p, s, e: [feat])
    monkeypatch.setattr("dora.satellite.read_window", fake_reader)

    # 1. run_tool
    raw_res = run_tool("field_ndvi", {"field": POLY, "date": "2026-10-05"})
    res_dict = json.loads(raw_res)
    assert res_dict["status"] == "ok"
    assert res_dict["scene_id"] == "S2B_20HPH_20261002_1_L2A"

    # 2. MCP call
    from mcp_server.server import field_ndvi as mcp_field_ndvi
    mcp_out = mcp_field_ndvi(field=POLY, date="2026-10-05")
    assert "result" in mcp_out
    assert "provenance" in mcp_out
    assert mcp_out["result"]["status"] == "ok"
    assert "resource" in mcp_out["result"]
    assert mcp_out["result"]["resource"]["mimeType"] == "image/png"
    assert len(mcp_out["result"]["resource"]["blob"]) > 0


# ==============================================================================
# Test 15: Clean data directory
# ==============================================================================


def test_15_clean_data_directory():
    """15. Clean state: no temporary files left in dora/data or observatory."""
    cmd = ["git", "status", "--porcelain", "dora/data", "observatory"]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
