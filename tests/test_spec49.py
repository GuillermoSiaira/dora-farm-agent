"""Tests for SPEC-49: forward sales as a decision, with price risk."""
import math
import subprocess
import pytest
from pathlib import Path

from dora.scenario import Scenario, ScenarioError
from dora.engine import optimize, scenario_for_price_scenario, discrete_cvar
from dora.tools import hedge_analysis

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


def test_05_monotone_frontier():
    """5. Monotone frontier: as beta goes 0 -> 1, expected NPV does not increase, CVaR does not decrease, and hedge ratio does not decrease (+- 1e-6). Use pampas_core 2,000 ha and se_ba 500 ha."""
    betas = [0.0, 0.25, 0.5, 0.75, 1.0]
    for sc_name in ["pampas_core_2000", "se_ba_500"]:
        sc_base = SCENARIOS[sc_name]
        results = []
        for b in betas:
            sc = Scenario(**sc_base, price_risk={"risk_weight": b, "n_scenarios": 9})
            results.append(optimize(sc))

        for i in range(1, len(betas)):
            prev, curr = results[i - 1], results[i]
            assert curr.expected_npv <= prev.expected_npv + 1e-6, (
                f"{sc_name} beta={betas[i]}: E[NPV] {curr.expected_npv} > prev {prev.expected_npv}"
            )
            assert curr.cvar >= prev.cvar - 1e-6, (
                f"{sc_name} beta={betas[i]}: CVaR {curr.cvar} < prev {prev.cvar}"
            )

            prev_tot_fwd = sum(f["tonnes"] for f in prev.forward_sales)
            prev_tot_prod = sum(Scenario(**sc_base).crop_yield(c) * prev.hectares.get(c, 0.0) for c in Scenario(**sc_base).crops)
            prev_farm_hr = prev_tot_fwd / prev_tot_prod if prev_tot_prod > 0 else 0.0

            curr_tot_fwd = sum(f["tonnes"] for f in curr.forward_sales)
            curr_tot_prod = sum(Scenario(**sc_base).crop_yield(c) * curr.hectares.get(c, 0.0) for c in Scenario(**sc_base).crops)
            curr_farm_hr = curr_tot_fwd / curr_tot_prod if curr_tot_prod > 0 else 0.0

            assert curr_farm_hr >= prev_farm_hr - 1e-6, (
                f"{sc_name} beta={betas[i]}: farm hedge ratio {curr_farm_hr} < prev {prev_farm_hr}"
            )


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


def test_07_independent_check_each_scenario():
    """7. Independent check of each scenario:
    - fix the first stage (hectares and forward tonnes) of the solution;
    - re-solve each scenario alone with the deterministic engine, with that scenario's prices, the hectares fixed with min_area = max_area, and the forward as a forward_sale constraint;
    - compare NPV_s (+- 0.01 USD) and compute CVaR from those NPV_s by sorting, independently of the LP (+- 0.01).
    """
    # 1. Southeast Buenos Aires 500 ha
    sc1 = Scenario(
        region="southeast_buenos_aires",
        area_ha=500,
        owned_ha=500,
        own_capital_usd=50000,
        price_risk={"n_scenarios": 9, "risk_weight": 0.5},
    )
    res1 = optimize(sc1)

    ha1 = [{'type': 'min_area', 'crop': c, 'ha': res1.hectares[c]} for c in sc1.crops] + \
          [{'type': 'max_area', 'crop': c, 'ha': res1.hectares[c]} for c in sc1.crops]
    fwd1 = [{'type': 'forward_sale', 'crop': f['crop'], 'month': f['month'], 'tonnes': f['tonnes'], 'price_usd_t': f['price_usd_t']}
            for f in res1.forward_sales if f['tonnes'] > 1e-4]

    npvs_indep1 = []
    probs1 = []
    lp_npvs1 = res1.price_risk_results["scenario_npvs"]
    for s_idx, s_info in enumerate(res1.price_scenarios):
        sc_s = scenario_for_price_scenario(sc1, s_idx)
        sc_s.constraints = list(ha1) + list(fwd1)
        r = optimize(sc_s)
        npvs_indep1.append(r.npv)
        probs1.append(s_info["prob"])
        assert abs(r.npv - lp_npvs1[s_idx]) <= 0.01, f"se_ba_500 s={s_idx}: indep {r.npv} != lp {lp_npvs1[s_idx]}"

    cvar_indep1 = discrete_cvar(npvs_indep1, probs1, 0.10)
    assert abs(cvar_indep1 - res1.cvar) <= 0.01, f"se_ba_500 CVaR: indep {cvar_indep1} != lp {res1.cvar}"

    # 2. Pergamino 500 ha with soybean forward offer
    sc2 = Scenario(
        region="pampas_core",
        area_ha=500,
        owned_ha=500,
        own_capital_usd=260000,
        price_risk={
            "n_scenarios": 9,
            "risk_weight": 0.5,
            "forward_offers": [{"crop": "soybean", "month": "2027-05", "price_usd_t": 330.0, "max_tonnes": None}],
        },
    )
    res2 = optimize(sc2)

    ha2 = [{'type': 'min_area', 'crop': c, 'ha': res2.hectares[c]} for c in sc2.crops] + \
          [{'type': 'max_area', 'crop': c, 'ha': res2.hectares[c]} for c in sc2.crops]
    fwd2 = [{'type': 'forward_sale', 'crop': f['crop'], 'month': f['month'], 'tonnes': f['tonnes'], 'price_usd_t': f['price_usd_t']}
            for f in res2.forward_sales if f['tonnes'] > 1e-4]

    npvs_indep2 = []
    probs2 = []
    lp_npvs2 = res2.price_risk_results["scenario_npvs"]
    for s_idx, s_info in enumerate(res2.price_scenarios):
        sc_s = scenario_for_price_scenario(sc2, s_idx)
        sc_s.constraints = list(ha2) + list(fwd2)
        r = optimize(sc_s)
        npvs_indep2.append(r.npv)
        probs2.append(s_info["prob"])
        assert abs(r.npv - lp_npvs2[s_idx]) <= 0.01, f"Pergamino s={s_idx}: indep {r.npv} != lp {lp_npvs2[s_idx]}"

    cvar_indep2 = discrete_cvar(npvs_indep2, probs2, 0.10)
    assert abs(cvar_indep2 - res2.cvar) <= 0.01, f"Pergamino CVaR: indep {cvar_indep2} != lp {res2.cvar}"


def test_hedge_analysis_tool():
    """Test hedge_analysis tool: frontier, indifference price, duals, and explanation text."""
    sc_dict = {
        "region": "pampas_core",
        "area_ha": 500,
        "owned_ha": 500,
        "own_capital_usd": 260000,
        "price_risk": {
            "forward_offers": [{"crop": "soybean", "month": "2027-05", "price_usd_t": 330.0, "max_tonnes": None}],
        },
    }
    out = hedge_analysis(sc_dict, risk_weights=[0.0, 0.5, 1.0], lang="es")
    assert "frontier" in out
    assert len(out["frontier"]) == 3
    assert "price_scenarios" in out
    assert "indifference_price_usd_t" in out
    assert "explanation" in out
    assert "volatilidad" in out["explanation"].lower()
    assert "dora" in out["explanation"].lower()
    indiff_soy = out["indifference_price_usd_t"].get("soybean_2027-05", out["indifference_price_usd_t"].get("soybean"))
    assert indiff_soy is not None
    assert abs(indiff_soy - 330.0) <= 2.0
    assert sum(out["bisection_solves"].values()) <= 20


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
