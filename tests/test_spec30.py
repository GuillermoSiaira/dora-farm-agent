"""SPEC-30: Livestock in heads — Acceptance tests (offline, no network)."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from dora.scenario import Scenario, ScenarioError, load_livestock_data
from dora.engine import optimize
from dora.tools import evaluate_season, shadow_prices, next_question, build_scenario


DATA_DIR = Path(__file__).resolve().parent.parent / "dora" / "data" / "livestock"


# 1. Data format and integrity
def test_acceptance_1_livestock_data_integrity():
    """Every number in dora/data/livestock/*.json has value, unit, source, date and status;
    no url contains google.com/search; every old value is dated before 2024.
    """
    json_files = list(DATA_DIR.glob("*.json"))
    assert len(json_files) == 4, f"Expected 4 livestock files, found {len(json_files)}"

    for fpath in json_files:
        data = json.loads(fpath.read_text(encoding="utf-8"))

        def check_node(obj, path_str):
            if isinstance(obj, dict):
                # If it's a coefficient leaf with 'value'
                if "value" in obj:
                    assert "unit" in obj, f"Missing 'unit' at {path_str}"
                    assert "source" in obj, f"Missing 'source' at {path_str}"
                    assert "date" in obj, f"Missing 'date' at {path_str}"
                    assert "status" in obj, f"Missing 'status' at {path_str}"
                    assert obj["status"] in ("checked", "unchecked", "old", "sin_fuente"), f"Invalid status '{obj['status']}' at {path_str}"
                    if obj["status"] == "old":
                        yr = int(str(obj["date"])[:4])
                        assert yr < 2024, f"Old item must have year < 2024, got {yr} at {path_str}"
                    if "url" in obj and obj["url"]:
                        assert "google.com/search" not in obj["url"], f"Google search URL found at {path_str}"
                else:
                    for k, v in obj.items():
                        check_node(v, f"{path_str}.{k}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    check_node(v, f"{path_str}[{i}]")
            elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
                pytest.fail(f"Bare number found at {path_str}: {obj}. Must be wrapped in metadata object.")

        check_node(data, fpath.name)


# 2. Winter carrying capacity limits herd in Salado
def test_acceptance_2_salado_winter_carrying_capacity():
    """Salado, 500 ha of natural grass, cow_calf only, with the report's monthly receptivity:
    the herd the engine chooses is limited by winter (the grass dual is positive in winter
    and zero in spring); halving winter receptivity lowers the herd.
    """
    sc_dict = {
        "region": "southeast_buenos_aires",
        "area_ha": 500.0,
        "livestock": ["cow_calf"],
        "crops": [],
    }
    sc = Scenario(**sc_dict)
    r = optimize(sc)

    # In winter, grass constraint binds; in spring, surplus grass exists
    assert r.grass_shadow_price_by_season["winter"] > 0.0
    assert r.grass_shadow_price_by_season["spring"] == pytest.approx(0.0, abs=1e-6)

    # In shadow_prices, grass_by_season is reported per EV and per ha with plain meanings
    sp = shadow_prices(sc_dict, lang="es")
    assert sp["grass_by_season"]["winter"]["usd_per_extra_ev"] > 0.0
    assert sp["grass_by_season"]["winter"]["usd_per_extra_ha"] > 0.0
    assert "invierno te vale" in sp["grass_by_season"]["winter"]["meaning"]
    assert sp["grass_by_season"]["spring"]["usd_per_extra_ev"] == pytest.approx(0.0, abs=1e-6)
    assert sp["grass_by_season"]["spring"]["usd_per_extra_ha"] == pytest.approx(0.0, abs=1e-6)
    assert "primavera te sobra pasto" in sp["grass_by_season"]["spring"]["meaning"]

    herd_base = r.heads_livestock["cow_calf"]
    assert herd_base == pytest.approx(176.47, abs=0.1)

    # Halving winter receptivity cuts herd size in half
    sc_half = Scenario(
        region="southeast_buenos_aires",
        area_ha=500.0,
        livestock=["cow_calf"],
        crops=[],
        winter_receptivity=0.15,
    )
    r_half = optimize(sc_half)
    herd_half = r_half.heads_livestock["cow_calf"]
    assert herd_half < herd_base
    assert herd_half == pytest.approx(herd_base / 2.0, abs=0.2)


# 3. Feedlot uses no grass
def test_acceptance_3_feedlot_uses_no_grass():
    """Feedlot uses no grass: adding finishing_feedlot with no capacity limit
    does not change the grass dual.
    """
    # Iowa supports cow_calf and finishing_feedlot
    sc_base = Scenario(
        region="iowa",
        area_ha=500.0,
        cow_herd_heads=200.0,
        livestock=["cow_calf"],
        crops=[],
    )
    r_base = optimize(sc_base)
    base_winter_dual = r_base.grass_shadow_price_by_season.get("winter", 0.0)

    sc_feedlot = Scenario(
        region="iowa",
        area_ha=500.0,
        cow_herd_heads=200.0,
        livestock=["cow_calf", "finishing_feedlot"],
        crops=[],
    )
    r_feedlot = optimize(sc_feedlot)
    feedlot_winter_dual = r_feedlot.grass_shadow_price_by_season.get("winter", 0.0)

    assert feedlot_winter_dual == pytest.approx(base_winter_dual, abs=1e-3)


# 4. Cow herd capital valuation
def test_acceptance_4_cow_herd_end_value_no_unearned_profit():
    """The cow herd's end value: with the same herd at start and end and no price change,
    the herd adds no profit by itself (only the calves and culls sold do).
    """
    sc = Scenario(
        region="iowa",
        area_ha=500.0,
        cow_herd_heads=200.0,
        livestock=["cow_calf"],
        crops=[],
        deposit_rate_annual=0.0,
        credit_rate_annual=0.0,
    )
    r = optimize(sc)

    # When start and end herd are 200 cows at constant cow price,
    # the profit is strictly the cash flow growth from sales and operating costs
    cash_growth = r.cash[-1] - sc.own_capital_usd
    initial_herd_val = sc.cow_herd_heads * sc.livestock_cow_price()
    profit = r.final_wealth - (sc.own_capital_usd + initial_herd_val)
    assert profit - cash_growth == pytest.approx(0.0, abs=1e-3)
    # Check npv itself counts starting herd, so herd kept start-to-end adds no unearned profit
    assert r.npv - sc.own_capital_usd == pytest.approx(cash_growth, abs=1e-3)

    # When farmer owns more cows than land carries (300 owned, 176.5 fit),
    # excess cows are sold at cull price in fortnight 0
    sc_excess = Scenario(
        region="southeast_buenos_aires",
        area_ha=500.0,
        cow_herd_heads=300.0,
        livestock=["cow_calf"],
        crops=[],
    )
    r_excess = optimize(sc_excess)
    assert r_excess.cows_sold_heads == pytest.approx(123.53, abs=0.1)
    assert r_excess.cows_sold_revenue_usd == pytest.approx(106013.46, abs=1.0)


# 5. Regional activity availability
def test_acceptance_5_regional_activity_support():
    """Iowa cow_calf runs (no ScenarioError); Pampas Core cow_calf raises a ScenarioError
    naming the region and the activity (SAGyP models no cow-calf there).
    """
    # Iowa supports cow_calf
    sc_iowa = Scenario(
        region="iowa",
        area_ha=500.0,
        cow_herd_heads=100.0,
        livestock=["cow_calf"],
        crops=[],
    )
    r_iowa = optimize(sc_iowa)
    assert r_iowa.heads_livestock["cow_calf"] > 0

    # Pampas Core does not model cow_calf
    with pytest.raises(ScenarioError) as exc_info:
        Scenario(
            region="pampas_core",
            area_ha=500.0,
            livestock=["cow_calf"],
            crops=[],
        )
    msg = str(exc_info.value)
    assert "cow_calf" in msg
    assert "pampas_core" in msg


# 6. Provisional mark for unverified or old data
def test_acceptance_6_provisional_mark():
    """A result that uses an unchecked or old value carries the provisional mark naming it."""
    out = evaluate_season({
        "region": "southeast_buenos_aires",
        "area_ha": 500.0,
        "livestock": ["cow_calf"],
        "crops": [],
    })
    provisional = out.get("provisional", [])
    assert len(provisional) > 0
    prov_text = " ".join(provisional).lower()
    assert "receptividad" in prov_text or "ganadería" in prov_text or "provisorio" in prov_text


# 7. Interview next_question with cattle
def test_acceptance_7_next_question_cattle_candidates():
    """next_question with cattle in the scenario can return herd_size or activities;
    with no cattle it never does.
    """
    sc_cattle = {
        "region": "southeast_buenos_aires",
        "owned_ha": 500.0,
        "rented_land": False,
        "own_capital_usd": 100_000.0,
        "livestock": ["cow_calf"],
        "crops": [],
    }
    q_cattle = next_question(sc_cattle)
    assert q_cattle["next"]["id"] in ("herd_size", "activities", "winter_receptivity", "calf_fate")

    # With no cattle, cattle questions are never returned
    sc_nocattle = {
        "region": "southeast_buenos_aires",
        "area_ha": 500.0,
        "crops": ["soybean", "wheat"],
    }
    q_nocattle = next_question(sc_nocattle)
    assert q_nocattle["next"]["id"] not in ("herd_size", "activities", "winter_receptivity", "calf_fate")


# 8. SPEC-28 cattle-only case (Balcarce 500 ha, 100k USD)
def test_acceptance_8_spec28_cattle_only_case_updated():
    """The SPEC-28 cattle-only case (Balcarce, 500 ha, 100,000 USD, cría e invernada)
    still runs; its numbers change (new data), and the handoff shows before and after.
    """
    res = evaluate_season({
        "region": "southeast_buenos_aires",
        "owned_ha": 500.0,
        "own_capital_usd": 100_000.0,
        "crops": [],
        "livestock": ["cow_calf", "steer_fattening"],
    })
    assert len(res["hectares"]) == 0
    assert "heads_livestock" in res
    assert res["heads_livestock"]["cow_calf"] == pytest.approx(176.5, abs=0.5)
    assert res["npv_usd"] == pytest.approx(156566.70, abs=1.0)


# 9. Existing suite passes with updated cattle tests
def test_acceptance_9_existing_cattle_tests_pass():
    """The existing suite passes; tests that assert the old per-hectare cattle numbers
    are updated and listed in the handoff.
    """
    from tests.test_livestock import (
        test_cattle_only_land_cow_calf_perturbation,
        test_crop_margins_fall_shifts_shared_land_to_livestock,
        test_herd_purchase_ties_up_capital_and_valuation,
        test_livestock_income_sign_convention_matches_grain_sales,
        test_livestock_tools_and_validation,
    )
    from tests.test_spec28 import test_item_15_livestock_only

    test_cattle_only_land_cow_calf_perturbation()
    test_crop_margins_fall_shifts_shared_land_to_livestock()
    test_herd_purchase_ties_up_capital_and_valuation()
    test_livestock_income_sign_convention_matches_grain_sales()
    test_livestock_tools_and_validation()
    test_item_15_livestock_only()

# 10. Feedlot capacity shadow price and perturbation
def test_acceptance_10_feedlot_capacity_shadow_price_and_perturbation():
    """With a feedlot capacity below what the engine would use, feedlot.usd_per_extra_head_place
    is positive and raising the capacity by one head raises NPV by that amount (within 1 %);
    when capacity is unconstrained, dual is 0.0 and meaning says 'el corral no te limita'.
    """
    # Mato Grosso feedlot has positive margins
    d_cap = {
        "region": "mato_grosso",
        "area_ha": 500.0,
        "livestock": ["finishing_feedlot"],
        "crops": [],
        "own_capital_usd": 500_000.0,
        "feedlot_capacity_heads": 100.0,
    }
    r_cap = optimize(Scenario(**d_cap))
    assert r_cap.heads_livestock["finishing_feedlot"] == pytest.approx(100.0, abs=1e-3)
    assert r_cap.feedlot_shadow_price > 0.0

    sp_cap = shadow_prices(d_cap, lang="es")
    assert "feedlot" in sp_cap
    dual = sp_cap["feedlot"]["usd_per_extra_head_place"]
    assert dual > 0.0
    assert "un lugar más en el corral te vale" in sp_cap["feedlot"]["meaning"]

    # Perturbation: raising capacity by one head raises NPV by that amount within 1%
    d_cap101 = dict(d_cap, feedlot_capacity_heads=101.0)
    r_cap101 = optimize(Scenario(**d_cap101))
    delta_npv = r_cap101.npv - r_cap.npv
    assert abs(delta_npv - dual) / dual < 0.01

    # When capacity does not bind (e.g. huge capacity), dual is 0.0
    d_huge = dict(d_cap, feedlot_capacity_heads=5000.0)
    sp_huge = shadow_prices(d_huge, lang="es")
    assert sp_huge["feedlot"]["usd_per_extra_head_place"] == 0.0
    assert "el corral no te limita" in sp_huge["feedlot"]["meaning"]


# 11. Own herd shadow price and herd end valuation
def test_acceptance_11_own_herd_shadow_price():
    """With the herd fixed below what grass allows, herd.usd_per_extra_cow is positive;
    with herd above what grass allows, dual is 0.0 and meaning says 'el rodeo disponible no te limita'.
    """
    # In Salado, 500 ha of grass allows ~176.47 cows.
    # Herd cap at 100 cows binds below what grass allows.
    d_cap = {
        "region": "southeast_buenos_aires",
        "area_ha": 500.0,
        "livestock": ["cow_calf"],
        "crops": [],
        "cow_herd_heads": 100.0,
    }
    r_cap = optimize(Scenario(**d_cap))
    assert r_cap.heads_livestock["cow_calf"] == pytest.approx(100.0, abs=1e-3)
    assert r_cap.cow_herd_shadow_price > 0.0

    sp_cap = shadow_prices(d_cap, lang="es")
    assert "herd" in sp_cap
    assert sp_cap["herd"]["usd_per_extra_cow"] > 0.0
    assert "una vaca más te vale" in sp_cap["herd"]["meaning"]

    # When herd cap is 300 cows (above the 176.47 grass allows), grass binds first, so herd dual is 0.0
    d_300 = dict(d_cap, cow_herd_heads=300.0)
    r_300 = optimize(Scenario(**d_300))
    assert r_300.heads_livestock["cow_calf"] == pytest.approx(176.47, abs=0.1)
    assert r_300.cow_herd_shadow_price == pytest.approx(0.0, abs=1e-6)

    sp_300 = shadow_prices(d_300, lang="es")
    assert sp_300["herd"]["usd_per_extra_cow"] == 0.0
    assert "el rodeo disponible no te limita" in sp_300["herd"]["meaning"]

    # Also check herd_end reports what keeping one more cow is worth
    assert "herd_end" in sp_300
    assert sp_300["herd_end"]["usd_per_extra_cow_kept"] == pytest.approx(825.96, abs=0.1)
    assert "lo que vale una vaca al terminar la campaña" in sp_300["herd_end"]["meaning"]
