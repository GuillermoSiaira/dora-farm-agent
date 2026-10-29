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
