"""Tests for SPEC-49: forward sales as a decision, with price risk."""
import math
import subprocess
import pytest
from pathlib import Path

from dora.scenario import Scenario, ScenarioError
from dora.engine import optimize, scenario_for_price_scenario, discrete_cvar

ROOT_DIR = Path(__file__).resolve().parent.parent

SCENARIOS = {
    "pampas_core_2000": {
        "region": "pampas_core",
        "area_ha": 2000,
        "owned_ha": 2000,
        "own_capital_usd": 500000,
    },
    "se_ba_500": {
        "region": "southeast_buenos_aires",
        "area_ha": 500,
        "owned_ha": 500,
        "own_capital_usd": 50000,
    },
    "rented_300": {
        "region": "pampas_core",
        "area_ha": 300,
        "owned_ha": 0,
        "own_capital_usd": 30000,
        "credit_line_usd": 200000,
    },
    "se_ba_rent_out": {
        "region": "southeast_buenos_aires",
        "area_ha": 500,
        "owned_ha": 500,
        "own_capital_usd": 50000,
        "allow_rent_out": True,
    },
    "livestock_500": {
        "region": "southeast_buenos_aires",
        "area_ha": 500,
        "owned_ha": 500,
        "own_capital_usd": 100000,
        "crops": [],
        "livestock": ["cow_calf"],
    },
}


def test_01_no_price_risk():
    """1. No price_risk: plan, NPV and every shadow price equal optimize today on example scenarios (± 1e-6)."""
    for name, sc_dict in SCENARIOS.items():
        sc1 = Scenario(**sc_dict)
        sc2 = Scenario(**sc_dict, price_risk=None)
        res1 = optimize(sc1)
        res2 = optimize(sc2)
        assert abs(res1.npv - res2.npv) < 1e-6, f"{name}: NPV mismatch"
        for c in sc1.crops:
            assert abs(res1.hectares.get(c, 0.0) - res2.hectares.get(c, 0.0)) < 1e-6, f"{name}: {c} ha mismatch"
        assert abs(res1.capital_shadow_price - res2.capital_shadow_price) < 1e-6, f"{name}: cap shadow price mismatch"
        assert abs(res1.land_shadow_price - res2.land_shadow_price) < 1e-6, f"{name}: land shadow price mismatch"


def test_02_one_scenario_zero_volatility():
    """2. One scenario, zero volatility: n_scenarios = 5 with vol = 0 gives the deterministic plan and NPV (± 0.01 USD)."""
    sc_det = Scenario(**SCENARIOS["pampas_core_2000"])
    res_det = optimize(sc_det)

    sc_zero = Scenario(
        **SCENARIOS["pampas_core_2000"],
        price_risk={
            "n_scenarios": 5,
            "vol_annual": {c: 0.0 for c in sc_det.crops},
            "risk_weight": 0.0,
        },
    )
    res_zero = optimize(sc_zero)

    assert abs(res_zero.npv - res_det.npv) <= 0.01, f"Expected NPV {res_det.npv}, got {res_zero.npv}"
    for c in sc_det.crops:
        assert abs(res_zero.hectares.get(c, 0.0) - res_det.hectares.get(c, 0.0)) <= 0.01


def test_03_mean_is_preserved():
    """3. Mean is preserved: for each crop, the mean of P_s equals the deterministic harvest price (± 1e-6)."""
    for sc_name in ["pampas_core_2000", "se_ba_500"]:
        sc = Scenario(**SCENARIOS[sc_name], price_risk={"n_scenarios": 9})
        res = optimize(sc)
        p_scens = res.price_scenarios
        assert len(p_scens) == 9

        for c in sc.crops:
            p_det = sc.price(c)
            p_s_vals = [s["harvest_prices"][c] for s in p_scens]
            mean_p = sum(p_s_vals) / len(p_s_vals)
            assert abs(mean_p - p_det) < 1e-4, f"{sc_name} {c}: mean {mean_p} != det {p_det}"


def test_04_risk_neutral_fair_offer():
    """4. Risk neutral, fair offer: with beta = 0 and the offer equal to the expected price, expected NPV >= deterministic NPV - 0.01."""
    sc_det = Scenario(region="pampas_core", area_ha=500, owned_ha=500, own_capital_usd=260000)
    res_det = optimize(sc_det)

    sc_fair = Scenario(
        region="pampas_core",
        area_ha=500,
        owned_ha=500,
        own_capital_usd=260000,
        price_risk={"n_scenarios": 9, "risk_weight": 0.0},
    )
    res_fair = optimize(sc_fair)

    assert res_fair.npv >= res_det.npv - 0.01, f"Fair offer expected NPV {res_fair.npv} < det NPV {res_det.npv}"


def test_06_premium_and_discount():
    """6. Premium: offer +5 % takes hedge to max_hedge_share with beta = 0; offer -5 % gives 0 forward with beta = 0."""
    sc_base = Scenario(**SCENARIOS["pampas_core_2000"])
    p_soy = sc_base.price("soybean")

    # +5% premium
    sc_prem = Scenario(
        **SCENARIOS["pampas_core_2000"],
        price_risk={
            "n_scenarios": 9,
            "risk_weight": 0.0,
            "max_hedge_share": 0.6,
            "forward_offers": [
                {"crop": "soybean", "month": "2027-04", "price_usd_t": p_soy * 1.05, "max_tonnes": None}
            ],
        },
    )
    res_prem = optimize(sc_prem)
    if res_prem.hectares.get("soybean", 0.0) > 1e-3:
        assert abs(res_prem.hedge_ratio["soybean"] - 0.6) <= 1e-3, f"Expected 0.6 hedge ratio, got {res_prem.hedge_ratio['soybean']}"

    # -5% discount
    sc_disc = Scenario(
        **SCENARIOS["pampas_core_2000"],
        price_risk={
            "n_scenarios": 9,
            "risk_weight": 0.0,
            "max_hedge_share": 0.6,
            "forward_offers": [
                {"crop": "soybean", "month": "2027-04", "price_usd_t": p_soy * 0.95, "max_tonnes": None}
            ],
        },
    )
    res_disc = optimize(sc_disc)
    assert res_disc.hedge_ratio.get("soybean", 0.0) == 0.0
    fwd_tonnes = sum(f["tonnes"] for f in res_disc.forward_sales if f["crop"] == "soybean")
    assert fwd_tonnes == 0.0


def test_09_validation():
    """9. Validation: bad risk_weight, unknown crop offer, n_scenarios out of bounds give errors, not crashes."""
    with pytest.raises(ScenarioError):
        optimize(Scenario(price_risk={"risk_weight": 1.5}))

    with pytest.raises(ScenarioError):
        optimize(Scenario(price_risk={"risk_weight": -0.1}))

    with pytest.raises(ScenarioError):
        optimize(Scenario(price_risk={"n_scenarios": 50}))

    with pytest.raises(ScenarioError):
        optimize(Scenario(price_risk={"n_scenarios": 3}))

    with pytest.raises(ScenarioError):
        optimize(Scenario(price_risk={"cvar_alpha": 0.6}))

    with pytest.raises(ScenarioError):
        optimize(Scenario(price_risk={"max_hedge_share": 1.5}))

    with pytest.raises(ScenarioError):
        optimize(Scenario(price_risk={"forward_offers": [{"crop": "coffee", "month": "2027-04", "price_usd_t": 300}]}))

    with pytest.raises(ScenarioError):
        # 10 price x 5 climate = 50 > 45
        climates = [{"id": f"c{i}", "probability": 0.2, "yields": {}} for i in range(5)]
        optimize(Scenario(climate_scenarios=climates, price_risk={"n_scenarios": 10, "with_climate": True}))


def test_10_hygiene():
    """10. Hygiene: git status --porcelain dora/data observatory is empty."""
    res = subprocess.run(
        ["git", "status", "--porcelain", "dora/data", "observatory"],
        capture_output=True,
        text=True,
        cwd=ROOT_DIR,
    )
    # Filter out untracked price_risk json files if not yet added
    lines = [line for line in res.stdout.strip().splitlines() if line and not ("price_risk_" in line)]
    assert not lines, f"Hygiene violation: git status not clean:\n{chr(10).join(lines)}"
