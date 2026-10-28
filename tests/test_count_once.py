"""SPEC-17: freight and rent counted once."""
import pytest

from dora.engine import optimize
from dora.scenario import FORTNIGHTS, Scenario, load_routes_data
from dora.tools import compare_regions, evaluate_season

IOWA_RENT = 677.1


def _sown(res) -> float:
    return sum(h for h in res.hectares.values() if h > 1e-6)


# 1. Rent once: a rented farm with the regional rent equals renting the same land in through rent_in,
#    and only the land that is sown is rented.
def test_rented_land_pays_rent_once():
    rented = optimize(Scenario(area_ha=500, rented_land=True, region="iowa", regional_rent_usd_ha=IOWA_RENT))
    rent_in = optimize(Scenario(area_ha=500, owned_ha=0, max_rent_in_ha=500, region="iowa",
                                regional_rent_usd_ha=IOWA_RENT, allow_rent_out=False))
    assert rented.npv == pytest.approx(rent_in.npv, abs=0.01)
    assert _sown(rented) > 1.0, "with one rent, some corn pays in Iowa"
    for res in (rented, rent_in):
        assert res.rent_in_ha == pytest.approx(_sown(res), abs=1e-4)


def test_rented_land_without_rent_takes_the_source_rent():
    rented = Scenario(area_ha=500, rented_land=True, region="iowa")
    owned = Scenario(area_ha=500, region="iowa")
    assert rented.regional_rent_usd_ha == pytest.approx(IOWA_RENT)
    for c in rented.crops:
        # Per-hectare payments differ only by the overhead, never by the rent.
        diff = sum(rented.payments_per_ha(c).values()) - sum(owned.payments_per_ha(c).values())
        assert diff == pytest.approx(rented.data[c]["overhead_rented"] - rented.data[c]["overhead_owned"])


# 2. Rent once in the comparison.
def test_compare_regions_rented_farm_pays_rent_once():
    out = compare_regions({"area_ha": 500, "rented_land": True}, regions=["iowa"])
    single = optimize(Scenario(area_ha=500, owned_ha=0, max_rent_in_ha=500, region="iowa",
                               regional_rent_usd_ha=IOWA_RENT, allow_rent_out=False,
                               routes=load_routes_data("iowa")["routes"]))
    assert out["regions"]["iowa"]["with_land_cost"]["npv_usd"] == pytest.approx(single.npv, abs=0.01)


# 3. Freight once: a route whose only leg is the freight inside MAGyP's marketing nets the same as today.
def test_route_with_magyp_freight_nets_the_default_price():
    base = Scenario(region="southeast_buenos_aires")
    route = {"id": "truck", "name": "truck", "legs": [
        {"mode": "truck", "from": "farm", "to": "Quequén", "usd_t": base.freight_in_marketing_usd_t}]}
    with_route = Scenario(region="southeast_buenos_aires", routes=[route])
    for c in base.crops:
        for p in range(base.calendar[c]["harvest"], FORTNIGHTS):
            # Before SPEC-17: gross price minus the whole MAGyP marketing cost.
            gross = base.price(c) * (1 + base.monthly_price_rise) ** ((p - base.calendar[c]["harvest"]) / 2)
            before = gross - base.data[c]["marketing_harvest"] / base.data[c]["yield"]
            assert with_route.net_price(c, p) == pytest.approx(before, abs=0.01)
            assert base.net_price(c, p) == pytest.approx(before, abs=0.01)


def test_iowa_local_price_is_not_charged_inland_freight_twice():
    sc = Scenario(region="iowa", routes=[
        {"id": "gulf", "name": "gulf", "legs": [{"mode": "truck", "usd_t": 12.0}, {"mode": "barge", "usd_t": 28.0},
                                                {"mode": "port", "usd_t": 6.0}, {"mode": "ocean", "usd_t": 48.0}]},
        {"id": "pnw", "name": "pnw", "legs": [{"mode": "truck", "usd_t": 8.0}, {"mode": "rail", "usd_t": 58.0},
                                              {"mode": "port", "usd_t": 6.0}, {"mode": "ocean", "usd_t": 28.0}]},
    ])
    c, p = "corn", sc.calendar["corn"]["harvest"]
    local = sc.price(c) - sc.marketing_per_t(c)
    assert sc.net_price_route(c, p, sc.routes[0]) == pytest.approx(local, abs=0.01)
    # The destination price is the same for both routes, so the other route differs by its total cost
    # (100 against 94 USD/t): its dearer rail is partly made up by the cheaper Pacific crossing.
    assert sc.net_price_route(c, p, sc.routes[1]) == pytest.approx(local - 6.0, abs=0.01)


# 4. Freight visible in evaluate_season, with its source.
def test_evaluate_season_shows_the_freight():
    out = evaluate_season({"region": "southeast_buenos_aires"})
    for c, d in out["farm_gate_decomposition"].items():
        assert d["inland_freight_usd_t"] == pytest.approx(18.0)
        assert d["freight_taken_out_of_marketing_usd_t"] == pytest.approx(18.0)
        assert d["legs"][0]["usd_t"] == pytest.approx(18.0)
    sc = Scenario(region="southeast_buenos_aires")
    assert "CATAC" in sc.routes[0]["legs"][0]["source"]


# 5. The decomposition adds up for every region and crop.
@pytest.mark.parametrize("region", ["southeast_buenos_aires", "pampas_core", "iowa", "mato_grosso"])
def test_decomposition_adds_up(region):
    sc = Scenario(region=region)
    for c in sc.crops:
        d = sc.farm_gate_decomposition(c)
        total = d["destination_price_usd_t"] - d["total_legs_usd_t"] - d["taxes_usd_t"] - d["marketing_usd_t"]
        assert total == pytest.approx(d["net_price_usd_t"], abs=0.02)
        assert d["net_price_usd_t"] == pytest.approx(sc.net_price(c, sc.calendar[c]["harvest"]), abs=0.02)


# 6. A forward sale at the port price nets the same as a spot sale at that price in that fortnight.
def test_forward_sale_nets_like_spot_sale():
    sc = Scenario(region="southeast_buenos_aires")
    c, p = "soybean", 24
    spot_gross = sc.price(c) * (1 + sc.monthly_price_rise) ** ((p - sc.calendar[c]["harvest"]) / 2)
    spot_net = sc.net_price(c, p)
    fwd_net = spot_gross - sc.marketing_per_t(c) - sc.inland_cost(sc.routes[0], p)
    assert fwd_net == pytest.approx(spot_net, abs=0.01)
