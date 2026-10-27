import json
import os
from unittest.mock import patch

import pandas as pd
import plotly.graph_objects as go
import pytest

from app import build_app, format_number_es, fortnight_name_es, run_scenario
from dora.tools import run_tool


# 1. Building the Gradio app does not raise (call builder, do not launch)
def test_build_gradio_app_does_not_raise():
    app = build_app(api_key="")
    assert app is not None


# 2. Function behind Run with "Capital-rationed farm" example returns dict with
#    plan, three Plotly figures, constraints table, and NPV equals evaluate_season's
def test_run_scenario_capital_rationed_farm():
    # Capital-rationed farm: 500 ha, 50,000 USD capital, 100,000 USD credit
    res = run_scenario(
        area_ha=500.0,
        crops=["wheat", "corn", "soybean", "sunflower"],
        own_capital_usd=50000.0,
        credit_line_usd=100000.0,
        credit_rate_pct=10.0,
        supplier_delay=0,
        supplier_surcharge_pct=0.0,
        storage_capacity_t=1000.0,
    )

    assert isinstance(res, dict)
    assert "plan" in res
    assert isinstance(res["plan"], str)

    # Three main Plotly figures
    assert "figures" in res
    assert len(res["figures"]) == 3
    for fig in res["figures"]:
        assert isinstance(fig, go.Figure)

    assert isinstance(res["chart_rates"], go.Figure)
    assert isinstance(res["chart_resources"], go.Figure)
    assert isinstance(res["chart_cash_debt"], go.Figure)

    # Constraints table
    assert "constraints" in res
    assert isinstance(res["constraints"], pd.DataFrame)

    # NPV equals evaluate_season's
    eval_raw = run_tool(
        "evaluate_season",
        json.dumps({
            "scenario": {
                "area_ha": 500.0,
                "crops": ["wheat", "corn", "soybean", "sunflower"],
                "own_capital_usd": 50000.0,
                "credit_line_usd": 100000.0,
            }
        }),
    )
    eval_res = json.loads(eval_raw)
    assert res["npv"] == pytest.approx(eval_res["npv_usd"])


# 3. evaluate_season includes cash and debt with 30 values each
def test_evaluate_season_includes_cash_and_debt_30_values():
    eval_raw = run_tool("evaluate_season", json.dumps({"scenario": {"area_ha": 500}}))
    eval_res = json.loads(eval_raw)

    assert "cash" in eval_res
    assert "debt" in eval_res
    assert len(eval_res["cash"]) == 30
    assert len(eval_res["debt"]) == 30

    # Values rounded to 0 decimals
    for val in eval_res["cash"]:
        assert isinstance(val, (int, float))
        assert val == round(val)

    for val in eval_res["debt"]:
        assert isinstance(val, (int, float))
        assert val == round(val)


# 4. Without DORA_API_KEY, the Chat tab is not built
def test_chat_tab_not_built_without_api_key():
    with patch.dict(os.environ, {}, clear=True):
        app = build_app()
        assert not getattr(app, "has_chat", False)

        tab_ids = [getattr(b, "elem_id", None) for b in app.blocks.values()]
        assert "tab_chat" not in tab_ids

    # With API key set, the Chat tab IS built
    with patch.dict(os.environ, {"DORA_API_KEY": "fake-api-key"}, clear=True):
        app_with_chat = build_app()
        assert getattr(app_with_chat, "has_chat", True)

        tab_ids = [getattr(b, "elem_id", None) for b in app_with_chat.blocks.values()]
        assert "tab_chat" in tab_ids


# 5. Example scenario with constraints (Corn contract 150 ha)
def test_run_scenario_with_corn_constraint():
    res = run_scenario(
        area_ha=500.0,
        own_capital_usd=50000.0,
        credit_line_usd=100000.0,
        constraints_df=[["min_area", "corn", 150, "", ""]],
    )
    assert isinstance(res["constraints"], pd.DataFrame)
    assert len(res["constraints"]) == 1
    assert "corn" in res["plan_dict"]["hectares"]
    assert res["plan_dict"]["hectares"]["corn"] >= 150.0 - 1e-4


# 6. SPEC-04b: Spanish formatting tests
def test_spanish_number_formatter():
    assert format_number_es(88186.6) == "88.186,60"
    assert format_number_es(100000) == "100.000"


def test_spanish_fortnight_name():
    assert fortnight_name_es(15) == "2ª quincena de dic"


def test_spec_04b_chart_and_card_structure():
    # Capital-rationed farm
    res = run_scenario(
        area_ha=500.0,
        crops=["trigo", "maíz", "soja", "girasol"],
        own_capital_usd=50000.0,
        credit_line_usd=100000.0,
        credit_rate_pct=10.0,
        supplier_delay=0,
        supplier_surcharge_pct=0.0,
        storage_capacity_t=1000.0,
        lang="es",
    )

    # Chart A: Title and traces
    fig_a = res["chart_rates"]
    assert "¿Cuánto vale un dólar en cada quincena?" in fig_a.layout.title.text
    assert "Si la línea verde está arriba de la gris" in fig_a.layout.title.text
    trace_names = [t.name for t in fig_a.data]
    assert any("banco" in n.lower() for n in trace_names)
    assert any("campo" in n.lower() for n in trace_names)

    # Chart B: Only two per-dollar items
    fig_b = res["chart_resources"]
    assert len(fig_b.data[0].y) == 2
    assert "Línea de crédito (USD/$)" in fig_b.data[0].y
    assert "Capital propio (USD/$)" in fig_b.data[0].y

    # Value cards: Land and Storage
    assert "resource_cards" in res
    assert "Tierra:" in res["resource_cards"]
    assert "Almacenaje:" in res["resource_cards"]
    # In this scenario, storage is not active (value 0)
    assert "no es una restricción activa" in res["resource_cards"]

    # Plan card formatting
    assert "Fuentes:" in res["plan"]
    assert "88.186,60" in res["plan"] or "USD" in res["plan"]
