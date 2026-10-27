"""Acceptance tests for SPEC-14: Freight routes to the buyer (truck, rail, barge, ocean).

All tests must run without network access.
"""
import pytest
from dora.scenario import Scenario, REGIONS, load_routes_data
from dora.engine import optimize


def test_one_route_matches_default_freight_for_every_region():
    """Test 1: One route whose legs sum to today's freight gives the same plan and NPV as today, for every region."""
    for reg in ("southeast_buenos_aires", "pampas_core", "iowa", "mato_grosso"):
        default_freight = float(REGIONS[reg]["default_freight_usd_t"])

        sc_base = Scenario(region=reg, freight_usd_t=default_freight)
        res_base = optimize(sc_base)

        # Single truck leg equal to default freight
        route_single = {
            "id": "single_truck",
            "name": f"Single truck {default_freight} USD/t",
            "capacity_t": None,
            "legs": [{"mode": "truck", "from": "farm", "to": "port", "usd_t": default_freight}],
        }
        sc_route = Scenario(region=reg, freight_usd_t=default_freight, routes=[route_single])
        res_route = optimize(sc_route)

        assert res_route.npv == pytest.approx(res_base.npv, rel=1e-5), f"Failed for region {reg}"
        for c in sc_base.crops:
            assert res_route.hectares[c] == pytest.approx(res_base.hectares[c], rel=1e-5), f"Crop {c} in {reg}"

        # Two legs summing to default freight
        route_multi = {
            "id": "multi_leg",
            "name": f"Multi leg {default_freight} USD/t",
            "capacity_t": None,
            "legs": [
                {"mode": "truck", "from": "farm", "to": "elevator", "usd_t": round(default_freight * 0.6, 2)},
                {"mode": "truck", "from": "elevator", "to": "port", "usd_t": round(default_freight * 0.4, 2)},
            ],
        }
        sc_multi = Scenario(region=reg, freight_usd_t=default_freight, routes=[route_multi])
        res_multi = optimize(sc_multi)
        assert res_multi.npv == pytest.approx(res_base.npv, rel=1e-5), f"Multi-leg failed for {reg}"


def test_two_routes_different_costs_all_sales_go_by_cheaper():
    """Test 2: Two routes with different costs and no capacity: all sales go by the cheaper route."""
    route_cheap = {
        "id": "cheap_route",
        "name": "Cheaper transport (15 USD/t)",
        "capacity_t": None,
        "legs": [{"mode": "truck", "from": "farm", "to": "port", "usd_t": 15.0}],
    }
    route_expensive = {
        "id": "expensive_route",
        "name": "Expensive transport (30 USD/t)",
        "capacity_t": None,
        "legs": [{"mode": "truck", "from": "farm", "to": "port", "usd_t": 30.0}],
    }

    sc = Scenario(
        region="southeast_buenos_aires",
        routes=[route_cheap, route_expensive],
    )
    res = optimize(sc)

    # Everything sold should go via route_cheap
    cheap_tonnes = res.tonnes_by_route.get("cheap_route", 0.0)
    expensive_tonnes = res.tonnes_by_route.get("expensive_route", 0.0)

    assert cheap_tonnes > 100.0, f"Expected cheap tonnes > 100, got {cheap_tonnes}"
    assert expensive_tonnes == pytest.approx(0.0, abs=1e-4), f"Expected 0 on expensive route, got {expensive_tonnes}"


def test_cheaper_route_with_capacity_shadow_price_and_perturbation():
    """Test 3: Cheaper route with capacity below harvest is used up to capacity,

    the rest goes by the other, shadow price equals cost difference, and passes perturbation check.
    """
    cheap_cap = 500.0
    route_cheap = {
        "id": "rail_cheap",
        "name": "Rail allocation (15 USD/t)",
        "capacity_t": cheap_cap,
        "legs": [{"mode": "rail", "from": "station", "to": "port", "usd_t": 15.0}],
    }
    route_expensive = {
        "id": "truck_exp",
        "name": "Truck unlimited (25 USD/t)",
        "capacity_t": None,
        "legs": [{"mode": "truck", "from": "farm", "to": "port", "usd_t": 25.0}],
    }

    sc = Scenario(
        region="pampas_core",
        routes=[route_cheap, route_expensive],
    )
    res = optimize(sc)

    cheap_tonnes = res.tonnes_by_route.get("rail_cheap", 0.0)
    exp_tonnes = res.tonnes_by_route.get("truck_exp", 0.0)

    # Cheaper route used up to its capacity
    assert cheap_tonnes == pytest.approx(cheap_cap, rel=1e-3)
    # Remaining tonnes go by expensive route
    assert exp_tonnes > 100.0

    # Perturbation check: increase capacity by 1 tonne
    sc_pert = Scenario(
        region="pampas_core",
        routes=[
            dict(route_cheap, capacity_t=cheap_cap + 1.0),
            route_expensive,
        ],
    )
    res_pert = optimize(sc_pert)
    delta_npv = res_pert.npv - res.npv

    shadow_price = res.route_capacity_shadow_prices.get("rail_cheap", 0.0)
    assert shadow_price > 0.0
    assert shadow_price == pytest.approx(delta_npv, rel=1e-2)
    # The undiscounted cost difference is 10.0 USD/t; discounted to p=0 it is ~9-10 USD/t
    assert 7.0 <= shadow_price <= 10.5


def test_monthly_barge_cost_rise_in_autumn_shifts_sales():
    """Test 4: A monthly barge cost that rises in autumn moves barge sales to other months

    or to the other route when the difference exceeds the storage cost.
    """
    # In Iowa, harvest is in early/late autumn (fortnights 9-11: Sep-Oct).
    # Scenario A: Flat barge rate 28 USD/t across the season.
    # Scenario B: High autumn barge rate (50 USD/t in Sep/Oct), returning to 25 USD/t in winter/spring.
    # With storage cost of 2 USD/t/month, storing for 2 months costs 4 USD/t, which is much less than 22 USD/t spike.
    route_flat = {
        "id": "barge_flat",
        "name": "Flat barge",
        "capacity_t": None,
        "legs": [
            {"mode": "truck", "from": "farm", "to": "river", "usd_t": 12.0},
            {"mode": "barge", "from": "river", "to": "gulf", "usd_t": 28.0},
        ],
    }

    route_autumn_spike = {
        "id": "barge_spike",
        "name": "Spike barge in autumn",
        "capacity_t": None,
        "legs": [
            {"mode": "truck", "from": "farm", "to": "river", "usd_t": 12.0},
            {
                "mode": "barge",
                "from": "river",
                "to": "gulf",
                "usd_t": 25.0,
                "usd_t_by_month": {
                    "sep": 55.0,
                    "oct": 55.0,
                    "nov": 25.0,
                    "dec": 25.0,
                    "jan": 25.0,
                    "feb": 25.0,
                    "mar": 25.0,
                    "apr": 25.0,
                    "may": 25.0,
                    "jun": 25.0,
                },
            },
        ],
    }

    destination_price = {"corn": 240.0, "soybean": 450.0}

    sc_flat = Scenario(
        region="iowa",
        routes=[route_flat],
        destination_price_usd_t=destination_price,
    )
    res_flat = optimize(sc_flat)

    sc_spike = Scenario(
        region="iowa",
        routes=[route_autumn_spike],
        destination_price_usd_t=destination_price,
    )
    res_spike = optimize(sc_spike)

    # In res_spike, sales in Sep/Oct (fortnights 8, 9, 10, 11) should be 0 because storage is cheaper
    # than paying the 30 USD/t barge penalty
    autumn_sales_flat = 0.0
    autumn_sales_spike = 0.0
    autumn_fortnights = (8, 9, 10, 11)  # Sep and Oct
    for c in sc_flat.crops:
        for p in autumn_fortnights:
            autumn_sales_flat += res_flat.sales.get(c, {}).get(p, 0.0)
            autumn_sales_spike += res_spike.sales.get(c, {}).get(p, 0.0)

    assert autumn_sales_spike < 1e-4, f"Expected 0 autumn sales during barge spike, got {autumn_sales_spike}"
    # Meanwhile post-autumn sales in spike scenario are higher
    post_autumn_sales_spike = sum(
        t for c, sales in res_spike.sales.items() for p, t in sales.items() if p > 11
    )
    assert post_autumn_sales_spike > 500.0


def test_decomposition_adds_up_for_every_crop_and_route():
    """Test 5: The decomposition adds up: destination - legs - taxes = farm-gate price, for every crop and route."""
    for reg in ("southeast_buenos_aires", "pampas_core", "iowa", "mato_grosso"):
        routes_data = load_routes_data(reg)
        routes = routes_data.get("routes", [])
        assert routes, f"No routes found for region {reg}"

        for r in routes:
            sc = Scenario(region=reg, routes=[r])
            for c in sc.crops:
                decomp = sc.farm_gate_decomposition(c, r=r)

                dest = decomp["destination_price_usd_t"]
                legs = decomp["total_legs_usd_t"]
                taxes = decomp["taxes_usd_t"]
                fg = decomp["farm_gate_price_usd_t"]
                marketing = decomp["marketing_usd_t"]
                net_p = decomp["net_price_usd_t"]

                # Check identity: destination - legs - taxes = farm-gate price
                assert dest - legs - taxes == pytest.approx(fg, abs=0.02), (
                    f"Decomposition failed for {reg} crop {c} route {r.get('id')}: "
                    f"dest={dest}, legs={legs}, taxes={taxes}, fg={fg}"
                )
                # Check net price after marketing
                assert fg - marketing == pytest.approx(net_p, abs=0.02)

        # Also test with custom destination_price_usd_t (e.g. CFR China quotes)
        dest_quotes = {"wheat": 320.0, "corn": 250.0, "soybean": 460.0, "sunflower": 410.0}
        sc_dest = Scenario(region=reg, routes=routes, destination_price_usd_t=dest_quotes)
        for c in sc_dest.crops:
            for r in routes:
                decomp = sc_dest.farm_gate_decomposition(c, r=r)
                dest = decomp["destination_price_usd_t"]
                legs = decomp["total_legs_usd_t"]
                taxes = decomp["taxes_usd_t"]
                fg = decomp["farm_gate_price_usd_t"]
                assert dest == pytest.approx(dest_quotes[c], abs=0.02)
                assert dest - legs - taxes == pytest.approx(fg, abs=0.02)


def test_all_routes_files_cite_sources_and_marked_placeholder():
    """Verify that every route data file cites public publications with date and has placeholder: true."""
    for reg in ("southeast_buenos_aires", "pampas_core", "iowa", "mato_grosso"):
        data = load_routes_data(reg)
        assert data.get("placeholder") is True, f"Region {reg} must have placeholder: true"
        assert "citation" in data, f"Region {reg} must cite public publication"
        for r in data.get("routes", []):
            assert "id" in r and "legs" in r
            for leg in r["legs"]:
                assert "mode" in leg
                assert "usd_t" in leg
                assert "source" in leg
                assert "date" in leg
