"""Acceptance tests for SPEC-06: regions (Southeast Buenos Aires and Iowa) and field on map. No network calls."""
from dataclasses import replace
import json
import math
import pytest

from dora.engine import optimize
from dora.geo import field_from_map, polygon_area_ha, region_for_point
from dora.scenario import Scenario
from dora.tools import run_tool


def between_derivatives(sc, field, dual, delta=1.0, tol=1e-4):
    base = optimize(sc).npv
    up = optimize(replace(sc, **{field: getattr(sc, field) + delta})).npv
    down = optimize(replace(sc, **{field: getattr(sc, field) - delta})).npv
    right, left = (up - base) / delta, (base - down) / delta
    return right - tol <= dual <= left + tol


# 1. A 1 km x 1 km square near Balcarce (about -58.25, -37.85) has an area of 100 ha +/- 0.5%
def test_balcarce_1km_square_area_100ha():
    lat0, lon0 = -37.85, -58.25
    R = 6371008.8
    dlat = (1000.0 / R) * (180.0 / math.pi)
    dlon = (1000.0 / (R * math.cos(math.radians(lat0)))) * (180.0 / math.pi)
    coords = [
        [lon0, lat0],
        [lon0 + dlon, lat0],
        [lon0 + dlon, lat0 + dlat],
        [lon0, lat0 + dlat],
        [lon0, lat0],
    ]
    area = polygon_area_ha(coords)
    assert abs(area - 100.0) / 100.0 <= 0.005, f"Expected 100 ha +/- 0.5%, got {area}"


# 2. region_for_point bounding boxes
def test_region_for_point():
    assert region_for_point(-58.25, -37.85) == "southeast_buenos_aires"
    assert region_for_point(-93.6, 42.0) == "iowa"
    assert region_for_point(2.35, 48.85) is None


# 3. Scenario(region="iowa") uses Iowa's crops, calendar and season start.
#    The engine solves it, and every shadow price passes the same perturbation check as tests/test_engine.py.
def test_scenario_iowa_and_shadow_prices_perturbation():
    sc_default_iowa = Scenario(region="iowa")
    assert sc_default_iowa.crops == ("corn", "soybean")
    assert sc_default_iowa.season_start == "2026-04"
    assert sc_default_iowa.calendar["corn"]["harvest"] == 13
    assert sc_default_iowa.calendar["soybean"]["harvest"] == 12

    # Capital and credit shadow prices under scarce capital
    scarce = Scenario(region="iowa", own_capital_usd=50_000, credit_line_usd=100_000)
    r_scarce = optimize(scarce)
    assert r_scarce.npv > 0
    assert r_scarce.capital_shadow_price > 0.01
    assert between_derivatives(scarce, "own_capital_usd", r_scarce.cash_value[0])
    assert sum(r_scarce.credit_shadow_price) > 0.01
    assert between_derivatives(scarce, "credit_line_usd", sum(r_scarce.credit_shadow_price))

    # Land shadow price under abundant capital (with max_crop_share > 0.5 so land constraint binds instead of individual 50% caps)
    sc_land = Scenario(region="iowa", own_capital_usd=2_000_000, max_crop_share=0.7)
    r_land = optimize(sc_land)
    assert r_land.land_shadow_price > 0
    # One more owned hectare moves the land row and every rotation cap together (SPEC-21).
    npv = {a: optimize(replace(sc_land, area_ha=a)).npv for a in (499, 500, 501)}
    assert npv[501] - npv[500] - 1e-4 <= r_land.land_shadow_price <= npv[500] - npv[499] + 1e-4

    # Storage shadow price
    sc_stor = Scenario(region="iowa", own_capital_usd=2_000_000, storage_capacity_t=200, monthly_price_rise=0.03)
    r_stor = optimize(sc_stor)
    assert sum(r_stor.storage_shadow_price) > 0
    assert between_derivatives(sc_stor, "storage_capacity_t", sum(r_stor.storage_shadow_price))


# 4. The default region gives exactly the same results as before (NPV rel 1e-12).
def test_default_region_preserves_baseline():
    sc_implicit = Scenario()
    sc_explicit = Scenario(region="southeast_buenos_aires")
    r_implicit = optimize(sc_implicit)
    r_explicit = optimize(sc_explicit)
    rel_diff = abs(r_implicit.npv - r_explicit.npv) / abs(r_implicit.npv)
    assert rel_diff < 1e-12, f"Baseline NPV mismatch: {rel_diff}"


# 5. field_from_map through run_tool returns area and region for a valid polygon,
#    and a clear error for a self-intersecting or open one.
def test_field_from_map_tool():
    # Valid polygon in Southeast Buenos Aires
    valid_geojson = {
        "type": "Polygon",
        "coordinates": [[
            [-58.25, -37.85],
            [-58.24, -37.85],
            [-58.24, -37.84],
            [-58.25, -37.84],
            [-58.25, -37.85],
        ]]
    }
    raw = run_tool("field_from_map", json.dumps({"polygon": valid_geojson}))
    res = json.loads(raw)
    assert "error" not in res
    assert res["region"] == "southeast_buenos_aires"
    assert res["area_ha"] > 0
    assert isinstance(res["centroid"], list) and len(res["centroid"]) == 2

    # Valid polygon in Iowa
    iowa_geojson = {
        "type": "Polygon",
        "coordinates": [[
            [-93.65, 42.0],
            [-93.60, 42.0],
            [-93.60, 42.05],
            [-93.65, 42.05],
            [-93.65, 42.0],
        ]]
    }
    raw_iowa = run_tool("field_from_map", json.dumps({"polygon": iowa_geojson}))
    res_iowa = json.loads(raw_iowa)
    assert "error" not in res_iowa
    assert res_iowa["region"] == "iowa"
    assert res_iowa["area_ha"] > 0

    # Open polygon
    open_geojson = {
        "type": "Polygon",
        "coordinates": [[
            [-58.25, -37.85],
            [-58.24, -37.85],
            [-58.24, -37.84],
            [-58.25, -37.84],
        ]]
    }
    raw_open = run_tool("field_from_map", json.dumps({"polygon": open_geojson}))
    res_open = json.loads(raw_open)
    assert "error" in res_open
    assert "open" in res_open["error"].lower()

    # Self-intersecting polygon
    self_intersecting = {
        "type": "Polygon",
        "coordinates": [[
            [0.0, 0.0],
            [1.0, 1.0],
            [0.0, 1.0],
            [1.0, 0.0],
            [0.0, 0.0],
        ]]
    }
    raw_self = run_tool("field_from_map", json.dumps({"polygon": self_intersecting}))
    res_self = json.loads(raw_self)
    assert "error" in res_self
    assert "self-intersect" in res_self["error"].lower()


def test_cbot_curve_with_iowa_basis():
    sc = Scenario(region="iowa", price_curve_source="cbot_latest")
    assert sc.basis_usd_t
    assert "corn" in sc.basis_usd_t
    assert "soybean" in sc.basis_usd_t
    # Harvest price includes basis
    corn_harvest = sc.calendar["corn"]["harvest"]
    curve_pt = sc.curve_price("corn", corn_harvest)
    assert sc.price("corn") == pytest.approx(curve_pt + sc.basis_usd_t["corn"])


def test_build_scenario_iowa():
    from dora.tools import build_scenario
    res = build_scenario({"region": "iowa"})
    sc_data = res["scenario"]
    assert sc_data["region"]["value"] == "iowa"
    assert sc_data["crops"]["value"] == ["corn", "soybean"]
    assert "Iowa State University" in sc_data["price_corn"]["origin"]
    assert "Iowa State University" in sc_data["yield_corn"]["origin"]
