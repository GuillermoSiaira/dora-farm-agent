"""Acceptance tests for SPEC-23: Demo guide and DORA as a guide.

All tests run offline without network access.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import plotly.graph_objects as go
import pytest

from app import build_app, format_number_es, run_scenario
from dora.agent import Agent, FULL_SYSTEM_PROMPT
from dora.tools import evaluate_season, shadow_prices, tax_wedge


# ------------------------------------------------------------------------------
# Test 1: Page is never empty on load
# ------------------------------------------------------------------------------
def test_1_app_load_fills_scenario_outputs():
    """1. Building the app and running the load event fills the Scenario outputs

    (plan markdown not empty, every chart a figure with data).
    """
    app = build_app(api_key="")
    assert hasattr(app, "load_fn"), "app must expose load_fn for initialization"

    outputs = app.load_fn("es")
    (
        plan,
        land_card,
        fig_rates,
        fig_res,
        res_cards,
        fig_cash,
        fig_sales,
        constr_df,
        tax_df,
        tax_disc,
        run_entry,
        sc_params,
        banner,
        map_html,
        table_df,
        fig_obs,
    ) = outputs

    # Plan markdown not empty
    assert isinstance(plan, str)
    assert len(plan.strip()) > 0
    assert "Valor Presente Neto" in plan or "NPV" in plan

    # Land card not empty
    assert isinstance(land_card, str)
    assert len(land_card.strip()) > 0

    # Every chart is a Plotly figure with actual data points/traces
    charts = [fig_rates, fig_res, fig_cash, fig_sales]
    for fig in charts:
        assert isinstance(fig, go.Figure), f"Expected go.Figure, got {type(fig)}"
        assert len(fig.data) > 0, "Chart must contain data traces (not empty)"

    # DataFrames are valid
    assert isinstance(constr_df, pd.DataFrame)
    assert isinstance(tax_df, pd.DataFrame)
    assert isinstance(table_df, pd.DataFrame)


# ------------------------------------------------------------------------------
# Test 2: Example buttons load and compute
# ------------------------------------------------------------------------------
def test_2_example_buttons_load_and_compute():
    """2. Each example button loads and computes: the plan differs between

    'Capital restringido' and 'Contrato de maíz', and the maize contract plan has at least 150 ha of maize.
    """
    app = build_app(api_key="")
    assert hasattr(app, "example_rationed_fn")
    assert hasattr(app, "example_corn_fn")

    res_rationed = app.example_rationed_fn("es")
    res_corn = app.example_corn_fn("es")

    # Outputs: index 17 is plan_output
    plan_rationed = res_rationed[17]
    plan_corn = res_corn[17]

    assert plan_rationed != plan_corn, "Plan must differ between rationed capital and corn contract"

    # In corn contract, maize area is at least 150 ha
    sc_params_corn = res_corn[-1]
    assert "constraints" in sc_params_corn
    res_eval = run_scenario(
        area_ha=500.0,
        own_capital_usd=50000.0,
        constraints_df=sc_params_corn["constraints"],
        lang="es",
    )
    corn_ha = res_eval["plan_dict"]["hectares"].get("corn", 0.0)
    assert corn_ha >= 150.0 - 1e-4, f"Maize area must be >= 150 ha, got {corn_ha}"


# ------------------------------------------------------------------------------
# Test 3: Language separation
# ------------------------------------------------------------------------------
def test_3_language_separation():
    """3. Language: with lang='es', no output of the Scenario tab contains the English sentence

    'an extra hectare is worth'; with lang='en', no Spanish label of section 4 appears.
    """
    # Spanish run
    res_es = run_scenario(lang="es")
    for key in ("land_card", "plan", "resource_cards", "tax_disclaimer"):
        val = res_es.get(key, "")
        if isinstance(val, str):
            assert "an extra hectare is worth" not in val, f"Found English sentence in {key} for lang='es'"

    # English run
    res_en = run_scenario(lang="en")
    spanish_section4_markers = [
        "aunque quedan",
        "el valor viene de la rotación",
        "en la campaña (14,5 meses)",
        "alícuotas a verificar (placeholder)",
        "Derechos de exportación",
        "Impuesto a las ganancias",
        "Tasa de red vial municipal",
    ]
    texts_to_check = [
        res_en.get("land_card", ""),
        res_en.get("resource_cards", ""),
        res_en.get("tax_disclaimer", ""),
        " ".join(res_en.get("tax_wedge_table", pd.DataFrame()).get("Tax", []).tolist()),
    ]
    for marker in spanish_section4_markers:
        for t in texts_to_check:
            assert marker not in t, f"Found Spanish marker '{marker}' in English output: {t}"


# ------------------------------------------------------------------------------
# Test 4: Land card contains rotation sentence with unsown hectares
# ------------------------------------------------------------------------------
def test_4_land_card_contains_rotation_sentence_with_unsown_ha():
    """4. Land card: in the default Balcarce scenario (unsown hectares, land shadow price > 0),

    the card contains the rotation sentence with the unsown hectares from the tool.
    """
    res = run_scenario(area_ha=500.0, own_capital_usd=50000.0, lang="es")
    eval_res = res["evaluate_season"]
    unsown = eval_res.get("unsown_ha", 0.0)
    assert unsown > 0, "Default Balcarce scenario must have unsown hectares"

    unsown_fmt = format_number_es(unsown, 1)
    expected_es = (
        f"aunque quedan {unsown_fmt} ha sin sembrar: el valor viene de la rotación "
        f"(con una hectárea más podés sembrar más del cultivo que está en su tope)"
    )
    assert expected_es in res["land_card"] or expected_es in res["resource_cards"]

    # In English as well
    res_en = run_scenario(area_ha=500.0, own_capital_usd=50000.0, lang="en")
    expected_en = (
        f"even though {unsown:.1f} ha remain unsown: the value comes from the rotation "
        f"(with an extra hectare you can sow more of the crop that is at its cap)"
    )
    assert expected_en in res_en["land_card"] or expected_en in res_en["resource_cards"]


# ------------------------------------------------------------------------------
# Test 5: Returns show season figure, annual figure, and deposit rate
# ------------------------------------------------------------------------------
def test_5_returns_show_season_annual_and_deposit_rate():
    """5. Returns: the card shows the season figure, the annual figure and the deposit rate,

    all equal to the tool's fields.
    """
    eval_data = evaluate_season({"area_ha": 500, "own_capital_usd": 50000})
    lt = eval_data["land_tenure"]

    roc_season = lt["return_on_capital_pct"]
    roc_annual = lt["return_on_capital_annual_pct"]
    dep_rate = lt["deposit_rate_annual_pct"]
    season_m = lt.get("season_months", 14.5)

    # In English
    res_en = run_scenario(area_ha=500.0, own_capital_usd=50000.0, lang="en")
    card_en = res_en["land_card"]
    assert f"{roc_season:.1f}% for the season ({season_m:.1f} months)" in card_en
    assert f"{roc_annual:.1f}% annual" in card_en
    assert f"deposit rate {dep_rate:.1f}%" in card_en

    # In Spanish
    res_es = run_scenario(area_ha=500.0, own_capital_usd=50000.0, lang="es")
    card_es = res_es["land_card"]
    season_m_str = format_number_es(season_m, 1)
    assert f"{format_number_es(roc_season, 1)}% en la campaña ({season_m_str} meses)" in card_es
    assert f"{format_number_es(roc_annual, 1)}% anual" in card_es
    assert f"tasa depósito {format_number_es(dep_rate, 1)}%" in card_es


# ------------------------------------------------------------------------------
# Test 6: Frozen model and tool numbers match main to 1e-9
# ------------------------------------------------------------------------------
def test_6_frozen_tool_numbers_match_main_to_1e9():
    """6. The tools' numbers do not change: evaluate_season and shadow_prices

    for the default scenario give the same values as main (to 1e-9).
    """
    fixture_path = Path(__file__).parent / "data" / "spec23_main_tool_numbers.json"
    assert fixture_path.is_file(), f"Fixture missing: {fixture_path}"

    with open(fixture_path, "r", encoding="utf-8") as f:
        baseline = json.load(f)["numbers"]

    def extract_numbers(obj, prefix=""):
        nums = {}
        if isinstance(obj, dict):
            for k, v in obj.items():
                p = f"{prefix}.{k}" if prefix else k
                nums.update(extract_numbers(v, p))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                p = f"{prefix}[{i}]"
                nums.update(extract_numbers(v, p))
        elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
            nums[prefix] = float(obj)
        return nums

    default_sc = {
        "area_ha": 500.0,
        "crops": ["wheat", "corn", "soybean", "sunflower"],
        "own_capital_usd": 50000.0,
        "credit_line_usd": 100000.0,
        "region": "southeast_buenos_aires",
    }
    eval_actual = extract_numbers(evaluate_season(default_sc, lang="es"))
    eval_base = baseline["form_default|evaluate_season|es"]
    for k, base_val in eval_base.items():
        assert k in eval_actual, f"Missing key {k} in evaluate_season"
        assert eval_actual[k] == pytest.approx(base_val, abs=1e-9), f"Mismatch at {k}"

    shadow_actual = extract_numbers(shadow_prices(default_sc, lang="es"))
    shadow_base = baseline["form_default|shadow_prices|es"]
    for k, base_val in shadow_base.items():
        assert k in shadow_actual, f"Missing key {k} in shadow_prices"
        assert shadow_actual[k] == pytest.approx(base_val, abs=1e-9), f"Mismatch at {k}"

    tax_actual = extract_numbers(tax_wedge(default_sc, lang="es"))
    tax_base = baseline["form_default|tax_wedge|-"]
    for k, base_val in tax_base.items():
        assert k in tax_actual, f"Missing key {k} in tax_wedge"
        assert tax_actual[k] == pytest.approx(base_val, abs=1e-9), f"Mismatch at {k}"


# ------------------------------------------------------------------------------
# Test 7: DORA guide system prompt and screen context
# ------------------------------------------------------------------------------
def test_7_guide_system_prompt_and_screen_context():
    """7. Guide: the system prompt contains the 'Using the DORA screen' section;

    a scripted agent call (no network, with a fake client) passes the last scenario to the model.
    """
    guide_path = Path(__file__).parent.parent / "dora" / "modeling_guide.md"
    guide_content = guide_path.read_text(encoding="utf-8")
    assert "Using the DORA screen" in guide_content, "modeling_guide.md must contain 'Using the DORA screen' section"
    assert "Using the DORA screen" in FULL_SYSTEM_PROMPT, "FULL_SYSTEM_PROMPT must contain 'Using the DORA screen'"

    # Scripted agent call with fake client
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.tool_calls = None
    mock_choice.message.content = "Explicación del gráfico según tus parámetros de pantalla."
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_completion.usage.prompt_tokens = 10
    mock_completion.usage.completion_tokens = 5
    mock_completion.usage.total_tokens = 15
    mock_client.chat.completions.create.return_value = mock_completion

    agent = Agent(client=mock_client, use_verifier=False)
    assert any("Using the DORA screen" in m.get("content", "") for m in agent.messages if m["role"] == "system")

    screen_params = {
        "area_ha": 500.0,
        "own_capital_usd": 50000.0,
        "region": "southeast_buenos_aires",
    }
    reply = agent.ask("¿Qué significa este gráfico?", screen_scenario=screen_params)
    assert reply is not None
    assert agent.screen_scenario == screen_params

    # Verify that mock_client.chat.completions.create received messages mentioning screen_scenario
    assert mock_client.chat.completions.create.called
    call_args = mock_client.chat.completions.create.call_args
    messages = call_args.kwargs.get("messages", call_args.args[0] if call_args.args else [])

    found_screen_context = False
    for item in messages:
        content_str = str(item.get("content", ""))
        if "southeast_buenos_aires" in content_str and "50000" in content_str:
            found_screen_context = True
            break
    assert found_screen_context, "Screen scenario parameters must be passed in messages to the model"


# ------------------------------------------------------------------------------
# Test 8: Voice output policy (no TTS in Meta API)
# ------------------------------------------------------------------------------
def test_8_voice_output_policy():
    """8. If voice output is implemented: the button exists only in the chat,

    and no audio request is made until it is pressed.
    Meta Model API provides only ASR (transcribe), not TTS; therefore no TTS button exists.
    """
    app = build_app(api_key="fake-test-key")
    # Verify no TTS button exists in the blocks
    for block in app.blocks.values():
        if isinstance(block, go.Figure):
            continue
        val = getattr(block, "value", None)
        if isinstance(val, str):
            assert "🔊 Escuchar" not in val, "TTS button must not exist since Meta API lacks TTS"


# ------------------------------------------------------------------------------
# Test 9: Chat handles scenario state from Calculate button without TypeError (Issue 1)
# ------------------------------------------------------------------------------
def test_9_chat_handles_scenario_state_from_calculate():
    """Verify that after clicking Calculate with DataFrame constraints,
    last_scenario_state is JSON serializable and Agent.ask does not crash with TypeError."""
    app = build_app(api_key="fake-test-key")
    assert hasattr(app, "run_fn")
    assert hasattr(app, "respond_fn")

    constr_df = pd.DataFrame([["min_area", "maíz", 100, "", None]], columns=["Type", "Crop", "Value", "Month", "Price"])

    # Simulate on_run with DataFrame constraints
    run_res = app.run_fn(
        500.0, ["trigo", "maíz", "soja", "girasol"], 50000.0, 100000.0, 10.0,
        0, 0.0, 1000.0, "MAGyP default", constr_df, "es", "southeast_buenos_aires",
        None, 0.0, 0.0, True, [], 0.0
    )
    last_scenario_state = run_res[11]

    # Verify JSON serializability directly
    serialized = json.dumps(last_scenario_state, ensure_ascii=False)
    assert isinstance(serialized, str)
    assert "min_area" in serialized

    # Verify that respond_fn executes without TypeError
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.tool_calls = None
    mock_choice.message.content = "No se siembra más trigo porque el capital escasea."
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_completion.usage.prompt_tokens = 10
    mock_completion.usage.completion_tokens = 5
    mock_completion.usage.total_tokens = 15
    mock_client.chat.completions.create.return_value = mock_completion

    agent = Agent(client=mock_client, use_verifier=False)
    out_msg, out_files, out_audio, history, out_agent = app.respond_fn(
        "¿Por qué no sembrás más trigo?", None, None, [], agent, "es", last_scenario_state
    )
    assert len(history) == 2
    assert "No se siembra más trigo" in history[1]["content"]


# ------------------------------------------------------------------------------
# Test 10: Export duties placeholder notice in tax wedge table (Issue 2)
# ------------------------------------------------------------------------------
def test_10_export_duties_placeholder_notice():
    """Verify that the tax wedge table displays the placeholder notice on the export duties row."""
    # In Spanish
    res_es = run_scenario(lang="es")
    df_es = res_es["tax_wedge_table"]
    export_rows_es = df_es[df_es["Impuesto"].str.contains("exportación", case=False, na=False)]
    assert not export_rows_es.empty, "Export duties row not found in Spanish tax wedge table"
    es_amount = export_rows_es.iloc[0]["Monto (USD)"]
    assert "alícuotas a verificar (placeholder)" in es_amount

    # In English
    res_en = run_scenario(lang="en")
    df_en = res_en["tax_wedge_table"]
    export_rows_en = df_en[df_en["Tax"].str.contains("export", case=False, na=False)]
    assert not export_rows_en.empty, "Export duties row not found in English tax wedge table"
    en_amount = export_rows_en.iloc[0]["Amount (USD)"]
    assert "rates to be verified (placeholder)" in en_amount


# ------------------------------------------------------------------------------
# Test 11: Language switch recomputes and redraws all components (Issue 3)
# ------------------------------------------------------------------------------
def test_11_language_switch_recomputes_and_updates_all_components():
    """Verify that switching language recomputes the plan and updates notices, cards, tables, and chat labels."""
    app = build_app(api_key="fake-test-key")
    assert hasattr(app, "lang_change_fn")

    # Initial state from load
    load_out = app.load_fn("es")
    last_sc = load_out[11]

    # Switch to English
    out_en = app.lang_change_fn("English", last_sc)
    new_lang = out_en[0]
    crops_upd = out_en[1]
    comp_mode_upd = out_en[2]
    plan_en = out_en[3]
    land_card_en = out_en[4]
    constraints_en = out_en[10]
    tax_wedge_en = out_en[11]
    obs_banner_en = out_en[15]

    assert new_lang == "en"
    assert "wheat" in crops_upd["choices"]
    assert "Same farm" in comp_mode_upd["choices"][0]
    assert "Net Present Value" in plan_en
    assert "Owned land" in land_card_en
    assert "Tax" in tax_wedge_en.columns
    assert "Type" in constraints_en.columns or constraints_en.empty
    assert "Published Observatory Reference" in obs_banner_en

    # Switch back to Spanish
    out_es = app.lang_change_fn("Español", out_en[14])
    assert out_es[0] == "es"
    assert "trigo" in out_es[1]["choices"]
    assert "Mismo campo" in out_es[2]["choices"][0]
    assert "Valor Presente Neto" in out_es[3]
    assert "Tierra propia" in out_es[4]
    assert "Impuesto" in out_es[11].columns
    assert "Referencia Publicada del Observatorio" in out_es[15]


# ------------------------------------------------------------------------------
# Test 12: Minor fixes - Argentine comma, rent omission, routes, run_entry (Issue 5)
# ------------------------------------------------------------------------------
def test_12_minor_fixes():
    """Verify minor formatting: comma decimal, omitted rent when 0, route translation, None in run_entry."""
    # 1. Comma decimal and omission of 0.0 rent in Spanish
    res_es = evaluate_season({"area_ha": 500, "own_capital_usd": 50000, "lang": "es"})
    land_comp_es = res_es.get("land_comparison", "")
    assert "37,73" in land_comp_es
    assert "alquilar una cuesta" not in land_comp_es
    assert "la plata inmovilizada" not in land_comp_es

    # 2. When rent is present, it is included with comma
    res_rent = evaluate_season({"area_ha": 500, "own_capital_usd": 50000, "regional_rent_usd_ha": 150.0, "lang": "es"})
    assert "alquilar una cuesta 150,0" in res_rent.get("land_comparison", "")

    # 3. Route name in Spanish Plan is translated from 'Direct freight' to 'Flete directo'
    scenario_res = run_scenario(area_ha=500, own_capital_usd=50000, lang="es")
    assert "Flete directo" in scenario_res["plan"]
    assert "Direct freight" not in scenario_res["plan"]

    # 4. In run_entry, return_on_capital_and_land is None when land has no price
    assert scenario_res["run_entry"]["return_on_capital_and_land"] is None


# ------------------------------------------------------------------------------
# Test 13: Chart A readability, height, horizontal ticks, and legend position
# ------------------------------------------------------------------------------
def test_13_chart_rates_readability_and_ticks():
    """Verify that Chart A has height >= 300, horizontal ticks spaced every 2 fortnights, and legend above the plot."""
    from app import create_internal_rate_chart
    sp = shadow_prices({"area_ha": 500, "own_capital_usd": 50000})

    # Spanish
    fig_es = create_internal_rate_chart(sp, lang="es")
    assert fig_es.layout.height >= 300
    assert fig_es.layout.xaxis.tickangle == 0
    assert 10 <= len(fig_es.layout.xaxis.tickvals) <= 16
    assert fig_es.layout.legend.y >= 1.0
    assert "1ª may" in fig_es.layout.xaxis.ticktext[0]

    # English
    fig_en = create_internal_rate_chart(sp, lang="en")
    assert fig_en.layout.height >= 300
    assert fig_en.layout.xaxis.tickangle == 0
    assert 10 <= len(fig_en.layout.xaxis.tickvals) <= 16
    assert fig_en.layout.legend.y >= 1.0
    assert "early May" in fig_en.layout.xaxis.ticktext[0]


# ------------------------------------------------------------------------------
# Test 14: Chat badge verified in Spanish
# ------------------------------------------------------------------------------
def test_14_chat_badge_verified_in_spanish():
    """Verify that the chat verified badge in Spanish states 'verificado: cada número sale del motor'."""
    from app import STRINGS
    assert "verificado: cada número sale del motor" in STRINGS["es"]["chat_badge_verified"]
    assert "verified: every number comes from the engine" in STRINGS["en"]["chat_badge_verified"]


# ------------------------------------------------------------------------------
# Test 15: Regional Observatory map text, legend, and market rate line bilingual
# ------------------------------------------------------------------------------
def test_15_observatory_bilingual_map_and_chart():
    """Verify that Observatory map text uses 'vos' in Spanish, English in English, and chart market line follows language."""
    from app import get_observatory_ui_data, make_observatory_html

    # Spanish map HTML
    html_es = make_observatory_html([], lang="es")
    assert "hacé clic en los marcadores" in html_es
    assert "haga clic" not in html_es

    # English map HTML
    html_en = make_observatory_html([], lang="en")
    assert "click on markers" in html_en
    assert "hacé clic" not in html_en

    # Chart reference line
    banner_es, map_es, df_es, fig_obs_es = get_observatory_ui_data(lang="es")
    ann_es = [a.text for a in fig_obs_es.layout.annotations if "mercado" in a.text or "Market" in a.text]
    assert any("Tasa de mercado (4.0%)" in t for t in ann_es)
    assert not any("Market rate" in t for t in ann_es)

    banner_en, map_en, df_en, fig_obs_en = get_observatory_ui_data(lang="en")
    ann_en = [a.text for a in fig_obs_en.layout.annotations if "mercado" in a.text or "Market" in a.text]
    assert any("Market rate (4.0%)" in t for t in ann_en)
    assert not any("Tasa de mercado" in t for t in ann_en)


# ------------------------------------------------------------------------------
# 16. Charts carry their own title: Gradio's label must not cover it (Claude's review, 29/10)
# ------------------------------------------------------------------------------
def test_16_charts_hide_gradio_label():
    """Every chart draws its own title, so the component label is hidden instead of covering it."""
    import gradio as gr

    app = build_app(api_key="")
    plots = [b for b in app.blocks.values() if isinstance(b, gr.Plot)]
    assert len(plots) == 8
    assert all(p.show_label is False for p in plots)
