import json
from unittest.mock import MagicMock
import pytest

import app
from app import on_apply_polygon, on_region_change, respond, get_observatory_ui_data, build_app
from dora.engine import Result
from dora.verifier import check_scenario, fix_label_language


def test_1_region_dropdown_and_polygon_apply():
    # 1. The region dropdown choices include the four region keys;
    # on_apply_polygon with a polygon in Pergamino returns pampas_core and that region's crops;
    # with a polygon in the ocean it returns no region change and the "fuera de las regiones" message.
    demo = build_app(api_key="test-fake-key")

    # Verify dropdown choices in region_input
    # Find dropdown by checking components or choices
    found_choices = None
    for comp in demo.blocks.values():
        if hasattr(comp, "choices") and isinstance(comp.choices, list):
            vals = [c[1] if isinstance(c, tuple) else c for c in comp.choices]
            if "southeast_buenos_aires" in vals and "pampas_core" in vals:
                found_choices = vals
                break

    assert found_choices is not None, "region_input dropdown not found in app blocks"
    for expected_reg in ("southeast_buenos_aires", "pampas_core", "iowa", "mato_grosso"):
        assert expected_reg in found_choices

    # Pergamino polygon (centroid near lon -60.57, lat -33.89)
    poly_pergamino = {
        "type": "Polygon",
        "coordinates": [[
            [-60.6, -33.9],
            [-60.5, -33.9],
            [-60.5, -33.8],
            [-60.6, -33.8],
            [-60.6, -33.9],
        ]]
    }
    area_upd, crops_upd, reg_upd, msg, _ = on_apply_polygon(json.dumps(poly_pergamino), lang="es")
    assert reg_upd["value"] == "pampas_core"
    assert "trigo" in crops_upd["choices"]
    assert "maíz" in crops_upd["choices"]
    assert "soja" in crops_upd["choices"]
    assert "Campo delimitado" in msg
    assert "Zona núcleo (Pergamino)" in msg

    # Ocean polygon (outside all known regions)
    poly_ocean = {
        "type": "Polygon",
        "coordinates": [[
            [0.0, 0.0],
            [1.0, 0.0],
            [1.0, 1.0],
            [0.0, 1.0],
            [0.0, 0.0],
        ]]
    }
    area_upd_o, crops_upd_o, reg_upd_o, msg_o, _ = on_apply_polygon(json.dumps(poly_ocean), lang="es")
    assert "value" not in reg_upd_o
    assert "fuera de las regiones" in msg_o


def test_2_respond_api_failure_handling():
    # 2. respond with an agent whose ask raises returns the warning message in the history
    # and does not increase _daily_chat_counter.
    initial_counter = app._daily_chat_counter

    class BrokenAgent:
        user_texts = []

        def ask(self, *args, **kwargs):
            raise RuntimeError("API connection failed")

    agent = BrokenAgent()
    user_msg = "Plan para 500 ha en Pergamino"
    txt_out, files_out, audio_out, history, ret_agent = respond(
        user_msg, None, None, [], agent, "es", None
    )

    assert app._daily_chat_counter == initial_counter
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == user_msg
    assert history[1]["role"] == "assistant"
    assert "⚠️ No pude hablar con el modelo ahora" in history[1]["content"]

    # In English
    txt_out, files_out, audio_out, history_en, _ = respond(
        user_msg, None, None, [], agent, "en", None
    )
    assert app._daily_chat_counter == initial_counter
    assert "⚠️ Could not reach the model right now" in history_en[1]["content"]


def test_3_verifier_zero_needs_farmer():
    # 3. check_scenario("evaluate_season", {"credit_line_usd": 0, ...}, ["On 500 ha with $50,000 capital in Iowa ..."], [<a build_scenario result>])
    # reports credit_line_usd; with user text "nadie me presta" it does not.
    mock_build_scenario_res = json.dumps({
        "scenario": {
            "area_ha": 500.0,
            "own_capital_usd": 50000.0,
            "credit_line_usd": 0.0,
            "region": "iowa",
        }
    })

    # Case A: User said $50,000 capital in Iowa, said nothing about credit -> flagged
    scenario = {
        "area_ha": 500.0,
        "own_capital_usd": 50000.0,
        "credit_line_usd": 0.0,
        "region": "iowa",
    }
    user_texts_no_mention = ["On 500 ha with $50,000 capital in Iowa, what should I plant?"]
    problems = check_scenario(
        "evaluate_season",
        scenario,
        user_texts_no_mention,
        [mock_build_scenario_res]
    )
    assert any(p.parameter == "credit_line_usd" for p in problems)

    # Case B: User said "nadie me presta" -> accepted (not flagged)
    user_texts_no_credit_es = ["Tengo 500 ha en Balcarce con 50 lucas, nadie me presta un mango."]
    problems_allowed = check_scenario(
        "evaluate_season",
        scenario,
        user_texts_no_credit_es,
        [mock_build_scenario_res]
    )
    assert not any(p.parameter == "credit_line_usd" for p in problems_allowed)

    # Case C: User said in English "without credit" -> accepted
    user_texts_no_credit_en = ["On 500 ha with $50,000 capital in Iowa, no credit line available."]
    problems_allowed_en = check_scenario(
        "evaluate_season",
        scenario,
        user_texts_no_credit_en,
        [mock_build_scenario_res]
    )
    assert not any(p.parameter == "credit_line_usd" for p in problems_allowed_en)


def test_4_capital_stretches_half_month():
    # 4. capital_stretches for a one-fortnight stretch gives duration_months == 0.5.
    res = Result(
        npv=0.0,
        final_wealth=0.0,
        hectares={},
        sales={},
        stock={},
        cash=[0.0] * 30,
        debt=[0.0] * 30,
        cash_value=[1.0] * 30,
        internal_rate_annual=[0.04] * 30,
        capital_shadow_price=0.05,
        land_shadow_price=0.0,
        storage_shadow_price=[0.0] * 30,
        credit_shadow_price=[0.0] * 30,
        market_rate_annual=0.04,
    )
    res.cash_value[5] = 1.05
    res.cash_value[6] = 1.00
    # Fortnight 5 is scarce (annual rate > deposit rate 0.04)
    res.internal_rate_annual[5] = 0.80

    stretches = res.get_capital_stretches(lang="es")
    assert len(stretches) == 1
    s = stretches[0]
    assert s["start_fortnight_idx"] == 5
    assert s["end_fortnight_idx"] == 6
    assert s["duration_days"] == 15
    assert s["duration_months"] == 0.5


def test_5_fix_label_language():
    # 5. fix_label_language turns "Lo que entendí" into "What I understood" for an English question only.
    ans_with_es_label = "### Lo que entendí:\n- 500 ha in Iowa\n- Soybeans: 250 ha"
    ans_with_en_label = "### What I understood:\n- 500 ha in Iowa\n- Soybeans: 250 ha"

    user_en = "On 500 ha with Iowa corn, what is the optimal plan?"
    user_es = "¿Cuál es el plan óptimo para 500 ha en Balcarce con maíz?"

    # English question: the Spanish label is replaced in code, not sent back to the model
    assert fix_label_language(ans_with_es_label, user_en) == ans_with_en_label

    # English label stays as it is
    assert fix_label_language(ans_with_en_label, user_en) == ans_with_en_label

    # Spanish question keeps "Lo que entendí"
    assert fix_label_language(ans_with_es_label, user_es) == ans_with_es_label


def test_6_observatory_header_no_file_protocol():
    # 6. The Observatory header has no file:///.
    banner_es, _, _, _ = get_observatory_ui_data(force_run=False, lang="es")
    assert "file:///" not in banner_es
    assert "Fecha de la foto:" in banner_es

    banner_en, _, _, _ = get_observatory_ui_data(force_run=False, lang="en")
    assert "file:///" not in banner_en
    assert "Snapshot date:" in banner_en
