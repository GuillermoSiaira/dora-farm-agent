"""Acceptance tests for SPEC-25: Sowing dates and climate outlook.

Offline tests covering:
1. Exact equality to main when sowing_windows and climate_scenarios are omitted (6 scenarios).
2. Two identical windows split crop area arbitrarily with identical NPV to single window.
3. Late window with higher yield chosen under abundant capital, losing under scarce capital (checked against hand calculation).
4. Mass balance per crop with multiple harvest dates.
5. Machinery capacity staggers sowing, and dual lies between left and right derivatives.
6. climate_outlook reads snapshot and falls back to cache flagged.
7. climate_scenarios: matrix diagonal equals climate optimum, off-diagonal bounded by column diagonal.
8. Two-stage stochastic engine: 1 scenario (p=1) equals deterministic; expected NPV >= per-climate plans; perturbation test passes.
9. Agent with scripted model: question about climate/sowing dates calls climate_outlook and passes verifier.
"""
import json
from pathlib import Path
from types import SimpleNamespace as NS
import pytest

from dora.scenario import Scenario, CALENDAR, FORTNIGHTS
from dora.engine import optimize
from dora.tools import evaluate_season, shadow_prices, climate_scenarios, climate_outlook_tool
from dora.climate import climate_outlook
from dora.plan_check import evaluate_plan
from dora.agent import Agent

TESTS_DATA_DIR = Path(__file__).parent / "data"


def test_1_without_sowing_windows_and_climate_scenarios_matches_main():
    """Without sowing_windows or climate_scenarios, plan, NPV and duals equal main across 6 scenarios."""
    baseline_path = TESTS_DATA_DIR / "spec25_main_baseline.json"
    assert baseline_path.exists(), "tests/data/spec25_main_baseline.json must exist"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))

    scenarios = [
        Scenario(region="southeast_buenos_aires", area_ha=500, own_capital_usd=100000),
        Scenario(region="pampas_core", area_ha=400, own_capital_usd=80000),
        Scenario(region="iowa", area_ha=300, own_capital_usd=150000),
        Scenario(region="mato_grosso", area_ha=600, own_capital_usd=200000),
        Scenario(
            region="southeast_buenos_aires",
            area_ha=500,
            own_capital_usd=30000,
            credit_line_usd=50000,
            storage_options=[{"kind": "silo_bag"}],
            monthly_price_rise=0.03,
        ),
        Scenario(
            region="southeast_buenos_aires",
            area_ha=500,
            own_capital_usd=50000,
            payment_options=[{"id": "term_90d", "delay_fortnights": 6, "surcharge": 0.03}],
        ),
    ]

    for i, (sc, expected) in enumerate(zip(scenarios, baseline)):
        res = optimize(sc)
        assert abs(res.npv - expected["npv"]) < 1e-4, f"Scenario {i+1} NPV mismatch: {res.npv} vs {expected['npv']}"
        assert abs(res.land_shadow_price - expected["land_shadow_price"]) < 1e-4, f"Scenario {i+1} Land dual mismatch"
        assert abs(res.capital_shadow_price - expected["capital_shadow_price"]) < 1e-4, f"Scenario {i+1} Cap dual mismatch"
        for c in sc.crops:
            exp_h = expected["hectares"].get(c, 0.0)
            assert abs(res.hectares[c] - exp_h) < 1e-4, f"Scenario {i+1} {c} ha mismatch: {res.hectares[c]} vs {exp_h}"


def test_2_two_identical_windows_give_same_npv_and_total_area():
    """Two identical windows split crop area arbitrarily, but achieve identical NPV to 1 window."""
    s1 = Scenario(
        region="southeast_buenos_aires",
        area_ha=500,
        own_capital_usd=100000,
        crops=["corn"],
    )
    r1 = optimize(s1)

    s2 = Scenario(
        region="southeast_buenos_aires",
        area_ha=500,
        own_capital_usd=100000,
        crops=["corn"],
        sowing_windows={
            "corn": [
                {"id": "win_early_a", "sowing": 11, "harvest": 22, "yield_factor": 1.0},
                {"id": "win_early_b", "sowing": 11, "harvest": 22, "yield_factor": 1.0},
            ]
        },
    )
    r2 = optimize(s2)

    assert abs(r1.npv - r2.npv) < 1e-4
    total_corn_ha = sum(r2.hectares_by_window["corn"].values())
    assert abs(total_corn_ha - r1.hectares["corn"]) < 1e-4


def test_3_late_window_higher_yield_capital_abundant_vs_scarce_hand_calculation():
    """Late window with higher yield is preferred with abundant capital; scarce capital chooses earlier window for liquidity."""
    # Under abundant capital (200k USD), early corn gives 8.0 t/ha at f20, late corn gives 9.5 t/ha at f26.
    # Hand calculation:
    # Early revenue: 8.0 * net_price(f20) = 8.0 * 200.0 = 1600 USD/ha.
    # Late revenue:  9.5 * net_price(f26) = 9.5 * 200.0 = 1900 USD/ha.
    # Late corn delivers ~300 USD/ha more revenue, far exceeding the small time discount (~1% over 6 fortnights).
    s_abundant = Scenario(
        region="southeast_buenos_aires",
        area_ha=500,
        own_capital_usd=200000,
        crops=["corn"],
        sowing_windows={
            "corn": [
                {"id": "early", "sowing": 11, "harvest": 20, "yield_t_ha": 8.0},
                {"id": "late", "sowing": 15, "harvest": 26, "yield_t_ha": 9.5},
            ]
        },
    )
    r_ab = optimize(s_abundant)
    # Rotation caps corn at 250 ha (50% of 500 ha). All allocated to late corn.
    assert abs(r_ab.hectares_by_window["corn"]["late"] - 250.0) < 1e-4
    assert r_ab.hectares_by_window["corn"]["early"] < 1e-4

    # Under scarce capital (15,000 USD, 0 credit line), planting late corn leaves 0 cash inflow until fortnight 26.
    # Early corn harvests at f20, generating early cash that avoids early insolvency.
    s_scarce = Scenario(
        region="southeast_buenos_aires",
        area_ha=500,
        own_capital_usd=15000,
        credit_line_usd=0,
        crops=["corn"],
        sowing_windows={
            "corn": [
                {"id": "early", "sowing": 11, "harvest": 20, "yield_t_ha": 8.0},
                {"id": "late", "sowing": 15, "harvest": 26, "yield_t_ha": 9.5},
            ]
        },
    )
    r_sc = optimize(s_scarce)
    # Early corn must receive positive area to provide liquidity before f26
    assert r_sc.hectares_by_window["corn"]["early"] > 0.0


def test_4_mass_balance_per_crop_with_several_harvest_dates():
    """Mass balance per crop: total harvest equals sales + forward sales + storage shrink."""
    s4 = Scenario(
        region="southeast_buenos_aires",
        area_ha=500,
        own_capital_usd=100000,
        crops=["corn"],
        sowing_windows={
            "corn": [
                {"id": "early", "sowing": 11, "harvest": 20, "yield_t_ha": 8.0},
                {"id": "late", "sowing": 15, "harvest": 24, "yield_t_ha": 8.5},
            ]
        },
        sowing_capacity_ha_per_fortnight=125.0,
    )
    r4 = optimize(s4)
    win_map = s4.resolved_sowing_windows()
    total_prod = sum(
        r4.hectares_by_window["corn"][w["id"]] * float(w.get("yield_t_ha") or (s4.crop_yield("corn") * float(w.get("yield_factor", 1.0))))
        for w in win_map["corn"]
    )
    total_sales = sum(r4.sales["corn"].values())
    total_shrink = sum(opt_info["shrink_by_crop"].get("corn", 0.0) for opt_info in r4.storage_by_option.values())
    assert abs(total_prod - (total_sales + total_shrink)) < 1e-4


def test_5_machinery_capacity_staggers_sowing_and_dual_between_finite_differences():
    """Planter capacity below area forces staggering; dual of capacity lies between finite differences."""
    cap = 120.0
    s5 = Scenario(
        region="southeast_buenos_aires",
        area_ha=150,
        own_capital_usd=100000,
        crops=["corn"],
        max_crop_share=1.0,
        sowing_windows={
            "corn": [
                {"id": "early", "sowing": 11, "harvest": 20, "yield_t_ha": 9.0},
                {"id": "late", "sowing": 15, "harvest": 24, "yield_t_ha": 8.0},
            ]
        },
        sowing_capacity_ha_per_fortnight=cap,
    )
    r5 = optimize(s5)
    # Early corn has higher yield (9.0 vs 8.0), so it hits the planter capacity (120 ha).
    # The remaining 30 ha is staggered into the late window (sowing 15).
    assert abs(r5.hectares_by_window["corn"]["early"] - cap) < 1e-4
    assert abs(r5.hectares_by_window["corn"]["late"] - (150 - cap)) < 1e-4

    dual_11 = r5.sowing_capacity_shadow_prices.get(11, 0.0)
    assert dual_11 > 0.0

    # Perturbation +1 ha
    s5_plus = Scenario(
        region="southeast_buenos_aires",
        area_ha=150,
        own_capital_usd=100000,
        crops=["corn"],
        max_crop_share=1.0,
        sowing_windows={
            "corn": [
                {"id": "early", "sowing": 11, "harvest": 20, "yield_t_ha": 9.0},
                {"id": "late", "sowing": 15, "harvest": 24, "yield_t_ha": 8.0},
            ]
        },
        sowing_capacity_ha_per_fortnight=cap + 1.0,
    )
    r5_plus = optimize(s5_plus)
    d_plus = r5_plus.npv - r5.npv

    # Perturbation -1 ha
    s5_minus = Scenario(
        region="southeast_buenos_aires",
        area_ha=150,
        own_capital_usd=100000,
        crops=["corn"],
        max_crop_share=1.0,
        sowing_windows={
            "corn": [
                {"id": "early", "sowing": 11, "harvest": 20, "yield_t_ha": 9.0},
                {"id": "late", "sowing": 15, "harvest": 24, "yield_t_ha": 8.0},
            ]
        },
        sowing_capacity_ha_per_fortnight=cap - 1.0,
    )
    r5_minus = optimize(s5_minus)
    d_minus = r5.npv - r5_minus.npv

    assert d_plus - 0.01 <= dual_11 <= d_minus + 0.01


def test_6_climate_outlook_reads_snapshot_and_falls_back_to_cache():
    """climate_outlook reads stored snapshot and falls back cleanly to offline cache with flag."""
    res = climate_outlook("southeast_buenos_aires")
    assert res["region"] == "southeast_buenos_aires"
    assert "below_normal" in res["rainfall_probabilities"]
    assert "near_normal" in res["rainfall_probabilities"]
    assert "above_normal" in res["rainfall_probabilities"]
    assert res.get("from_cache") is True
    assert res.get("placeholder") is True          # not read from the issuing service yet (review of 30/10)
    assert "smn" in res["source"].lower()
    assert res["url"] == "https://www.smn.gob.ar/clima/perspectiva"


def test_7_climate_scenarios_diagonal_optimal_and_off_diagonal_bounded():
    """climate_scenarios: matrix diagonal equals climate optimum, and every off-diagonal is at most column diagonal."""
    scenario = {"area_ha": 500, "own_capital_usd": 100000, "region": "southeast_buenos_aires"}
    res = climate_scenarios(scenario)
    M = res["payoff_matrix"]
    climates = ["dry", "normal", "wet"]
    for c in climates:
        opt_c = res["plans"][c]["npv_usd"]
        assert abs(M[c][c] - opt_c) < 1e-2, f"Diagonal M[{c}][{c}]={M[c][c]} != opt={opt_c}"
        for other in climates:
            assert M[other][c] <= M[c][c] + 1e-2, f"Plan {other} in {c} exceeds optimum: {M[other][c]} > {M[c][c]}"

    # Check regret matrix: diagonal is zero, off-diagonal >= 0
    R = res["regret_matrix"]
    for c in climates:
        assert abs(R[c][c]) < 1e-2
        for other in climates:
            assert R[other][c] >= -1e-2


def test_8_stochastic_engine_one_scenario_equals_deterministic_and_expected_npv_optimal():
    """Two-stage stochastic engine: 1 scenario (p=1) equals deterministic; expected NPV >= per-climate plans; duals pass perturbation."""
    # 1. One scenario of prob 1 equals deterministic engine exactly
    sc_det = Scenario(region="southeast_buenos_aires", area_ha=500, own_capital_usd=100000)
    r_det = optimize(sc_det)

    sc_stoch_1 = Scenario(
        region="southeast_buenos_aires",
        area_ha=500,
        own_capital_usd=100000,
        climate_scenarios=[
            {"id": "normal", "probability": 1.0, "yields": {c: sc_det.crop_yield(c) for c in sc_det.crops}}
        ],
    )
    r_stoch_1 = optimize(sc_stoch_1)
    assert abs(r_det.npv - r_stoch_1.npv) < 1e-4
    assert abs(r_det.land_shadow_price - r_stoch_1.land_shadow_price) < 1e-4
    assert abs(r_det.capital_shadow_price - r_stoch_1.capital_shadow_price) < 1e-4

    # 2. Expected NPV >= every per-climate plan evaluated in all climates
    sc3_scenarios = [
        {"id": "dry", "probability": 0.45, "yields": {"wheat": 3.0, "corn": 6.5, "soybean": 2.0, "sunflower": 1.8}},
        {"id": "normal", "probability": 0.35, "yields": {"wheat": 3.5, "corn": 7.5, "soybean": 2.5, "sunflower": 2.0}},
        {"id": "wet", "probability": 0.20, "yields": {"wheat": 3.85, "corn": 8.6, "soybean": 2.88, "sunflower": 2.1}},
    ]
    cap = 200000.0
    sc_stoch = Scenario(region="southeast_buenos_aires", area_ha=500, own_capital_usd=cap, climate_scenarios=sc3_scenarios)
    r_stoch = optimize(sc_stoch)

    probs = {"dry": 0.45, "normal": 0.35, "wet": 0.20}
    clim_scenarios_obj = {
        c_info["id"]: Scenario(region="southeast_buenos_aires", area_ha=500, own_capital_usd=cap, yields=c_info["yields"])
        for c_info in sc3_scenarios
    }
    opt_plans = {cid: optimize(sc_obj) for cid, sc_obj in clim_scenarios_obj.items()}

    for plan_id, plan_res in opt_plans.items():
        exp_npv = 0.0
        for clim_id, sc_obj in clim_scenarios_obj.items():
            ev = evaluate_plan(sc_obj, plan_res.hectares)
            assert ev["feasible"], f"Plan {plan_id} infeasible in {clim_id}"
            exp_npv += probs[clim_id] * ev["npv_plan_usd"]
        assert r_stoch.npv >= exp_npv - 0.01

    # 3. Perturbation test for capital and land duals in stochastic engine
    r_cap_plus = optimize(Scenario(
        region="southeast_buenos_aires",
        area_ha=500,
        own_capital_usd=cap + 1.0,
        climate_scenarios=sc3_scenarios,
    ))
    r_cap_minus = optimize(Scenario(
        region="southeast_buenos_aires",
        area_ha=500,
        own_capital_usd=cap - 1.0,
        climate_scenarios=sc3_scenarios,
    ))
    d_cap_plus = r_cap_plus.npv - r_stoch.npv
    d_cap_minus = r_stoch.npv - r_cap_minus.npv
    cap_sp = r_stoch.capital_shadow_price
    assert d_cap_plus - 1.0 - 0.01 <= cap_sp <= d_cap_minus - 1.0 + 0.01

    r_land_plus = optimize(Scenario(
        region="southeast_buenos_aires",
        area_ha=501.0,
        own_capital_usd=cap,
        climate_scenarios=sc3_scenarios,
    ))
    r_land_minus = optimize(Scenario(
        region="southeast_buenos_aires",
        area_ha=499.0,
        own_capital_usd=cap,
        climate_scenarios=sc3_scenarios,
    ))
    d_land_plus = r_land_plus.npv - r_stoch.npv
    d_land_minus = r_stoch.npv - r_land_minus.npv
    land_sp = r_stoch.land_shadow_price
    assert d_land_plus - 0.01 <= land_sp <= d_land_minus + 0.01


def test_9_agent_scripted_model_sowing_dates_calls_climate_outlook_and_passes_verifier():
    """Agent with scripted model: question on sowing dates and climate calls climate_outlook and passes verifier."""
    class ScriptedModel:
        def __init__(self, script):
            self.script = list(script)
            self.seen = []
            self.chat = NS(completions=NS(create=self.create))

        def create(self, model, messages, tools):
            self.seen.append(list(messages))
            step = self.script.pop(0)
            msg = NS(content=None, tool_calls=step) if isinstance(step, list) else NS(content=step, tool_calls=None)
            return NS(choices=[NS(message=msg)])

    def tool_call(name, args, i=1):
        return NS(id=f"call_{i}", function=NS(name=name, arguments=json.dumps(args)))

    outlook_call = tool_call("climate_outlook", {"region": "southeast_buenos_aires"})
    outlook_res = climate_outlook("southeast_buenos_aires")
    p_dry = round(outlook_res["rainfall_probabilities"]["below_normal"] * 100)
    p_norm = round(outlook_res["rainfall_probabilities"]["near_normal"] * 100)
    p_wet = round(outlook_res["rainfall_probabilities"]["above_normal"] * 100)

    agent_answer = (
        f"Para el trimestre noviembre-enero en Balcarce, el SMN pronostica un {p_dry}% de probabilidad "
        f"de precipitación inferior a lo normal (seco), {p_norm}% normal y {p_wet}% superior a lo normal."
    )

    model = ScriptedModel([[outlook_call], agent_answer])
    agent = Agent(client=model, model="test", use_verifier=True)
    reply = agent.ask("¿Cómo viene el clima para la siembra en Balcarce?")

    assert reply.verified
    assert len(reply.tool_calls) == 1
    assert reply.tool_calls[0]["tool"] == "climate_outlook"
    assert "45%" in reply.text or "45 %" in reply.text



def test_10_second_crop_shares_land_after_wheat_total_land_is_wheat_not_sum():
    """(a) With wheat and second-crop soybean both profitable, plan sows them on same ha and land used is wheat area."""
    from dora.tools import evaluate_season
    sc = Scenario(
        region="southeast_buenos_aires",
        area_ha=200,
        owned_ha=200,
        own_capital_usd=200_000,
        crops=["wheat", "soybean"],
        max_crop_share=1.0,
        sowing_windows={
            "wheat": [{"id": "standard", "sowing": 3, "harvest": 15, "yield_t_ha": 5.0, "placeholder": False}],
            "soybean": [
                {"id": "first_crop", "sowing": 13, "harvest": 23, "yield_t_ha": 2.0, "placeholder": False},
                {"id": "second_crop", "after": "wheat", "sowing": 16, "harvest": 24, "yield_t_ha": 2.5, "placeholder": False},
            ],
        },
    )
    r = optimize(sc)
    # Both wheat and second-crop soybean sown on the full 200 ha
    assert r.hectares["wheat"] == pytest.approx(200.0, abs=1e-3)
    assert r.hectares_by_window["soybean"]["second_crop"] == pytest.approx(200.0, abs=1e-3)
    assert r.double_cropped_ha["wheat/soybean"] == pytest.approx(200.0, abs=1e-3)
    # Total crop hectares is 400 (200 wheat + 200 soybean), but physical land used is 200 ha
    assert sum(r.hectares.values()) == 400.0
    ev = evaluate_season({
        "region": "southeast_buenos_aires",
        "area_ha": 200,
        "owned_ha": 200,
        "own_capital_usd": 200_000,
        "crops": ["wheat", "soybean"],
        "max_crop_share": 1.0,
        "sowing_windows": sc.sowing_windows,
    })
    assert ev["unsown_ha"] == pytest.approx(0.0, abs=1e-3)


def test_11_second_crop_soybean_never_exceeds_wheat():
    """(b) Second-crop soybean area is bounded by wheat area sown."""
    sc = Scenario(
        region="southeast_buenos_aires",
        area_ha=200,
        owned_ha=200,
        own_capital_usd=200_000,
        crops=["wheat", "soybean"],
        max_crop_share=1.0,
        constraints=[{"type": "max_area", "crop": "wheat", "ha": 120.0}],
        sowing_windows={
            "wheat": [{"id": "standard", "sowing": 3, "harvest": 15, "yield_t_ha": 5.0, "placeholder": False}],
            "soybean": [
                {"id": "first_crop", "sowing": 13, "harvest": 23, "yield_t_ha": 2.0, "placeholder": False},
                {"id": "second_crop", "after": "wheat", "sowing": 16, "harvest": 24, "yield_t_ha": 2.5, "placeholder": False},
            ],
        },
    )
    r = optimize(sc)
    # Wheat is capped at 120 ha
    assert r.hectares["wheat"] == pytest.approx(120.0, abs=1e-3)
    # Second-crop soybean cannot exceed 120 ha
    assert r.hectares_by_window["soybean"]["second_crop"] <= r.hectares["wheat"] + 1e-6
    assert r.hectares_by_window["soybean"]["second_crop"] == pytest.approx(120.0, abs=1e-3)
    assert r.double_cropped_ha["wheat/soybean"] == pytest.approx(120.0, abs=1e-3)


def test_12_dual_of_after_row_passes_perturbation_test():
    """(c) The dual of the 'after' row passes the perturbation test."""
    from dataclasses import replace
    sc = Scenario(
        region="southeast_buenos_aires",
        area_ha=200,
        owned_ha=200,
        own_capital_usd=200_000,
        crops=["wheat", "soybean"],
        max_crop_share=1.0,
        constraints=[{"type": "max_area", "crop": "wheat", "ha": 120.0}],
        sowing_windows={
            "wheat": [{"id": "standard", "sowing": 3, "harvest": 15, "yield_t_ha": 5.0, "placeholder": False}],
            "soybean": [
                {"id": "first_crop", "sowing": 13, "harvest": 23, "yield_t_ha": 2.0, "placeholder": False},
                {"id": "second_crop", "after": "wheat", "sowing": 16, "harvest": 24, "yield_t_ha": 2.5, "placeholder": False},
            ],
        },
    )
    r = optimize(sc)
    dual = r.double_crop_shadow_prices["wheat"]
    assert dual > 0.0

    # Perturb the after row RHS with +1.0 ha
    r_plus = optimize(replace(sc, double_crop_slack_ha=1.0))
    d_plus = r_plus.npv - r.npv

    # Perturb the after row RHS with -1.0 ha
    r_minus = optimize(replace(sc, double_crop_slack_ha=-1.0))
    d_minus = r.npv - r_minus.npv

    assert d_plus - 0.01 <= dual <= d_minus + 0.01
    assert abs(d_plus - dual) < 1e-2


def test_13_second_crop_sowing_before_harvest_rejected():
    """A window declaring 'after' with sowing before preceding harvest is rejected."""
    from dora.scenario import ScenarioError
    sc = Scenario(
        region="southeast_buenos_aires",
        area_ha=200,
        sowing_windows={
            "soybean": [
                {"id": "second_crop", "after": "wheat", "sowing": 14, "harvest": 24, "yield_t_ha": 2.0},
            ],
        },
    )
    with pytest.raises(ScenarioError, match="before harvest"):
        optimize(sc)
