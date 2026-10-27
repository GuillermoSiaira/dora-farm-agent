"""Acceptance tests for SPEC-12: Livestock as an alternative use of the land.

Tests verify:
1. Empty livestock gives identical results to baseline engine (NPV rel 1e-12).
2. With cattle-only land and cow-calf allowed, cow-calf uses that land and shadow price
   passes the perturbation check.
3. When crop margins fall below cow-calf's (e.g. 40% soybean price cut), livestock
   takes more of the shared land.
4. Herd purchase ties up capital at fortnight 0: with scarce capital, raising herd_end_value
   makes herd purchase more attractive and lowering it less.
5. Livestock income enters cash with the same sign convention as grain sales.
6. Parameter validation, modeling guide mappings, and tool outputs.
"""
from dataclasses import replace
import pytest

from dora.engine import optimize
from dora.scenario import Scenario, ScenarioError
from dora.tools import build_scenario, evaluate_season, shadow_prices


def test_no_livestock_identical_to_baseline():
    """1. Without livestock activities, results are identical to the current engine (NPV rel 1e-12)."""
    sc_base = Scenario(area_ha=500.0, own_capital_usd=50_000.0)
    sc_ls = Scenario(area_ha=500.0, own_capital_usd=50_000.0, livestock=[])

    r_base = optimize(sc_base)
    r_ls = optimize(sc_ls)

    rel_diff = abs(r_base.npv - r_ls.npv) / abs(r_base.npv)
    assert rel_diff < 1e-12
    assert abs(r_base.final_wealth - r_ls.final_wealth) / abs(r_base.final_wealth) < 1e-12
    assert abs(r_base.land_shadow_price - r_ls.land_shadow_price) < 1e-9
    assert r_base.hectares == r_ls.hectares
    assert r_base.cash == r_ls.cash
    assert r_base.debt == r_ls.debt


def test_cattle_only_land_cow_calf_perturbation():
    """2. With cattle-only land and cow-calf allowed, cow-calf uses that land.
    Its shadow price passes the perturbation check of tests/test_engine.py.
    """
    sc = Scenario(
        area_ha=500.0,
        own_capital_usd=500_000.0,
        livestock=["cow_calf"],
        livestock_only_ha=100.0,
    )
    r = optimize(sc)

    # Cow-calf uses the cattle-only land
    assert r.hectares_livestock.get("cow_calf", 0.0) >= 100.0 - 1e-6

    # Shadow price of cattle-only land is positive
    sp = r.livestock_only_shadow_price
    assert sp > 0.0

    # Perturbation check: NPV(L+1) - NPV(L) <= lambda_low <= NPV(L) - NPV(L-1)
    npv = {
        L: optimize(replace(sc, livestock_only_ha=float(L))).npv
        for L in (99, 100, 101)
    }
    assert npv[101] - npv[100] - 1e-4 <= sp <= npv[100] - npv[99] + 1e-4


def test_crop_margins_fall_shifts_shared_land_to_livestock():
    """3. When crop margins fall below cow-calf's (e.g. 40% soybean price cut),
    livestock takes more of the shared land.
    """
    # In Pampas Core at normal prices (~310 USD/t), soybean margin (~468 USD/ha)
    # is well above cow-calf (~161 USD/ha), so all shared land goes to crops.
    sc_normal = Scenario(
        region="pampas_core",
        area_ha=500.0,
        own_capital_usd=500_000.0,
        crops=("soybean",),
        max_crop_share=1.0,
        livestock=["cow_calf"],
    )
    r_normal = optimize(sc_normal)
    assert r_normal.hectares_livestock.get("cow_calf", 0.0) < 1e-3
    assert r_normal.hectares.get("soybean", 0.0) == pytest.approx(500.0, abs=1e-3)

    # With a 40% soybean price cut (310 -> 180 USD/t), soybean margin falls
    # below cow-calf's margin, so livestock takes the shared land.
    sc_cut = Scenario(
        region="pampas_core",
        area_ha=500.0,
        own_capital_usd=500_000.0,
        crops=("soybean",),
        max_crop_share=1.0,
        livestock=["cow_calf"],
        prices={"soybean": 180.0},
    )
    r_cut = optimize(sc_cut)
    assert r_cut.hectares_livestock.get("cow_calf", 0.0) == pytest.approx(500.0, abs=1e-3)
    assert r_cut.hectares.get("soybean", 0.0) < 1e-3


def test_herd_purchase_ties_up_capital_and_valuation():
    """4. Herd purchase ties up capital at fortnight 0: with scarce capital,
    raising herd_end_value makes herd purchase more attractive, and lowering it less.
    """
    sc = Scenario(
        area_ha=500.0,
        own_capital_usd=30_000.0,
        credit_line_usd=10_000.0,
        livestock=["cow_calf_herd_purchase"],
        crops=("soybean",),
    )
    r_base = optimize(sc)
    r_high = optimize(replace(sc, herd_end_value=700.0))
    r_low = optimize(replace(sc, herd_end_value=300.0))

    # Higher end value raises NPV; lower end value lowers NPV
    assert r_high.npv > r_base.npv > r_low.npv

    # Higher end value makes herd purchase more attractive (more hectares allocated);
    # lower end value makes it less attractive (fewer hectares or none)
    ha_high = r_high.hectares_livestock.get("cow_calf_herd_purchase", 0.0)
    ha_base = r_base.hectares_livestock.get("cow_calf_herd_purchase", 0.0)
    ha_low = r_low.hectares_livestock.get("cow_calf_herd_purchase", 0.0)

    assert ha_high > ha_base
    assert ha_base > ha_low


def test_livestock_income_sign_convention_matches_grain_sales():
    """5. Livestock income enters cash with the same sign convention as grain sales."""
    sc = Scenario(
        area_ha=100.0,
        own_capital_usd=50_000.0,
        livestock=["cow_calf"],
        livestock_only_ha=100.0,
    )
    r = optimize(sc)
    sale_p, net_inc = sc.livestock_net_income("cow_calf")

    assert net_inc > 0.0
    # In fortnight sale_p, positive livestock revenue comes into the account,
    # increasing ending cash surplus S_p relative to pre-sale fortnight S_{p-1}
    assert r.cash[sale_p] > r.cash[sale_p - 1]


def test_livestock_tools_and_validation():
    """Check build_scenario, evaluate_season, and shadow_prices integration."""
    sc_dict = {
        "area_ha": 500.0,
        "region": "southeast_buenos_aires",
        "livestock": ["cow_calf", "steer_fattening"],
        "livestock_only_ha": 150.0,
        "max_livestock_share": 0.4,
    }

    built = build_scenario(sc_dict)["scenario"]
    assert built["livestock"]["value"] == ["cow_calf", "steer_fattening"]
    assert built["livestock_only_ha"]["value"] == 150.0
    assert built["max_livestock_share"]["value"] == 0.4

    eval_out = evaluate_season(sc_dict)
    assert "hectares_livestock" in eval_out
    assert "livestock_only_shadow_price_usd_ha" in eval_out
    assert eval_out["livestock_only_shadow_price_usd_ha"] > 0.0

    sp_out = shadow_prices(sc_dict)
    assert "cattle_only_land" in sp_out
    assert sp_out["cattle_only_land"]["usd_per_extra_ha"] > 0.0

    # Unsupported region for livestock raises ScenarioError
    with pytest.raises(ScenarioError, match="not supported"):
        evaluate_season({
            "region": "iowa",
            "livestock": ["cow_calf"],
        })
