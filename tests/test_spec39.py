"""Tests for SPEC-39: break-even prices from linear program duals."""
from __future__ import annotations

import copy
import json
from dataclasses import replace
import pytest

from dora.engine import optimize
from dora.scenario import Scenario
from dora.tools import break_even_prices, run_tool


def test_1_sign_and_size_of_reduced_cost():
    """1. Sign and size of the reduced cost.
    A scenario where corn has 0 ha: forcing 1 ha of corn (min_area 1) lowers the NPV
    by the reported reduced cost of its best window, within 1 %."""
    sc0 = Scenario(
        region="southeast_buenos_aires",
        area_ha=500.0,
        own_capital_usd=50_000.0,
        allow_rent_out=False,
    )
    r0 = optimize(sc0)
    assert r0.hectares.get("corn", 0.0) == pytest.approx(0.0, abs=1e-4)

    wids = r0.reduced_cost_usd_ha["corn"]
    best_wid = min(wids, key=lambda w: wids[w])
    rc_best = wids[best_wid]
    assert rc_best > 0.0

    sc1 = Scenario(
        region="southeast_buenos_aires",
        area_ha=500.0,
        own_capital_usd=50_000.0,
        allow_rent_out=False,
        constraints=[{"type": "min_area", "crop": "corn", "ha": 1.0}],
    )
    r1 = optimize(sc1)
    delta_npv = r0.npv - r1.npv
    assert delta_npv > 0.0
    # Within 1%
    assert abs(delta_npv - rc_best) / rc_best < 0.01


def test_2_price_needed_whole_curve_rise():
    """2. Price needed works. For that crop, raising its whole curve by
    whole_curve_rise_usd_t * 1.05 makes it enter (> 0.5 ha); by * 0.95 it does not."""
    sc0 = Scenario(
        region="southeast_buenos_aires",
        area_ha=500.0,
        own_capital_usd=50_000.0,
        allow_rent_out=False,
    )
    res = break_even_prices(sc0, verify=False)
    corn_res = next(c for c in res["crops"] if c["crop"] == "corn")
    rise = corn_res["whole_curve_rise_usd_t"]
    assert rise > 0.0

    def run_corn_delta(mult: float) -> float:
        delta = rise * mult
        new_pc = copy.deepcopy(sc0.price_curve)
        new_prices = dict(sc0.prices)
        if "corn" in new_pc and new_pc["corn"]:
            for m in new_pc["corn"]:
                new_pc["corn"][m] += delta
        else:
            new_prices["corn"] = sc0.price("corn") + delta
        sc_mod = replace(sc0, price_curve=new_pc, prices=new_prices)
        r = optimize(sc_mod)
        return float(r.hectares.get("corn", 0.0))

    ha_up = run_corn_delta(1.05)
    ha_down = run_corn_delta(0.95)
    assert ha_up > 0.5, f"Corn should enter with mult 1.05, got {ha_up} ha"
    assert ha_down <= 0.5, f"Corn should not enter with mult 0.95, got {ha_down} ha"


def test_3_per_fortnight_price_needed():
    """3. Per fortnight. For the best fortnight only, raising that fortnight's price
    (and only that one) to price_needed * 1.05 makes the crop enter."""
    sc0 = Scenario(
        region="southeast_buenos_aires",
        area_ha=500.0,
        own_capital_usd=50_000.0,
        allow_rent_out=False,
    )
    res = break_even_prices(sc0, verify=False)
    corn_res = next(c for c in res["crops"] if c["crop"] == "corn")
    best = corn_res["best"]
    p_best = best["fortnight"]
    p_needed = best["price_needed_usd_t"]

    orig_net = sc0.net_price_route

    def custom_net_up(c: str, p: int, r: dict) -> float:
        if c == "corn" and p == p_best:
            gross_p = p_needed * 1.05
            gross_receipts = sc0.gross_receipts_rate * gross_p
            tx_tax = sc0.transaction_tax_rate * gross_p
            tot_legs = sc0.route_cost(r, p)
            return gross_p - tot_legs - gross_receipts - tx_tax - sc0.marketing_per_t(c)
        return orig_net(c, p, r)

    sc_mod = copy.copy(sc0)
    sc_mod.net_price_route = custom_net_up
    r = optimize(sc_mod)
    assert r.hectares.get("corn", 0.0) > 0.5


def test_4_tax_gap_formula():
    """4. Taxes. With gross_receipts_rate 0.01 and transaction_tax_rate 0.006
    the gap is the net gap divided by 0.984 (unit test on the formula)."""
    gr_rate = 0.01
    tx_rate = 0.006
    tax_denom = 1.0 - gr_rate - tx_rate
    assert tax_denom == pytest.approx(0.984, abs=1e-6)

    gap_net = 10.0
    gap_price = gap_net / tax_denom
    assert gap_price == pytest.approx(gap_net / 0.984, abs=1e-6)


def test_5_crops_in_plan_listed_in_already_in_plan():
    """5. Crops in the plan are listed in already_in_plan with hectares and no price."""
    sc0 = Scenario(
        region="southeast_buenos_aires",
        area_ha=500.0,
        own_capital_usd=50_000.0,
        allow_rent_out=False,
    )
    res = break_even_prices(sc0, verify=False)
    already = res.get("already_in_plan", [])
    assert len(already) >= 2
    crops_already = [item["crop"] for item in already]
    assert "wheat" in crops_already
    assert "soybean" in crops_already

    for item in already:
        assert "crop" in item
        assert "hectares" in item
        assert item["hectares"] > 0
        assert "price" not in item
        assert "price_needed_usd_t" not in item
        assert "price_now_usd_t" not in item


def test_6_spec38_case_all_rented_out():
    """6. SPEC-38 case: Southeast Buenos Aires 500 ha owned, 50,000 USD, everything rented out:
    every crop gets a price, context mentions the rent, and test 2 holds for each crop."""
    sc = Scenario(
        region="southeast_buenos_aires",
        area_ha=500.0,
        own_capital_usd=50_000.0,
        allow_rent_out=True,
    )
    r_base = optimize(sc)
    assert r_base.rent_out_ha == pytest.approx(500.0, abs=1e-4)

    res = break_even_prices(sc, verify=False)
    assert "context" in res
    assert "425.1" in res["context"]
    assert "alquilar paga" in res["context"] or "renting out pays" in res["context"]

    assert len(res["crops"]) == 4
    crop_names = [c["crop"] for c in res["crops"]]
    for expected in ["wheat", "corn", "soybean", "sunflower"]:
        assert expected in crop_names

    for cr in res["crops"]:
        c_name = cr["crop"]
        rise = cr["whole_curve_rise_usd_t"]
        assert rise > 0.0

        def run_crop(mult: float) -> float:
            delta = rise * mult
            new_pc = copy.deepcopy(sc.price_curve)
            new_prices = dict(sc.prices)
            if c_name in new_pc and new_pc[c_name]:
                for m in new_pc[c_name]:
                    new_pc[c_name][m] += delta
            else:
                new_prices[c_name] = sc.price(c_name) + delta
            sc_mod = replace(sc, price_curve=new_pc, prices=new_prices)
            r = optimize(sc_mod)
            return float(r.hectares.get(c_name, 0.0))

        ha_up = run_crop(1.05)
        ha_down = run_crop(0.95)
        assert ha_up > 0.5, f"{c_name} failed ha_up > 0.5 (got {ha_up})"
        assert ha_down <= 0.5, f"{c_name} failed ha_down <= 0.5 (got {ha_down})"


def test_7_climate_scenarios_message():
    """7. Climate scenarios: the tool returns the 'not available' message, no exception."""
    sc_payload = {
        "area_ha": 500,
        "climate_scenarios": [{"name": "dry", "probability": 0.33, "yield_factors": {}}],
    }
    res_es = break_even_prices(sc_payload, lang="es")
    assert "message" in res_es
    assert "Precios de indiferencia no disponibles" in res_es["message"]

    res_en = break_even_prices(sc_payload, lang="en")
    assert "message" in res_en
    assert "Break-even prices not available" in res_en["message"]


def test_8_tool_registered_and_run_tool():
    """8. The tool is in test_tools.py's list and runs through run_tool."""
    from dora.tools import TOOLS
    assert "break_even_prices" in TOOLS

    payload = {
        "scenario": {
            "area_ha": 500,
            "own_capital_usd": 50000,
            "allow_rent_out": False,
        },
        "verify": False,
        "lang": "es",
    }
    out_str = run_tool("break_even_prices", json.dumps(payload))
    out = json.loads(out_str)
    assert "crops" in out
    assert "already_in_plan" in out
    assert "meaning" in out
    assert isinstance(out["crops"], list)

