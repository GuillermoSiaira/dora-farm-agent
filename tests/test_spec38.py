"""Tests for SPEC-38: owned land can be rented out at zone rent, tenure comparison."""
import json
import pytest
from dora.scenario import Scenario
from dora.engine import optimize, _optimize_stochastic
from dora.tools import evaluate_season
from app import run_scenario


def test_1_southeast_buenos_aires_budget_rent():
    """1. Owned 500 ha Southeast Buenos Aires, 50,000 USD: regional_rent_usd_ha > 0,
    regional_rent_source names the budget file, regional_rent_placeholder as decided in 1."""
    sc = Scenario(
        region="southeast_buenos_aires",
        area_ha=500.0,
        own_capital_usd=50_000.0,
    )
    assert sc.regional_rent_usd_ha == pytest.approx(425.1, abs=0.01)
    assert "magyp_southeast_2026-06.json" in sc.regional_rent_source
    assert sc.regional_rent_placeholder is False


def test_2_regression_guard_allow_rent_out_false():
    """2. Same with allow_rent_out: false: NPV, hectares and sales equal to current main."""
    sc = Scenario(
        region="southeast_buenos_aires",
        area_ha=500.0,
        own_capital_usd=50_000.0,
        allow_rent_out=False,
    )
    r = optimize(sc)
    # Stored values from main (regression guard)
    assert r.npv == pytest.approx(88186.5968, abs=1e-3)
    assert r.hectares["wheat"] == pytest.approx(121.7228, abs=1e-3)
    assert r.hectares["soybean"] == pytest.approx(250.0, abs=1e-3)
    assert r.hectares["corn"] == pytest.approx(0.0, abs=1e-4)
    assert r.hectares["sunflower"] == pytest.approx(0.0, abs=1e-4)
    assert r.sales["wheat"][15] == pytest.approx(500.2806, abs=1e-3)
    assert r.sales["soybean"][23] == pytest.approx(610.0, abs=1e-3)


def test_3_rent_too_low_rents_nothing():
    """3. Same with regional_rent_usd_ha: 0.01: no land rented out (rent too low), plan equal to test 2."""
    sc = Scenario(
        region="southeast_buenos_aires",
        area_ha=500.0,
        own_capital_usd=50_000.0,
        regional_rent_usd_ha=0.01,
    )
    r = optimize(sc)
    assert r.rent_out_ha == pytest.approx(0.0, abs=1e-4)
    assert r.npv == pytest.approx(88186.5968, abs=1e-3)
    assert r.hectares["wheat"] == pytest.approx(121.7228, abs=1e-3)
    assert r.hectares["soybean"] == pytest.approx(250.0, abs=1e-3)


def test_4_high_rent_rents_all():
    """4. Same with regional_rent_usd_ha: 2000: all 500 ha rented out, best == 'rent_out',
    NPV = own capital + 500 * 2000 * (1 - transaction tax rate) - land tax * 500, to the cent."""
    sc = Scenario(
        region="southeast_buenos_aires",
        area_ha=500.0,
        own_capital_usd=50_000.0,
        regional_rent_usd_ha=2000.0,
        allow_rent_out=True,
    )
    r = optimize(sc)
    assert r.rent_out_ha == pytest.approx(500.0, abs=1e-4)
    # Formula from SPEC-38:
    expected_npv = sc.own_capital_usd + 500.0 * 2000.0 * (1.0 - sc.transaction_tax_rate) - sc.land_tax_usd_ha_year * 500.0
    assert r.npv == pytest.approx(expected_npv, abs=1e-2)
    assert r.npv == pytest.approx(1_050_000.0, abs=1e-2)

    ev = evaluate_season({
        "region": "southeast_buenos_aires",
        "area_ha": 500.0,
        "own_capital_usd": 50_000.0,
        "regional_rent_usd_ha": 2000.0,
        "allow_rent_out": True,
    })
    assert ev.get("tenure_comparison", {}).get("best") == "rent_out"


def test_5_tenure_comparison_components():
    """5. tenure_comparison.farm_only_npv_usd equals test 2's NPV;
    rent_all_npv_usd equals the NPV of the scenario with every crop capped at 0."""
    ev = evaluate_season({
        "region": "southeast_buenos_aires",
        "area_ha": 500.0,
        "own_capital_usd": 50_000.0,
    })
    tc = ev["tenure_comparison"]
    # farm_only_npv_usd matches test 2
    assert tc["farm_only_npv_usd"] == pytest.approx(88186.6, abs=0.1)

    # rent_all_npv_usd matches scenario with all crops capped at 0
    sc_cap0 = Scenario(
        region="southeast_buenos_aires",
        area_ha=500.0,
        own_capital_usd=50_000.0,
        allow_rent_out=True,
        constraints=[{"type": "max_area", "crop": c, "ha": 0.0} for c in ("wheat", "corn", "soybean", "sunflower")],
    )
    r_cap0 = optimize(sc_cap0)
    assert tc["rent_all_npv_usd"] == pytest.approx(r_cap0.npv, abs=0.1)


def test_6_pampas_core_conservation_of_land_and_max_rent_out():
    """6. Pampas core 2,000 ha, 500,000 USD: rent_out_ha + sum(hectares) + unsown_ha == 2000 (± 0.1),
    and NPV >= farm-only NPV. Pampas core 2,000 ha with max_rent_out_ha: 1000 rents out <= 1000 ha
    and its NPV lies between farm-only and free plan."""
    sc = Scenario(
        region="pampas_core",
        area_ha=2000.0,
        own_capital_usd=500_000.0,
    )
    r = optimize(sc)
    ev = evaluate_season({
        "region": "pampas_core",
        "area_ha": 2000.0,
        "own_capital_usd": 500_000.0,
    })
    tot_land = r.rent_out_ha + sum(r.hectares.values()) + ev["unsown_ha"]
    assert tot_land == pytest.approx(2000.0, abs=0.1)
    farm_only_npv = ev["tenure_comparison"]["farm_only_npv_usd"]
    assert r.npv >= farm_only_npv - 1e-4

    # max_rent_out_ha: 1000
    sc_max = Scenario(
        region="pampas_core",
        area_ha=2000.0,
        own_capital_usd=500_000.0,
        max_rent_out_ha=1000.0,
    )
    r_max = optimize(sc_max)
    assert r_max.rent_out_ha <= 1000.0 + 1e-4
    assert farm_only_npv <= r_max.npv <= r.npv + 1e-4


def test_7_rented_farm_unchanged_and_no_tenure_comparison():
    """7. A rented farm (rented_land: true, no owned land): output unchanged from main
    and no tenure_comparison."""
    sc = Scenario(
        region="southeast_buenos_aires",
        area_ha=500.0,
        rented_land=True,
        own_capital_usd=50_000.0,
    )
    r = optimize(sc)
    assert r.npv == pytest.approx(50000.0, abs=1e-2)
    assert sum(r.hectares.values()) == pytest.approx(0.0, abs=1e-4)

    ev = evaluate_season({
        "region": "southeast_buenos_aires",
        "area_ha": 500.0,
        "rented_land": True,
        "own_capital_usd": 50_000.0,
    })
    assert "tenure_comparison" not in ev


def test_8_stochastic_allow_rent_out_false_rents_nothing():
    """8. _optimize_stochastic with allow_rent_out: false rents nothing."""
    sc = Scenario(
        region="southeast_buenos_aires",
        area_ha=500.0,
        own_capital_usd=50_000.0,
        allow_rent_out=False,
        climate_scenarios=[
            {"name": "normal", "prob": 0.5, "yields": {"wheat": 3.0, "corn": 6.0, "soybean": 2.5, "sunflower": 2.0}},
            {"name": "dry", "prob": 0.5, "yields": {"wheat": 2.0, "corn": 4.0, "soybean": 1.8, "sunflower": 1.5}},
        ],
    )
    r = _optimize_stochastic(sc)
    assert r.rent_out_ha == pytest.approx(0.0, abs=1e-4)


def test_9_app_plan_text(monkeypatch):
    """9. App: with a hand-made evaluate_season result (rent_out 623.5 ha, rent 570, comparison present)
    the plan text has Dado en alquiler: 623,5 ha a 570 USD/ha and the comparison line;
    with regional_rent_placeholder: true it has alquiler estimado."""
    mock_eval = {
        "npv_usd": 1640000.0,
        "unsown_ha": 0.0,
        "max_credit_usd": 0.0,
        "debt": [0.0],
        "hectares": {"wheat": 0.0, "corn": 0.0, "soybean": 0.0, "sunflower": 0.0},
        "regional_rent_usd_ha": 570.0,
        "regional_rent_placeholder": False,
        "rent_out_income_usd": 355395.0,
        "land_tenure": {
            "rent_out_ha": 623.5,
            "owned_ha": 2000.0,
        },
        "tenure_comparison": {
            "farm_only_npv_usd": 1157834.52,
            "rent_all_npv_usd": 1640000.0,
            "best": "mix",
            "gain_vs_farm_only_usd": 482165.48,
        },
    }

    def fake_run_tool(name, payload_json):
        if name == "evaluate_season":
            return json.dumps(mock_eval)
        elif name == "shadow_prices":
            return json.dumps({"land": {}, "capital": {"rates_per_fortnight": []}})
        elif name == "build_scenario":
            return json.dumps({"scenario": {}})
        elif name == "tax_wedge":
            return json.dumps({"taxes": []})
        return "{}"

    monkeypatch.setattr("app.run_tool", fake_run_tool)
    res = run_scenario(area_ha=2000, crops=["wheat", "corn", "soybean", "sunflower"], own_capital_usd=500000, lang="es")
    plan = res["plan"]
    assert "Dado en alquiler" in plan
    assert "623,5 ha a 570 USD/ha" in plan
    assert "Dado en alquiler: 623,5 ha a 570 USD/ha" in plan.replace("**", "")
    assert "Sembrando todo lo que alcanza:" in plan
    assert "Alquilando todo:" in plan
    assert "El plan elige una combinación de siembra y alquiler." in plan
    assert "alquiler estimado" not in plan

    # Placeholder case
    mock_eval_ph = dict(mock_eval, regional_rent_placeholder=True)
    def fake_run_tool_ph(name, payload_json):
        if name == "evaluate_season":
            return json.dumps(mock_eval_ph)
        elif name == "shadow_prices":
            return json.dumps({"land": {}, "capital": {"rates_per_fortnight": []}})
        elif name == "build_scenario":
            return json.dumps({"scenario": {}})
        elif name == "tax_wedge":
            return json.dumps({"taxes": []})
        return "{}"

    monkeypatch.setattr("app.run_tool", fake_run_tool_ph)
    res_ph = run_scenario(area_ha=2000, crops=["wheat", "corn", "soybean", "sunflower"], own_capital_usd=500000, lang="es")
    assert "alquiler estimado" in res_ph["plan"]


def test_10_break_even_rent():
    """10. break_even_rent_usd_ha: with that rent passed as regional_rent_usd_ha and allow_rent_out: True,
    the plan's NPV equals farm_only within 1 USD."""
    ev = evaluate_season({
        "region": "pampas_core",
        "area_ha": 100.0,
        "own_capital_usd": 100_000.0,
        "crops": ["soybean"],
        "max_crop_share": 1.0,
        "price_curve_source": "rosario_2026-10-27",
    })
    tc = ev["tenure_comparison"]
    be_rent = tc["break_even_rent_usd_ha"]
    farm_only_npv = tc["farm_only_npv_usd"]

    sc_be = Scenario(
        region="pampas_core",
        area_ha=100.0,
        own_capital_usd=100_000.0,
        crops=["soybean"],
        max_crop_share=1.0,
        price_curve_source="rosario_2026-10-27",
        regional_rent_usd_ha=be_rent,
        allow_rent_out=True,
    )
    r_be = optimize(sc_be)
    assert r_be.npv == pytest.approx(farm_only_npv, abs=1.0)


def test_11_app_plan_text_farming(monkeypatch):
    """11. App plan text when the plan farms and tenure_comparison is present:
    shows 'Si alquilaras todo a {rent} USD/ha: VAN {rent_all} ({diff:+} USD). Alquilar conviene si te pagan más de {break_even} USD/ha.'
    with placeholder note if regional_rent_placeholder is true."""
    mock_eval = {
        "npv_usd": 1159513.59,
        "unsown_ha": 623.5,
        "max_credit_usd": 0.0,
        "debt": [0.0],
        "hectares": {"wheat": 170.1, "corn": 177.8, "soybean": 1000.0, "sunflower": 28.6},
        "regional_rent_usd_ha": 570.0,
        "regional_rent_placeholder": False,
        "rent_out_income_usd": 0.0,
        "land_tenure": {
            "rent_out_ha": 0.0,
            "owned_ha": 2000.0,
        },
        "tenure_comparison": {
            "farm_only_npv_usd": 1159513.59,
            "rent_all_npv_usd": 1640000.0,
            "best": "rent_out",
            "gain_vs_farm_only_usd": 0.0,
            "break_even_rent_usd_ha": 425.43,
            "renting_pays_more": True,
        },
    }

    def fake_run_tool(name, payload_json):
        if name == "evaluate_season":
            return json.dumps(mock_eval)
        elif name == "shadow_prices":
            return json.dumps({"land": {}, "capital": {"rates_per_fortnight": []}})
        elif name == "build_scenario":
            return json.dumps({"scenario": {}})
        elif name == "tax_wedge":
            return json.dumps({"taxes": []})
        return "{}"

    monkeypatch.setattr("app.run_tool", fake_run_tool)
    res = run_scenario(area_ha=2000, crops=["wheat", "corn", "soybean", "sunflower"], own_capital_usd=500000, lang="es")
    plan = res["plan"]
    assert "Dado en alquiler" not in plan
    assert "Si alquilaras todo a 570 USD/ha: VAN 1.640.000,00 (+480.486,41 USD)." in plan
    assert "Alquilar conviene si te pagan más de 425,43 USD/ha." in plan
    assert "Pico de crédito utilizado: USD 0" in plan.replace("**", "")
    assert "None" not in plan

    # Placeholder case
    mock_eval_ph = dict(mock_eval, regional_rent_placeholder=True)
    monkeypatch.setattr("app.run_tool", lambda name, payload: json.dumps(mock_eval_ph) if name == "evaluate_season" else "{}")
    res_ph = run_scenario(area_ha=2000, crops=["wheat", "corn", "soybean", "sunflower"], own_capital_usd=500000, lang="es")
    assert "(alquiler estimado: cargá el que te ofrecen en Opciones avanzadas)" in res_ph["plan"]
