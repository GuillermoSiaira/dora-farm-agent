"""Acceptance tests for SPEC-14b: Logistics as a network (shared legs), route data and comparison fixes."""

import time
import pytest
from dora.scenario import Scenario, REGIONS
from dora.engine import optimize
from dora.tools import evaluate_season, shadow_prices, compare_regions
from app import build_app


def test_shared_leg_capacity_and_perturbation():
    """Two routes share one leg whose capacity is below harvest.

    Sum of tonnes on that leg = capacity, and the shadow price passes the perturbation check.
    """
    # Create two routes sharing a port terminal leg with capacity 500.0 t
    shared_leg = {
        "leg_id": "shared_port_elevator",
        "name": "Shared Port Elevator Terminal",
        "mode": "port",
        "usd_t": 5.0,
        "capacity_t": 500.0,
    }
    r1 = {
        "id": "route_truck",
        "name": "Truck to Port, Ocean to China",
        "legs": [
            {"leg_id": "truck_local", "mode": "truck", "usd_t": 15.0},
            shared_leg,
            {"leg_id": "ocean_china", "mode": "ocean", "usd_t": 45.0},
        ],
    }
    r2 = {
        "id": "route_rail",
        "name": "Rail to Port, Ocean to China",
        "legs": [
            {"leg_id": "rail_local", "mode": "rail", "usd_t": 20.0},
            shared_leg,
            {"leg_id": "ocean_china", "mode": "ocean", "usd_t": 45.0},
        ],
    }
    # 200 ha of wheat at yield 4.11 t/ha = 822 t > 500 t capacity (max_crop_share=1.0)
    # Provide enough cash so cash isn't scarce
    sc = Scenario(
        area_ha=200.0,
        crops=("wheat",),
        max_crop_share=1.0,
        own_capital_usd=100_000.0,
        routes=[r1, r2],
    )
    res = optimize(sc)

    # Total tonnes across both routes must equal 500.0 t (since both use the shared leg)
    tot_tonnes = sum(res.tonnes_by_route.values())
    assert abs(tot_tonnes - 500.0) < 1e-2
    assert abs(res.tonnes_by_leg["shared_port_elevator"] - 500.0) < 1e-2

    sp_info = res.leg_shadow_prices["shared_port_elevator"]
    assert sp_info["mode"] == "port"
    shadow_price = sp_info["shadow_price_usd_t"]
    assert shadow_price > 0.0

    # Perturbation check: capacity + 1 t and capacity - 1 t
    shared_plus = dict(shared_leg, capacity_t=501.0)
    sc_plus = Scenario(
        area_ha=200.0,
        crops=("wheat",),
        max_crop_share=1.0,
        own_capital_usd=100_000.0,
        routes=[
            dict(r1, legs=[r1["legs"][0], shared_plus, r1["legs"][2]]),
            dict(r2, legs=[r2["legs"][0], shared_plus, r2["legs"][2]]),
        ],
    )
    res_plus = optimize(sc_plus)

    shared_minus = dict(shared_leg, capacity_t=499.0)
    sc_minus = Scenario(
        area_ha=200.0,
        crops=("wheat",),
        max_crop_share=1.0,
        own_capital_usd=100_000.0,
        routes=[
            dict(r1, legs=[r1["legs"][0], shared_minus, r1["legs"][2]]),
            dict(r2, legs=[r2["legs"][0], shared_minus, r2["legs"][2]]),
        ],
    )
    res_minus = optimize(sc_minus)

    # dNPV/dCap ≈ shadow_price
    d_npv_plus = res_plus.npv - res.npv
    d_npv_minus = res.npv - res_minus.npv
    assert abs(d_npv_plus - shadow_price) < 0.2
    assert abs(d_npv_minus - shadow_price) < 0.2


def test_non_binding_leg_capacity_reports_zero():
    """A leg capacity that is not binding has a shadow price of 0 and appears in the output."""
    shared_leg = {
        "leg_id": "ample_port",
        "name": "Ample Port Elevator",
        "mode": "port",
        "usd_t": 5.0,
        "capacity_t": 100_000.0,  # clearly non-binding
    }
    r = {
        "id": "route_ample",
        "name": "Route via ample port",
        "capacity_t": 50_000.0,  # non-binding route capacity
        "legs": [
            {"leg_id": "truck_leg", "mode": "truck", "usd_t": 15.0},
            shared_leg,
        ],
    }
    sc = Scenario(
        area_ha=50.0,
        crops=("wheat",),
        own_capital_usd=100_000.0,
        routes=[r],
    )
    res = optimize(sc)

    # Route shadow price should appear as 0.0 in route_capacity_shadow_prices
    assert "route_ample" in res.route_capacity_shadow_prices
    assert res.route_capacity_shadow_prices["route_ample"] == 0.0

    # Summary should also keep 0.0 for route_capacity_shadow_prices
    s = res.summary()
    assert "route_ample" in s.get("route_capacity_shadow_prices", {})
    assert s["route_capacity_shadow_prices"]["route_ample"] == 0.0

    # Leg shadow price should appear in leg_shadow_prices with 0.0
    assert "ample_port" in res.leg_shadow_prices
    assert res.leg_shadow_prices["ample_port"]["shadow_price_usd_t"] == 0.0
    assert res.leg_shadow_prices["ample_port"]["mode"] == "port"

    # Also check tools evaluate_season and shadow_prices
    ev = evaluate_season({
        "area_ha": 50.0,
        "crops": ["wheat"],
        "own_capital_usd": 100_000.0,
        "routes": [r],
    })
    assert "ample_port" in ev.get("leg_shadow_prices", {})
    assert ev["leg_shadow_prices"]["ample_port"]["shadow_price_usd_t"] == 0.0

    sp = shadow_prices({
        "area_ha": 50.0,
        "crops": ["wheat"],
        "own_capital_usd": 100_000.0,
        "routes": [r],
    })
    assert "ample_port" in sp.get("leg_shadow_prices", {})
    assert sp["leg_shadow_prices"]["ample_port"]["shadow_price_usd_t"] == 0.0


def test_freight_share_equals_hand_computation():
    """Freight share = inland legs ÷ farm-gate gross price, computed by hand for one region, equals reported."""
    sc_dict = {
        "area_ha": 100.0,
        "crops": ["soybean"],
        "own_capital_usd": 100_000.0,
        "region": "mato_grosso",
    }
    res_comp = compare_regions(sc_dict, regions=["mato_grosso"], mode="same_farm")
    mg_entry = res_comp["regions"]["mato_grosso"]

    # Hand calculation for Mato Grosso with soybean:
    # Gross price from data: 355.0 USD/t
    # Inland legs from truck_santos (the only inland leg is truck 75.0 USD/t)
    expected_freight_share = round(75.0 / 355.0, 4)  # 0.2113
    assert abs(mg_entry["freight_share"] - expected_freight_share) < 1e-4
    assert abs(mg_entry["freight_share_pct"] - round(expected_freight_share * 100, 2)) < 1e-2


def test_mato_grosso_reads_own_basis_file():
    """Mato Grosso no longer reads basis_iowa.json."""
    mg_reg = REGIONS["mato_grosso"]
    basis_file = mg_reg.get("basis_file")
    assert basis_file is not None
    assert basis_file.is_file()
    assert "basis_iowa" not in basis_file.name
    assert "basis_mato_grosso" in basis_file.name


def test_build_app_under_5_seconds():
    """build_app() builds in under 5 seconds."""
    t0 = time.perf_counter()
    demo = build_app()
    elapsed = time.perf_counter() - t0
    assert demo is not None
    assert elapsed < 5.0, f"build_app() took {elapsed:.2f}s, expected < 5.0s"
