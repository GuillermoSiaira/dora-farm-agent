"""DORA: Crop-season planning demo web application with shadow-price charts.

Runs with Gradio and Plotly. Works in standalone scenario mode (no model needed)
and adds an agent chat tab when DORA_API_KEY is present.
"""
from __future__ import annotations

import json
import os
from typing import Any

import gradio as gr
import pandas as pd
import plotly.graph_objects as go

from dora.prices import available_curves
from dora.scenario import CALENDAR, FORTNIGHTS, fortnight_name
from dora.tools import run_tool

DAILY_CHAT_LIMIT = 200
_daily_chat_counter = 0

STRINGS = {
    "es": {
        "title": "DORA — Asistente de Planificación Agrícola",
        "description": "Optimización económica de campaña agrícola, análisis de restricciones financieras y precios sombra.",
        "tab_scenario": "Escenario",
        "tab_chat": "Chat con DORA",
        "lang_selector": "Idioma / Language",
        "inputs_header": "Parámetros del campo",
        "area_ha": "Superficie total (ha)",
        "crops": "Cultivos disponibles",
        "own_capital_usd": "Capital propio inicial (USD)",
        "credit_line_usd": "Línea de crédito (USD)",
        "credit_rate_pct": "Tasa del crédito anual (%)",
        "supplier_delay": "Plazo pago insumos (quincenas)",
        "supplier_surcharge": "Recargo de proveedor (%)",
        "storage_capacity_t": "Capacidad de almacenaje propio (t)",
        "price_source": "Fuente de precios",
        "magyp_default": "MAGyP por defecto",
        "constraints_header": "Restricciones del productor (opcional)",
        "run_button": "Calcular Plan Óptimo",
        "examples_header": "Ejemplos rápidos",
        "ex_rationed": "Campo con capital restringido",
        "ex_supplier": "Mismo campo, insumos a 90 días",
        "ex_corn": "Contrato de maíz (área mín. 150 ha)",
        "outputs_header": "Resultados de la Campaña",
        "plan_title": "Plan Propuesto y Valor Presente",
        "chart_rates_title": "¿Cuándo es escaso el capital?",
        "chart_rates_caption": "La línea muestra la tasa interna quincena a quincena. Las zonas sombreadas indican escasez de capital donde un dólar extra rinde más que el depósito bancario.",
        "chart_resources_title": "¿Cuánto vale cada recurso escaso?",
        "chart_resources_caption": "Muestra el precio sombra de cada factor: cuánto aumentaría el valor presente de la campaña ante una unidad adicional de cada recurso.",
        "chart_cash_debt_title": "¿Cómo evolucionan la caja y la deuda?",
        "chart_cash_debt_caption": "Evolución quincenal de los fondos líquidos en caja y la utilización de la línea de crédito comercial.",
        "chart_sales_title": "¿Cuándo y qué se vende?",
        "chart_sales_caption": "Distribución mensual de ventas físicas de grano según la capacidad de almacenaje y precios esperados.",
        "constraints_title": "Estado de las Restricciones y Costo de Oportunidad",
        "chat_input_placeholder": "Hacé una pregunta sobre la campaña (ej: ¿Por qué no sembramos más trigo?)...",
        "chat_badge_verified": "✅ **Verificado: cada número proviene del motor de cálculo.**",
        "chat_badge_unverified": "⚠️ **No verificado** (números sin respaldo: {unsupported})",
        "chat_limit_reached": "Se ha alcanzado el límite diario de 200 consultas. Por favor, intente nuevamente mañana.",
        "tool_calls_summary": "Detalle de llamadas a herramientas ({n})",
    },
    "en": {
        "title": "DORA — Farm Crop-Season Planning Assistant",
        "description": "Farm economic optimization, financial bottleneck analysis, and resource shadow prices.",
        "tab_scenario": "Scenario",
        "tab_chat": "Chat with DORA",
        "lang_selector": "Language / Idioma",
        "inputs_header": "Farm Parameters",
        "area_ha": "Total Farmland (ha)",
        "crops": "Available Crops",
        "own_capital_usd": "Starting Own Capital (USD)",
        "credit_line_usd": "Credit Line (USD)",
        "credit_rate_pct": "Credit Annual Rate (%)",
        "supplier_delay": "Supplier Payment Delay (fortnights)",
        "supplier_surcharge": "Supplier Surcharge (%)",
        "storage_capacity_t": "Storage Capacity (t)",
        "price_source": "Price Curve Source",
        "magyp_default": "MAGyP default",
        "constraints_header": "Farmer Constraints (optional)",
        "run_button": "Run Optimization",
        "examples_header": "Quick Scenarios",
        "ex_rationed": "Capital-rationed farm",
        "ex_supplier": "Same farm, 90-day supplier term",
        "ex_corn": "Corn contract (min area 150 ha)",
        "outputs_header": "Season Results",
        "plan_title": "Proposed Plan & Present Value",
        "chart_rates_title": "When is capital scarce?",
        "chart_rates_caption": "Line indicates fortnightly internal rate. Shaded periods indicate capital shortages where an extra dollar yields above the deposit rate.",
        "chart_resources_title": "What is each resource worth?",
        "chart_resources_caption": "Shadow price of each resource: how much present value increases with one additional unit of that factor.",
        "chart_cash_debt_title": "How do cash and debt evolve?",
        "chart_cash_debt_caption": "Fortnightly surplus cash vs credit line usage across the season.",
        "chart_sales_title": "When and what is sold?",
        "chart_sales_caption": "Monthly grain sales by crop under storage constraints and price expectations.",
        "constraints_title": "Farmer Constraints & Opportunity Cost",
        "chat_input_placeholder": "Ask a question about the season (e.g. Why isn't more wheat sown?)...",
        "chat_badge_verified": "✅ **Verified: every number comes from the engine.**",
        "chat_badge_unverified": "⚠️ **Not verified** (unsupported numbers: {unsupported})",
        "chat_limit_reached": "The daily cap of 200 questions has been reached. Please try again tomorrow.",
        "tool_calls_summary": "Tool calls details ({n})",
    },
}


# ==============================================================================
# Chart Generators
# ==============================================================================

def create_internal_rate_chart(shadow_prices_data: dict, lang: str = "es") -> go.Figure:
    """Chart A: Internal rate by fortnight with market rate and shaded scarce periods."""
    t = STRINGS.get(lang, STRINGS["es"])
    fortnights_info = shadow_prices_data.get("by_fortnight", [])
    market_rate = shadow_prices_data.get("market_rate_annual", 0.04) * 100.0

    x_labels = [row["fortnight"] for row in fortnights_info]
    rates = [row["internal_rate_annual"] * 100.0 for row in fortnights_info]

    fig = go.Figure()

    # Base line for internal rate
    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=rates,
            mode="lines+markers",
            name="Internal Rate / Tasa Interna" if lang == "es" else "Internal Rate",
            line={"color": "#16a34a", "width": 2.5},
            marker={"size": 6, "color": "#15803d"},
        )
    )

    # Market rate horizontal line
    fig.add_hline(
        y=market_rate,
        line_dash="dash",
        line_color="#dc2626",
        annotation_text=f"Market Rate / Tasa Mercado ({market_rate:.1f}%)"
        if lang == "es"
        else f"Market Deposit Rate ({market_rate:.1f}%)",
        annotation_position="top right",
    )

    # Shade fortnights where capital is scarce
    for i, rate in enumerate(rates):
        if rate > market_rate + 0.1:
            fig.add_vrect(
                x0=i - 0.45,
                x1=i + 0.45,
                fillcolor="#fca5a5",
                opacity=0.35,
                layer="below",
                line_width=0,
            )

    fig.update_layout(
        title={
            "text": f"<b>{t['chart_rates_title']}</b><br><sup>{t['chart_rates_caption']}</sup>",
            "x": 0.02,
        },
        xaxis={"title": "Quincena" if lang == "es" else "Fortnight", "tickangle": -45},
        yaxis={"title": "Tasa anual (%)" if lang == "es" else "Annual Rate (%)"},
        template="plotly_white",
        margin={"l": 50, "r": 30, "t": 75, "b": 70},
        height=380,
        showlegend=True,
    )
    return fig


def create_resource_shadow_prices_chart(shadow_prices_data: dict, lang: str = "es") -> go.Figure:
    """Chart B: Horizontal bars of shadow prices for capital, land, storage, and credit line."""
    t = STRINGS.get(lang, STRINGS["es"])

    cap_val = shadow_prices_data.get("own_capital", {}).get("usd_per_extra_dollar", 0.0)
    land_val = shadow_prices_data.get("land", {}).get("usd_per_extra_ha", 0.0)
    stor_val = shadow_prices_data.get("storage", {}).get("usd_per_extra_tonne", 0.0)
    cred_val = shadow_prices_data.get("credit_line", {}).get("usd_per_extra_dollar", 0.0)

    categories = [
        "Capital propio (USD/$)" if lang == "es" else "Own Capital (USD/$)",
        "Línea de crédito (USD/$)" if lang == "es" else "Credit Line (USD/$)",
        "Almacenaje (USD/t)" if lang == "es" else "Storage (USD/t)",
        "Tierra (USD/ha)" if lang == "es" else "Land (USD/ha)",
    ]
    values = [cap_val, cred_val, stor_val, land_val]

    fig = go.Figure(
        go.Bar(
            x=values,
            y=categories,
            orientation="h",
            marker={"color": ["#16a34a", "#2563eb", "#d97706", "#9333ea"]},
            text=[f"{v:.4f}" if v < 1 else f"{v:.2f}" for v in values],
            textposition="auto",
        )
    )

    fig.update_layout(
        title={
            "text": f"<b>{t['chart_resources_title']}</b><br><sup>{t['chart_resources_caption']}</sup>",
            "x": 0.02,
        },
        xaxis={"title": "Precio Sombra (USD)" if lang == "es" else "Shadow Price (USD)"},
        yaxis={"autorange": "reversed"},
        template="plotly_white",
        margin={"l": 150, "r": 30, "t": 75, "b": 50},
        height=320,
    )
    return fig


def create_cash_debt_chart(eval_data: dict, lang: str = "es") -> go.Figure:
    """Chart C: Area chart with cash surplus and debt across fortnights."""
    t = STRINGS.get(lang, STRINGS["es"])
    cash = eval_data.get("cash", [0] * FORTNIGHTS)
    debt = eval_data.get("debt", [0] * FORTNIGHTS)
    x_labels = [fortnight_name(p) for p in range(FORTNIGHTS)]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=cash,
            mode="lines",
            name="Caja libre (USD)" if lang == "es" else "Surplus Cash (USD)",
            line={"color": "#16a34a", "width": 2},
            fill="tozeroy",
            fillcolor="rgba(34, 197, 94, 0.25)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=debt,
            mode="lines",
            name="Deuda tomada (USD)" if lang == "es" else "Credit Used (USD)",
            line={"color": "#dc2626", "width": 2},
            fill="tozeroy",
            fillcolor="rgba(239, 68, 68, 0.25)",
        )
    )

    fig.update_layout(
        title={
            "text": f"<b>{t['chart_cash_debt_title']}</b><br><sup>{t['chart_cash_debt_caption']}</sup>",
            "x": 0.02,
        },
        xaxis={"title": "Quincena" if lang == "es" else "Fortnight", "tickangle": -45},
        yaxis={"title": "Monto (USD)" if lang == "es" else "Amount (USD)"},
        template="plotly_white",
        margin={"l": 60, "r": 30, "t": 75, "b": 70},
        height=380,
    )
    return fig


def create_sales_chart(eval_data: dict, lang: str = "es") -> go.Figure:
    """Chart 6: Stacked bar chart of grain sales by month."""
    t = STRINGS.get(lang, STRINGS["es"])
    sales_by_month = eval_data.get("sales_t_by_month", {})

    all_months_set = set()
    for crop, months_dict in sales_by_month.items():
        all_months_set.update(months_dict.keys())

    all_months = sorted(list(all_months_set))
    fig = go.Figure()

    colors = {"wheat": "#eab308", "corn": "#f97316", "soybean": "#22c55e", "sunflower": "#a855f7"}
    names_es = {"wheat": "Trigo", "corn": "Maíz", "soybean": "Soja", "sunflower": "Girasol"}

    for crop in ("wheat", "corn", "soybean", "sunflower"):
        if crop in sales_by_month:
            y_vals = [sales_by_month[crop].get(m, 0.0) for m in all_months]
            label = names_es.get(crop, crop) if lang == "es" else crop.capitalize()
            fig.add_trace(
                go.Bar(
                    x=all_months,
                    y=y_vals,
                    name=label,
                    marker_color=colors.get(crop, "#6b7280"),
                )
            )

    fig.update_layout(
        barmode="stack",
        title={
            "text": f"<b>{t['chart_sales_title']}</b><br><sup>{t['chart_sales_caption']}</sup>",
            "x": 0.02,
        },
        xaxis={"title": "Mes de Venta" if lang == "es" else "Sale Month"},
        yaxis={"title": "Toneladas (t)" if lang == "es" else "Tonnes (t)"},
        template="plotly_white",
        margin={"l": 50, "r": 30, "t": 75, "b": 50},
        height=320,
    )
    return fig


# ==============================================================================
# Backend Runner Function
# ==============================================================================

def parse_constraints_input(constraints_input: Any) -> list[dict]:
    """Parse constraints dataframe or list of lists into engine constraint format."""
    if constraints_input is None:
        return []
    rows = []
    if isinstance(constraints_input, pd.DataFrame):
        rows = constraints_input.values.tolist()
    elif isinstance(constraints_input, list):
        rows = constraints_input
    else:
        return []

    parsed: list[dict] = []
    for row in rows:
        if not row or len(row) < 3:
            continue
        ctype = str(row[0]).strip() if row[0] is not None else ""
        crop = str(row[1]).strip().lower() if row[1] is not None else ""
        val = row[2]
        if not ctype or not crop or ctype == "nan" or crop == "nan":
            continue

        item: dict[str, Any] = {"type": ctype, "crop": crop}
        try:
            num_val = float(val)
        except (ValueError, TypeError):
            continue

        if ctype in ("min_area", "max_area"):
            item["ha"] = num_val
        elif ctype == "min_share":
            item["share"] = num_val if num_val <= 1.0 else num_val / 100.0
        elif ctype == "forward_sale":
            item["tonnes"] = num_val
            month = str(row[3]).strip() if len(row) > 3 and row[3] is not None else ""
            price = row[4] if len(row) > 4 else None
            if month:
                item["month"] = month
            try:
                if price is not None:
                    item["price_usd_t"] = float(price)
            except (ValueError, TypeError):
                pass
        parsed.append(item)
    return parsed


def run_scenario(
    area_ha: float = 500.0,
    crops: list[str] | tuple[str, ...] = ("wheat", "corn", "soybean", "sunflower"),
    own_capital_usd: float = 50000.0,
    credit_line_usd: float = 100000.0,
    credit_rate_pct: float = 10.0,
    supplier_delay: int = 0,
    supplier_surcharge_pct: float = 0.0,
    storage_capacity_t: float = 1000.0,
    price_source: str = "MAGyP default",
    constraints_df: Any = None,
    lang: str = "es",
) -> dict:
    """Execute scenario evaluation, shadow prices, and generate charts."""
    cleaned_crops = [c for c in crops if c in CALENDAR]
    if not cleaned_crops:
        cleaned_crops = list(CALENDAR)

    scenario_payload: dict[str, Any] = {
        "area_ha": float(area_ha),
        "crops": cleaned_crops,
        "own_capital_usd": float(own_capital_usd),
        "credit_line_usd": float(credit_line_usd),
        "credit_rate_annual": float(credit_rate_pct) / 100.0,
        "input_payment_delay_fortnights": int(supplier_delay),
        "input_delay_surcharge": float(supplier_surcharge_pct) / 100.0,
        "storage_capacity_t": float(storage_capacity_t),
    }

    if price_source and price_source not in ("MAGyP default", "MAGyP por defecto"):
        scenario_payload["price_curve_source"] = price_source

    parsed_constraints = parse_constraints_input(constraints_df)
    if parsed_constraints:
        scenario_payload["constraints"] = parsed_constraints

    # Execute tools
    eval_raw = run_tool("evaluate_season", json.dumps({"scenario": scenario_payload}))
    eval_res = json.loads(eval_raw)
    if "error" in eval_res:
        raise ValueError(f"evaluate_season failed: {eval_res['error']}")

    shadow_raw = run_tool("shadow_prices", json.dumps({"scenario": scenario_payload}))
    shadow_res = json.loads(shadow_raw)
    if "error" in shadow_res:
        raise ValueError(f"shadow_prices failed: {shadow_res['error']}")

    build_raw = run_tool("build_scenario", json.dumps({"scenario": scenario_payload}))
    build_res = json.loads(build_raw)

    # 1. Build Plan Card markdown
    sc_meta = build_res.get("scenario", {})
    npv = eval_res.get("npv_usd", 0.0)
    unsown = eval_res.get("unsown_ha", 0.0)
    max_cred = eval_res.get("max_credit_usd", 0.0)
    max_fortnight = eval_res.get("max_credit_fortnight", "N/A")
    hectares = eval_res.get("hectares", {})

    crop_names_es = {"wheat": "Trigo", "corn": "Maíz", "soybean": "Soja", "sunflower": "Girasol"}

    plan_md_lines = [
        f"### **Valor Presente Neto (NPV):** USD {npv:,.2f}" if lang == "es" else f"### **Net Present Value (NPV):** USD {npv:,.2f}",
        "",
        "#### **Siembra propuesta:**" if lang == "es" else "#### **Crop Allocation:**",
    ]
    for c, ha in hectares.items():
        c_label = crop_names_es.get(c, c) if lang == "es" else c.capitalize()
        price_origin = sc_meta.get(f"price_{c}", {}).get("origin", "MAGyP")
        yield_origin = sc_meta.get(f"yield_{c}", {}).get("origin", "MAGyP")
        plan_md_lines.append(
            f"- **{c_label}**: {ha:.1f} ha *(rinde: {yield_origin}, precio: {price_origin})*"
            if lang == "es"
            else f"- **{c_label}**: {ha:.1f} ha *(yield: {yield_origin}, price: {price_origin})*"
        )
    if unsown > 1e-3:
        plan_md_lines.append(
            f"- *Superficie sin sembrar:* {unsown:.1f} ha" if lang == "es" else f"- *Unsown area:* {unsown:.1f} ha"
        )

    plan_md_lines.append("")
    plan_md_lines.append(
        f"**Pico de crédito utilizado:** USD {max_cred:,.2f} ({max_fortnight})"
        if lang == "es"
        else f"**Peak credit used:** USD {max_cred:,.2f} ({max_fortnight})"
    )

    if eval_res.get("price_source"):
        plan_md_lines.append(
            f"**Fuente de curvas:** {eval_res['price_source']}"
            if lang == "es"
            else f"**Price curve source:** {eval_res['price_source']}"
        )
    if eval_res.get("warning"):
        plan_md_lines.append(f"> ⚠️ *{eval_res['warning']}*")

    plan_markdown = "\n".join(plan_md_lines)

    # 2. Charts
    fig_a = create_internal_rate_chart(shadow_res, lang=lang)
    fig_b = create_resource_shadow_prices_chart(shadow_res, lang=lang)
    fig_c = create_cash_debt_chart(eval_res, lang=lang)
    fig_sales = create_sales_chart(eval_res, lang=lang)

    # 3. Constraints Table
    constraints_out = []
    for c in eval_res.get("constraints", []):
        constraints_out.append({
            "Tipo / Type": c.get("type"),
            "Cultivo / Crop": c.get("crop", ""),
            "Etiqueta / Label": c.get("label", ""),
            "¿Activa? / Binding?": "Sí / Yes" if c.get("binding") else "No",
            "Costo Oportunidad / Opp. Cost": f"{c.get('opportunity_cost', 0):.2f}",
            "Unidad / Unit": c.get("unit", ""),
            "Significado / Meaning": c.get("meaning", ""),
        })
    constraints_table_df = pd.DataFrame(constraints_out)

    return {
        "npv": npv,
        "npv_usd": npv,
        "plan": plan_markdown,
        "plan_dict": eval_res,
        "chart_rates": fig_a,
        "chart_resources": fig_b,
        "chart_cash_debt": fig_c,
        "chart_sales": fig_sales,
        "figures": (fig_a, fig_b, fig_c),
        "constraints": constraints_table_df,
        "evaluate_season": eval_res,
        "shadow_prices": shadow_res,
        "build_scenario": build_res,
    }


# ==============================================================================
# Gradio App Builder
# ==============================================================================

def build_app(api_key: str | None = None) -> gr.Blocks:
    """Construct the Gradio interface."""
    resolved_api_key = api_key if api_key is not None else os.environ.get("DORA_API_KEY", "")
    has_chat = bool(resolved_api_key)

    theme = gr.themes.Soft(primary_hue="green")

    with gr.Blocks(title="DORA Farm Agent") as app:
        app.theme = theme
        lang_state = gr.State("es")

        with gr.Row():
            with gr.Column(scale=9):
                gr.Markdown("# 🌾 DORA — Asistente de Planificación Agrícola")
                gr.Markdown("Optimización económica de campaña agrícola, análisis de cuellos de botella de capital y precios sombra.")
            with gr.Column(scale=3):
                lang_radio = gr.Radio(
                    choices=["Español", "English"],
                    value="Español",
                    label="Idioma / Language",
                )

        with gr.Tabs():
            # ------------------------------------------------------------------
            # TAB 1: SCENARIO
            # ------------------------------------------------------------------
            with gr.TabItem("📊 Escenario / Scenario", id="tab_scenario", elem_id="tab_scenario"):
                with gr.Row():
                    # Left column: Inputs
                    with gr.Column(scale=4):
                        gr.Markdown("### Parámetros de la Campaña")
                        area_input = gr.Number(value=500.0, label="Superficie total (ha)", minimum=1, maximum=100000)
                        crops_input = gr.CheckboxGroup(
                            choices=["wheat", "corn", "soybean", "sunflower"],
                            value=["wheat", "corn", "soybean", "sunflower"],
                            label="Cultivos disponibles",
                        )
                        own_cap_input = gr.Number(value=50000.0, label="Capital propio inicial (USD)")
                        cred_line_input = gr.Number(value=100000.0, label="Línea de crédito (USD)")
                        cred_rate_input = gr.Number(value=10.0, label="Tasa de interés anual del crédito (%)")
                        supplier_delay_input = gr.Dropdown(
                            choices=[0, 2, 4, 6],
                            value=0,
                            label="Plazo pago insumos (quincenas: 6 = 90 días)",
                        )
                        supplier_surcharge_input = gr.Number(value=0.0, label="Recargo de proveedor por plazo (%)")
                        storage_input = gr.Number(value=1000.0, label="Capacidad de almacenaje propio (t)")

                        curve_choices = ["MAGyP default"] + available_curves()
                        price_source_input = gr.Dropdown(
                            choices=curve_choices,
                            value="MAGyP default",
                            label="Fuente de curva de precios",
                        )

                        gr.Markdown("#### Restricciones específicas (opcional)")
                        constraints_input = gr.Dataframe(
                            headers=["Type", "Crop", "Value", "Month", "Price"],
                            datatype=["str", "str", "number", "str", "number"],
                            row_count=1,
                            value=[["", "", None, "", None]],
                            label="Restricciones (min_area, max_area, min_share, forward_sale)",
                        )

                        run_btn = gr.Button("⚡ Calcular Plan Óptimo", variant="primary", size="lg")

                        gr.Markdown("#### Escenarios de Ejemplo")
                        with gr.Row():
                            ex_btn_rationed = gr.Button("Capital restringido", size="sm")
                            ex_btn_supplier = gr.Button("Insumos a 90 días", size="sm")
                            ex_btn_corn = gr.Button("Contrato de maíz", size="sm")

                    # Right column: Outputs
                    with gr.Column(scale=8):
                        gr.Markdown("### Plan Propuesto y Diagnóstico")
                        plan_output = gr.Markdown("Presione **Calcular Plan Óptimo** para generar el plan.")

                        chart_rates_output = gr.Plot(label="¿Cuándo es escaso el capital?")
                        chart_resources_output = gr.Plot(label="¿Cuánto vale cada recurso escaso?")
                        chart_cash_debt_output = gr.Plot(label="¿Cómo evolucionan la caja y la deuda?")
                        chart_sales_output = gr.Plot(label="Ventas por mes")

                        gr.Markdown("#### Restricciones y Costo de Oportunidad")
                        constraints_output = gr.Dataframe(label="Análisis de Restricciones")

                def on_run(area, crops, own_cap, cred_line, cred_rate, delay, surcharge, stor, p_source, constr, lang):
                    res = run_scenario(
                        area_ha=area,
                        crops=crops,
                        own_capital_usd=own_cap,
                        credit_line_usd=cred_line,
                        credit_rate_pct=cred_rate,
                        supplier_delay=delay,
                        supplier_surcharge_pct=surcharge,
                        storage_capacity_t=stor,
                        price_source=p_source,
                        constraints_df=constr,
                        lang=lang,
                    )
                    return (
                        res["plan"],
                        res["chart_rates"],
                        res["chart_resources"],
                        res["chart_cash_debt"],
                        res["chart_sales"],
                        res["constraints"],
                    )

                run_btn.click(
                    fn=on_run,
                    inputs=[
                        area_input,
                        crops_input,
                        own_cap_input,
                        cred_line_input,
                        cred_rate_input,
                        supplier_delay_input,
                        supplier_surcharge_input,
                        storage_input,
                        price_source_input,
                        constraints_input,
                        lang_state,
                    ],
                    outputs=[
                        plan_output,
                        chart_rates_output,
                        chart_resources_output,
                        chart_cash_debt_output,
                        chart_sales_output,
                        constraints_output,
                    ],
                )

                # Example button handlers
                def load_example_rationed():
                    return 500.0, 50000.0, 100000.0, 0, 0.0, [["", "", None, "", None]]

                def load_example_supplier():
                    return 500.0, 50000.0, 100000.0, 6, 3.0, [["", "", None, "", None]]

                def load_example_corn():
                    return 500.0, 50000.0, 100000.0, 0, 0.0, [["min_area", "corn", 150, "", None]]

                ex_btn_rationed.click(
                    fn=load_example_rationed,
                    outputs=[area_input, own_cap_input, cred_line_input, supplier_delay_input, supplier_surcharge_input, constraints_input],
                )
                ex_btn_supplier.click(
                    fn=load_example_supplier,
                    outputs=[area_input, own_cap_input, cred_line_input, supplier_delay_input, supplier_surcharge_input, constraints_input],
                )
                ex_btn_corn.click(
                    fn=load_example_corn,
                    outputs=[area_input, own_cap_input, cred_line_input, supplier_delay_input, supplier_surcharge_input, constraints_input],
                )

            # ------------------------------------------------------------------
            # TAB 2: CHAT (Only included if DORA_API_KEY is present)
            # ------------------------------------------------------------------
            if has_chat:
                with gr.TabItem("💬 Chat con DORA / Chat", id="tab_chat", elem_id="tab_chat"):
                    chatbot = gr.Chatbot(height=500, label="DORA Farm Agent")
                    with gr.Row():
                        chat_msg = gr.Textbox(
                            placeholder="Consultá sobre tu plan de siembra...",
                            label="Tu mensaje",
                            scale=9,
                        )
                        chat_send = gr.Button("Enviar", variant="primary", scale=2)

                    agent_state = gr.State(None)

                    def respond(user_text: str, history: list, agent_instance: Any, lang: str):
                        global _daily_chat_counter
                        t = STRINGS.get(lang, STRINGS["es"])

                        if not user_text.strip():
                            return "", history, agent_instance

                        if _daily_chat_counter >= DAILY_CHAT_LIMIT:
                            history.append((user_text, t["chat_limit_reached"]))
                            return "", history, agent_instance

                        _daily_chat_counter += 1

                        if agent_instance is None:
                            from dora.agent import Agent
                            agent_instance = Agent()

                        reply = agent_instance.ask(user_text)

                        # Badge formatting
                        if reply.verified:
                            badge = t["chat_badge_verified"]
                        else:
                            unsupp = ", ".join(u.text for u in reply.unsupported)
                            badge = t["chat_badge_unverified"].format(unsupported=unsupp)

                        # Tool calls detail
                        tool_calls_text = ""
                        if reply.tool_calls:
                            summary_text = t["tool_calls_summary"].format(n=len(reply.tool_calls))
                            call_items = []
                            for c in reply.tool_calls:
                                call_items.append(f"- **{c.get('tool')}**: `{c.get('arguments')}`")
                            tool_calls_text = f"\n\n<details><summary>{summary_text}</summary>\n\n" + "\n".join(call_items) + "\n</details>"

                        bot_message = f"{badge}\n\n{reply.text}{tool_calls_text}"
                        history.append((user_text, bot_message))
                        return "", history, agent_instance

                    chat_send.click(
                        fn=respond,
                        inputs=[chat_msg, chatbot, agent_state, lang_state],
                        outputs=[chat_msg, chatbot, agent_state],
                    )
                    chat_msg.submit(
                        fn=respond,
                        inputs=[chat_msg, chatbot, agent_state, lang_state],
                        outputs=[chat_msg, chatbot, agent_state],
                    )

            # Language switch
            def on_lang_change(selected_lang: str):
                return "es" if selected_lang == "Español" else "en"

            lang_radio.change(fn=on_lang_change, inputs=[lang_radio], outputs=[lang_state])

        app.has_chat = has_chat
    return app


if __name__ == "__main__":
    demo = build_app()
    demo.launch(theme=getattr(demo, "theme", None))
