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

from dora.geo import field_from_map
from dora.prices import available_curves
from dora.scenario import CALENDAR, FORTNIGHTS, REGIONS, fortnight_name, fortnightly_rate, normalize_region
from dora.tools import run_tool

DAILY_CHAT_LIMIT = 200
_daily_chat_counter = 0

MONTHS_ES = ["may", "jun", "jul", "ago", "sep", "oct", "nov", "dic", "ene", "feb", "mar", "abr"]

CROP_TRANSLATION_TO_EN = {
    "trigo": "wheat",
    "maíz": "corn",
    "maiz": "corn",
    "soja": "soybean",
    "girasol": "sunflower",
    "wheat": "wheat",
    "corn": "corn",
    "soybean": "soybean",
    "sunflower": "sunflower",
}

CROP_TRANSLATION_TO_ES = {
    "wheat": "trigo",
    "corn": "maíz",
    "soybean": "soja",
    "sunflower": "girasol",
}


def format_number_es(val: float | int, decimals: int | None = None) -> str:
    """Format numbers in Argentine style: dot thousands, comma decimal.

    88186.6 -> '88.186,60'
    100000 -> '100.000'
    """
    if decimals is None:
        if isinstance(val, int):
            return f"{val:,}".replace(",", ".")
        s = f"{float(val):,.2f}"
    else:
        s = f"{float(val):,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fortnight_name_es(p: int) -> str:
    """Return Spanish representation of fortnight p.

    For example, index 15 is '2ª quincena de dic'.
    """
    month = MONTHS_ES[(p // 2) % 12]
    part = "1ª" if p % 2 == 0 else "2ª"
    suffix = " (año 2)" if p >= 24 else ""
    return f"{part} quincena de {month}{suffix}"


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
        "supplier_delay": "Plazo pago insumos (quincenas: 6 = 90 días)",
        "supplier_surcharge": "Recargo de proveedor (%)",
        "storage_capacity_t": "Capacidad de almacenaje propio (t)",
        "price_source": "Fuente de precios",
        "magyp_default": "MAGyP por defecto",
        "constraints_header": "Restricciones del productor (opcional)",
        "run_button": "Calcular Plan Óptimo",
        "examples_header": "Ejemplos rápidos",
        "ex_rationed": "Capital restringido",
        "ex_supplier": "Insumos a 90 días",
        "ex_corn": "Contrato de maíz",
        "outputs_header": "Resultados de la Campaña",
        "plan_title": "Plan Propuesto y Diagnóstico",
        "chart_rates_title": "¿Cuánto vale un dólar en cada quincena?",
        "chart_rates_caption": "Si la línea verde está arriba de la gris, en esa quincena la plata vale más que en el banco: el capital escasea.",
        "chart_resources_title": "¿Cuánto vale un dólar adicional de capital o crédito?",
        "chart_resources_caption": "Retorno en valor presente por cada dólar extra de capital propio o línea de crédito comercial.",
        "chart_cash_debt_title": "¿Cómo evolucionan la caja y la deuda?",
        "chart_cash_debt_caption": "Evolución quincenal de los fondos líquidos en caja y la utilización de la línea de crédito comercial.",
        "chart_sales_title": "¿Cuándo y qué se vende?",
        "chart_sales_caption": "Distribución mensual de ventas físicas de grano según la capacidad de almacenaje y precios esperados.",
        "constraints_title": "Estado de las Restricciones y Costo de Oportunidad",
        "chat_input_placeholder": "Hacé una pregunta sobre la campaña (ej: ¿Por qué no sembramos más trigo?)...",
        "chat_badge_verified": "✅ **verificado: every number comes from the engine**",
        "chat_badge_unverified": "⚠️ **not verified** (números sin respaldo: {unsupported})",
        "chat_limit_reached": "Se ha alcanzado el límite diario de 200 consultas. Por favor, intente nuevamente mañana.",
        "tool_calls_summary": "Detalle de llamadas a herramientas ({n})",
        "source_magyp": "Rindes y precios: MAGyP, márgenes jun-2026, sudeste de Buenos Aires",
        "source_curve": "Curva de precios: {source}, al {as_of}",
        "land_card_inactive": "**Tierra:** 0 USD/ha — *no es una restricción activa*",
        "land_card_active": "**Tierra:** {val} USD/ha — *cada hectárea adicional aportaría {val} USD de valor presente*",
        "storage_card_inactive": "**Almacenaje:** 0 USD/t — *no es una restricción activa*",
        "storage_card_active": "**Almacenaje:** {val} USD/t — *cada tonelada adicional aportaría {val} USD de valor presente*",
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
        "supplier_delay": "Supplier Payment Delay (fortnights: 6 = 90 days)",
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
        "chart_rates_title": "What is one dollar worth in each fortnight?",
        "chart_rates_caption": "If the green line is above the gray line, money is worth more than in the bank in that fortnight: capital is scarce.",
        "chart_resources_title": "What is an extra dollar of capital or credit worth?",
        "chart_resources_caption": "Return in present value for each additional dollar of own capital or credit line.",
        "chart_cash_debt_title": "How do cash and debt evolve?",
        "chart_cash_debt_caption": "Fortnightly surplus cash vs credit line usage across the season.",
        "chart_sales_title": "When and what is sold?",
        "chart_sales_caption": "Monthly grain sales by crop under storage constraints and price expectations.",
        "constraints_title": "Farmer Constraints & Opportunity Cost",
        "chat_input_placeholder": "Ask a question about the season (e.g. Why isn't more wheat sown?)...",
        "chat_badge_verified": "✅ **verified: every number comes from the engine**",
        "chat_badge_unverified": "⚠️ **not verified** (unsupported numbers: {unsupported})",
        "chat_limit_reached": "The daily cap of 200 questions has been reached. Please try again tomorrow.",
        "tool_calls_summary": "Tool calls details ({n})",
        "source_magyp": "Yields and prices: MAGyP margins report, Jun-2026, Southeast Buenos Aires",
        "source_curve": "Price curve: {source}, as of {as_of}",
        "land_card_inactive": "**Land:** 0 USD/ha — *not an active constraint*",
        "land_card_active": "**Land:** {val} USD/ha — *each extra hectare adds {val} USD of present value*",
        "storage_card_inactive": "**Storage:** 0 USD/t — *not an active constraint*",
        "storage_card_active": "**Storage:** {val} USD/t — *each extra tonne adds {val} USD of present value*",
    },
}


# ==============================================================================
# Chart Generators
# ==============================================================================

def create_internal_rate_chart(shadow_prices_data: dict, lang: str = "es") -> go.Figure:
    """Chart A: Value today of one dollar in each fortnight vs bank baseline.

    Plots cash dual λ_p vs (1 + r)^(-p), shading the scarcity area where λ_p > market.
    Internal rate is exposed as hover text.
    """
    t = STRINGS.get(lang, STRINGS["es"])
    fortnights_info = shadow_prices_data.get("by_fortnight", [])
    market_rate_annual = shadow_prices_data.get("market_rate_annual", 0.04)
    rf = fortnightly_rate(market_rate_annual)

    n_points = len(fortnights_info)
    x_labels = [
        fortnight_name_es(p) if lang == "es" else fortnight_name(p)
        for p in range(n_points)
    ]
    cash_vals = [
        row.get("usd_today_per_dollar", 1.0)
        for row in fortnights_info
    ]
    market_vals = [(1.0 + rf) ** (-p) for p in range(n_points)]
    rates = [row.get("internal_rate_annual", 0.0) * 100.0 for row in fortnights_info]

    fig = go.Figure()

    # Base line: Value of dollar in bank (1 + r)^(-p)
    hover_market = [
        f"{x}<br>Banco / Bank: USD {m:.4f}" if lang == "es" else f"{x}<br>Bank: USD {m:.4f}"
        for x, m in zip(x_labels, market_vals)
    ]
    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=market_vals,
            mode="lines",
            name="En el banco (tasa de mercado)" if lang == "es" else "In bank (market rate)",
            line={"color": "#9ca3af", "dash": "dot", "width": 2},
            hoverinfo="text",
            hovertext=hover_market,
        )
    )

    # Scarcity line: Value of dollar on the farm (λ_p)
    hover_cash = [
        f"{x}<br>Valor en el campo: USD {c:.4f}<br>Tasa interna anualizada: {r:.1f}%"
        if lang == "es"
        else f"{x}<br>Value on farm: USD {c:.4f}<br>Annualized internal rate: {r:.1f}%"
        for x, c, r in zip(x_labels, cash_vals, rates)
    ]
    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=cash_vals,
            mode="lines+markers",
            name="En el campo (valor hoy de $1)" if lang == "es" else "On farm (today's value of $1)",
            line={"color": "#16a34a", "width": 2.5},
            marker={"size": 6, "color": "#15803d"},
            fill="tonexty",
            fillcolor="rgba(34, 197, 94, 0.2)",
            hoverinfo="text",
            hovertext=hover_cash,
        )
    )

    fig.update_layout(
        title={
            "text": f"<b>{t['chart_rates_title']}</b><br><sup>{t['chart_rates_caption']}</sup>",
            "x": 0.02,
        },
        xaxis={"title": "Quincena" if lang == "es" else "Fortnight", "tickangle": -45},
        yaxis={"title": "Valor hoy de $1 disponible en p (USD)" if lang == "es" else "Value today of $1 in p (USD)"},
        template="plotly_white",
        margin={"l": 60, "r": 30, "t": 75, "b": 70},
        height=380,
        showlegend=True,
    )
    return fig


def create_resource_shadow_prices_chart(shadow_prices_data: dict, lang: str = "es") -> go.Figure:
    """Chart B: Horizontal bar chart for the two per-dollar shadow prices only."""
    t = STRINGS.get(lang, STRINGS["es"])

    cap_val = shadow_prices_data.get("own_capital", {}).get("usd_per_extra_dollar", 0.0)
    cred_val = shadow_prices_data.get("credit_line", {}).get("usd_per_extra_dollar", 0.0)

    categories = [
        "Línea de crédito (USD/$)" if lang == "es" else "Credit Line (USD/$)",
        "Capital propio (USD/$)" if lang == "es" else "Own Capital (USD/$)",
    ]
    values = [cred_val, cap_val]

    fig = go.Figure(
        go.Bar(
            x=values,
            y=categories,
            orientation="h",
            marker={"color": ["#2563eb", "#16a34a"]},
            text=[f"{v:.4f}" for v in values],
            textposition="auto",
        )
    )

    fig.update_layout(
        title={
            "text": f"<b>{t['chart_resources_title']}</b><br><sup>{t['chart_resources_caption']}</sup>",
            "x": 0.02,
        },
        xaxis={"title": "USD extra de valor presente por cada dólar" if lang == "es" else "Extra USD in present value per dollar"},
        template="plotly_white",
        margin={"l": 150, "r": 30, "t": 75, "b": 50},
        height=240,
    )
    return fig


def create_cash_debt_chart(eval_data: dict, lang: str = "es") -> go.Figure:
    """Chart C: Area chart with cash surplus and debt across fortnights."""
    t = STRINGS.get(lang, STRINGS["es"])
    cash = eval_data.get("cash", [0] * FORTNIGHTS)
    debt = eval_data.get("debt", [0] * FORTNIGHTS)
    x_labels = [
        fortnight_name_es(p) if lang == "es" else fortnight_name(p)
        for p in range(FORTNIGHTS)
    ]

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
        raw_crop = str(row[1]).strip().lower() if row[1] is not None else ""
        crop = CROP_TRANSLATION_TO_EN.get(raw_crop, raw_crop)
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
    region: str = "southeast_buenos_aires",
    owned_ha: float | None = None,
    max_rent_in_ha: float = 0.0,
    allow_rent_out: bool = True,
    max_buy_ha: float = 0.0,
) -> dict:
    """Execute scenario evaluation, shadow prices, and generate charts."""
    t = STRINGS.get(lang, STRINGS["es"])

    norm_reg = normalize_region(region)
    reg_crops = REGIONS[norm_reg]["crops"]

    # Translate crops to English for engine
    cleaned_crops = [
        CROP_TRANSLATION_TO_EN.get(str(c).strip().lower(), str(c).strip().lower())
        for c in crops
    ]
    cleaned_crops = [c for c in cleaned_crops if c in reg_crops]
    if not cleaned_crops:
        cleaned_crops = list(reg_crops)

    scenario_payload: dict[str, Any] = {
        "area_ha": float(area_ha),
        "crops": cleaned_crops,
        "own_capital_usd": float(own_capital_usd),
        "credit_line_usd": float(credit_line_usd),
        "credit_rate_annual": float(credit_rate_pct) / 100.0,
        "input_payment_delay_fortnights": int(supplier_delay),
        "input_delay_surcharge": float(supplier_surcharge_pct) / 100.0,
        "storage_capacity_t": float(storage_capacity_t),
        "region": norm_reg,
    }

    if owned_ha is not None:
        scenario_payload["owned_ha"] = float(owned_ha)
    if max_rent_in_ha > 0:
        scenario_payload["max_rent_in_ha"] = float(max_rent_in_ha)
    scenario_payload["allow_rent_out"] = bool(allow_rent_out)
    if max_buy_ha > 0:
        scenario_payload["max_buy_ha"] = float(max_buy_ha)

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

    # 1. Build Plan Card with shorter origins and Spanish formatting
    sc_meta = build_res.get("scenario", {})
    npv = eval_res.get("npv_usd", 0.0)
    unsown = eval_res.get("unsown_ha", 0.0)
    max_cred = eval_res.get("max_credit_usd", 0.0)
    hectares = eval_res.get("hectares", {})

    # Peak credit fortnight in selected language
    debt_list = eval_res.get("debt", [])
    if debt_list and max(debt_list) > 1e-6:
        peak_idx = max(range(len(debt_list)), key=lambda p: debt_list[p])
        max_fortnight_str = (
            fortnight_name_es(peak_idx) if lang == "es" else fortnight_name(peak_idx)
        )
    else:
        max_fortnight_str = eval_res.get("max_credit_fortnight", "N/A")

    crop_names_display = {
        "wheat": "Trigo" if lang == "es" else "Wheat",
        "corn": "Maíz" if lang == "es" else "Corn",
        "soybean": "Soja" if lang == "es" else "Soybean",
        "sunflower": "Girasol" if lang == "es" else "Sunflower",
    }

    npv_fmt = format_number_es(npv) if lang == "es" else f"{npv:,.2f}"
    cred_fmt = format_number_es(int(round(max_cred))) if lang == "es" else f"{max_cred:,.0f}"

    plan_md_lines = [
        f"### **Valor Presente Neto (NPV):** USD {npv_fmt}"
        if lang == "es"
        else f"### **Net Present Value (NPV):** USD {npv_fmt}",
        "",
        "#### **Siembra propuesta:**" if lang == "es" else "#### **Crop Allocation:**",
    ]

    has_farmer_override = False
    for c, ha in hectares.items():
        c_label = crop_names_display.get(c, c)
        ha_fmt = format_number_es(ha, 1) if lang == "es" else f"{ha:.1f}"

        # Check if farmer explicitly gave values
        price_orig = sc_meta.get(f"price_{c}", {}).get("origin", "")
        yield_orig = sc_meta.get(f"yield_{c}", {}).get("origin", "")
        farmer_tags = []
        if price_orig == "farmer":
            farmer_tags.append("precio informado" if lang == "es" else "farmer price")
            has_farmer_override = True
        if yield_orig == "farmer":
            farmer_tags.append("rinde informado" if lang == "es" else "farmer yield")
            has_farmer_override = True

        tag_str = f" *({', '.join(farmer_tags)})*" if farmer_tags else ""
        plan_md_lines.append(f"- **{c_label}**: {ha_fmt} ha{tag_str}")

    if unsown > 1e-3:
        unsown_fmt = format_number_es(unsown, 1) if lang == "es" else f"{unsown:.1f}"
        plan_md_lines.append(
            f"- *Superficie sin sembrar:* {unsown_fmt} ha"
            if lang == "es"
            else f"- *Unsown area:* {unsown_fmt} ha"
        )

    plan_md_lines.append("")
    plan_md_lines.append(
        f"**Pico de crédito utilizado:** USD {cred_fmt} ({max_fortnight_str})"
        if lang == "es"
        else f"**Peak credit used:** USD {cred_fmt} ({max_fortnight_str})"
    )

    # Shorter origins: one line per source used
    plan_md_lines.append("")
    plan_md_lines.append("---")
    plan_md_lines.append("**Fuentes:**" if lang == "es" else "**Sources:**")
    if eval_res.get("price_source"):
        plan_md_lines.append(f"- {t['source_curve'].format(source=eval_res['price_source'], as_of='')}")
    else:
        if norm_reg == "iowa":
            plan_md_lines.append("- Iowa State University Extension (Ag Decision Maker A1-20)")
        else:
            plan_md_lines.append(f"- {t['source_magyp']}")
    if has_farmer_override:
        plan_md_lines.append(
            "- Valores propios del productor marcados arriba"
            if lang == "es"
            else "- Custom farmer inputs marked above"
        )

    if eval_res.get("warning"):
        plan_md_lines.append(f"> ⚠️ *{eval_res['warning']}*")

    plan_markdown = "\n".join(plan_md_lines)

    # 2. Charts
    fig_a = create_internal_rate_chart(shadow_res, lang=lang)
    fig_b = create_resource_shadow_prices_chart(shadow_res, lang=lang)
    fig_c = create_cash_debt_chart(eval_res, lang=lang)
    fig_sales = create_sales_chart(eval_res, lang=lang)

    # Value cards for Land and Storage (Fix 2)
    land_val = shadow_res.get("land", {}).get("usd_per_extra_ha", 0.0)
    stor_val = shadow_res.get("storage", {}).get("usd_per_extra_tonne", 0.0)

    if land_val < 1e-4:
        land_card = t["land_card_inactive"]
    else:
        land_fmt = format_number_es(land_val, 2) if lang == "es" else f"{land_val:.2f}"
        land_card = t["land_card_active"].format(val=land_fmt)

    if stor_val < 1e-4:
        storage_card = t["storage_card_inactive"]
    else:
        stor_fmt = format_number_es(stor_val, 2) if lang == "es" else f"{stor_val:.2f}"
        storage_card = t["storage_card_active"].format(val=stor_fmt)

    resource_cards_md = f"#### Otros Recursos:\n- {land_card}\n- {storage_card}"

    # 3. Constraints Table
    constraints_out = []
    for c in eval_res.get("constraints", []):
        cost = c.get("opportunity_cost", 0)
        cost_fmt = format_number_es(cost, 2) if lang == "es" else f"{cost:.2f}"
        crop_val = c.get("crop", "")
        crop_display = CROP_TRANSLATION_TO_ES.get(crop_val, crop_val) if lang == "es" else crop_val

        constraints_out.append({
            "Tipo / Type": c.get("type"),
            "Cultivo / Crop": crop_display,
            "Etiqueta / Label": c.get("label", ""),
            "¿Activa? / Binding?": "Sí / Yes" if c.get("binding") else "No",
            "Costo Oportunidad / Opp. Cost": cost_fmt,
            "Unidad / Unit": c.get("unit", ""),
            "Significado / Meaning": c.get("meaning", ""),
        })
    constraints_table_df = pd.DataFrame(constraints_out)

    tax_raw = run_tool("tax_wedge", json.dumps({"scenario": scenario_payload}))
    tax_res = json.loads(tax_raw) if tax_raw else {}

    lt = eval_res.get("land_tenure", {})
    comp = eval_res.get("land_comparison", "")
    roc = lt.get("return_on_capital", 0.0) * 100.0
    roc_land = lt.get("return_on_capital_and_land", 0.0) * 100.0

    land_card_md = (
        f"### Decisiones de Tenencia y Tierra / Land Decisions:\n"
        f"- **Tierra propia / Owned:** {lt.get('owned_ha', area_ha)} ha | "
        f"**Alquilada hacia adentro / Rented in:** {lt.get('rent_in_ha', 0)} ha | "
        f"**Alquilada hacia afuera / Rented out:** {lt.get('rent_out_ha', 0)} ha | "
        f"**Comprada / Bought:** {lt.get('buy_ha', 0)} ha\n"
        f"- **Retorno sobre capital operativo / ROC:** {roc:.2f}%\n"
        f"- **Retorno sobre capital y tierra / ROC & Land:** {roc_land:.2f}%\n"
        f"- **Comparación de valor / Intuition:** *{comp}*"
    )

    tax_rows = []
    for tx in tax_res.get("taxes", []):
        tax_rows.append({
            "Impuesto / Tax": tx.get("name"),
            "Monto / USD": format_number_es(tx.get("usd", 0), 2) if lang == "es" else f"{tx.get('usd', 0):,.2f}",
            "% Ingreso Bruto / % Gross Revenue": f"{tx.get('percent_gross_revenue', 0):.2f}%",
            "Fuente / Source": tx.get("source", ""),
        })
    tax_wedge_df = pd.DataFrame(tax_rows)

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
        "resource_cards": resource_cards_md,
        "constraints": constraints_table_df,
        "evaluate_season": eval_res,
        "shadow_prices": shadow_res,
        "build_scenario": build_res,
        "land_card": land_card_md,
        "tax_wedge_table": tax_wedge_df,
        "tax_wedge_res": tax_res,
        "tax_disclaimer": tax_res.get("disclaimer", ""),
    }


LEAFLET_HEAD = """
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css" />
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css" />
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.js"></script>
<script>
function initDoraLeafletMap() {
  var container = document.getElementById('dora-map');
  if (!container) return;
  if (window._doraMapInitialized) {
    if (window._doraMap) window._doraMap.invalidateSize();
    return;
  }
  if (typeof L === 'undefined' || typeof L.Control.Draw === 'undefined') {
    setTimeout(initDoraLeafletMap, 200);
    return;
  }

  var osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  });
  var esri = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 19,
    attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
  });

  var map = L.map('dora-map', {
    center: [-37.85, -58.25],
    zoom: 12,
    layers: [osm]
  });
  window._doraMap = map;
  window._doraMapInitialized = true;

  var baseLayers = {
    "OpenStreetMap": osm,
    "Esri Satelital / Satellite": esri
  };
  L.control.layers(baseLayers).addTo(map);

  var drawnItems = new L.FeatureGroup();
  map.addLayer(drawnItems);

  var drawControl = new L.Control.Draw({
    draw: {
      polygon: {
        allowIntersection: false,
        showArea: true
      },
      rectangle: true,
      circle: false,
      circlemarker: false,
      marker: false,
      polyline: false
    },
    edit: {
      featureGroup: drawnItems
    }
  });
  map.addControl(drawControl);

  map.on(L.Draw.Event.CREATED, function (e) {
    drawnItems.clearLayers();
    drawnItems.addLayer(e.layer);
    var geojson = e.layer.toGeoJSON();
    var inputEl = document.querySelector('#dora_polygon_json textarea') || document.querySelector('#dora_polygon_json input');
    if (inputEl) {
      inputEl.value = JSON.stringify(geojson.geometry);
      inputEl.dispatchEvent(new Event('input', { bubbles: true }));
    }
  });

  setTimeout(function() { map.invalidateSize(); }, 350);
}

function initObservatoryLeafletMap() {
  var container = document.getElementById('observatory-map');
  if (!container) return;
  if (window._observatoryMapInitialized) {
    if (window._observatoryMap) window._observatoryMap.invalidateSize();
    return;
  }
  if (typeof L === 'undefined') {
    setTimeout(initObservatoryLeafletMap, 200);
    return;
  }

  var osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: '&copy; OpenStreetMap contributors'
  });

  var map = L.map('observatory-map', {
    center: [-10.0, -60.0],
    zoom: 3,
    layers: [osm]
  });
  window._observatoryMap = map;
  window._observatoryMapInitialized = true;

  var raw = container.getAttribute('data-regions');
  var regionsData = raw ? JSON.parse(raw) : [];

  function getColor(roc) {
    return roc > 35 ? '#006837' :
           roc > 20 ? '#31a354' :
           roc > 10 ? '#78c679' :
                      '#e5f5e0';
  }

  regionsData.forEach(function(r) {
    if (!r.coords || r.coords.length < 2) return;
    var marker = L.circleMarker(r.coords, {
      radius: 12,
      fillColor: getColor(r.return_on_capital_pct),
      color: '#1b4d24',
      weight: 2,
      opacity: 1,
      fillOpacity: 0.85
    }).addTo(map);

    var popupHtml = '<b>' + r.name + '</b><br>' +
      'Retorno capital / ROC: <b>' + r.return_on_capital_pct + '%</b><br>' +
      'NPV/ha: <b>USD ' + r.npv_per_ha + '</b><br>' +
      'Puerto / Port: ' + r.port + ' (' + r.distance_km + ' km)<br>' +
      'Flete / Freight: USD ' + r.freight_usd_t + '/t<br>' +
      'Fuente / Source: ' + r.price_source;
    marker.bindPopup(popupHtml);
  });

  var legend = L.control({position: 'bottomright'});
  legend.onAdd = function (map) {
    var div = L.DomUtil.create('div', 'info legend');
    div.style.background = 'white';
    div.style.padding = '6px 10px';
    div.style.borderRadius = '5px';
    div.style.border = '1px solid #ccc';
    div.style.fontSize = '12px';
    div.innerHTML = '<b>Retorno sobre Capital (%)</b><br>' +
      '<i style="background:#006837; width:12px; height:12px; display:inline-block; margin-right:4px;"></i> &gt; 35%<br>' +
      '<i style="background:#31a354; width:12px; height:12px; display:inline-block; margin-right:4px;"></i> 20% &ndash; 35%<br>' +
      '<i style="background:#78c679; width:12px; height:12px; display:inline-block; margin-right:4px;"></i> 10% &ndash; 20%<br>' +
      '<i style="background:#e5f5e0; width:12px; height:12px; display:inline-block; margin-right:4px; border:1px solid #aaa;"></i> &lt; 10%';
    return div;
  };
  legend.addTo(map);

  setTimeout(function() { map.invalidateSize(); }, 350);
}

document.addEventListener('DOMContentLoaded', function() {
  setTimeout(initDoraLeafletMap, 500);
  setTimeout(initObservatoryLeafletMap, 700);
});
setInterval(function() {
  if (!window._doraMapInitialized) {
    initDoraLeafletMap();
  }
  if (!window._observatoryMapInitialized) {
    initObservatoryLeafletMap();
  } else if (window._observatoryMap) {
    window._observatoryMap.invalidateSize();
  }
}, 1000);
</script>
"""

LEAFLET_CONTAINER_HTML = """
<div style="margin-bottom: 6px;">
  <small style="color: #555;"><b>Delimitar lote en el mapa (opcional)</b>: use la herramienta poligonal o rectangular. El área y la región se calcularán automáticamente.</small>
</div>
<div id="dora-map" style="width: 100%; height: 320px; border-radius: 8px; border: 1px solid #ccc; z-index: 1;"></div>
"""


def make_observatory_html(map_items: list[dict]) -> str:
    escaped_json = json.dumps(map_items).replace("'", "&#39;")
    return f"""
<div style="margin-bottom: 6px;">
  <small style="color: #555;"><b>Mapa del Observatorio Regional</b>: haga clic en los marcadores para ver el retorno sobre el capital y flete de cada región.</small>
</div>
<div id="observatory-map" data-regions='{escaped_json}' style="width: 100%; height: 380px; border-radius: 8px; border: 1px solid #ccc; z-index: 1;"></div>
"""


def get_observatory_ui_data(force_run: bool = False):
    from pathlib import Path
    from dora.observatory import run_observatory

    latest_file = Path("observatory/latest.json")
    if latest_file.is_file() and not force_run:
        try:
            with open(latest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = run_observatory(save=True)
    else:
        data = run_observatory(save=True)

    date_str = data.get("date", "2026-10-27")
    commentary = data.get("commentary")
    regions = data.get("regions", {})

    map_items = []
    table_rows = []

    for key, r in regions.items():
        map_items.append({
            "key": key,
            "name": r.get("name", key),
            "coords": r.get("coords", [0.0, 0.0]),
            "return_on_capital_pct": r.get("return_on_capital_pct", 0),
            "npv_per_ha": r.get("npv_per_ha", 0),
            "port": r.get("port", ""),
            "distance_km": r.get("distance_km", 0),
            "freight_usd_t": r.get("freight_usd_t", 0),
            "price_source": r.get("price_source", ""),
        })

        crop_mix_str = ", ".join(f"{c}: {h} ha" for c, h in r.get("crop_mix", {}).items())
        roc_pct = r.get("return_on_capital_pct", 0)
        roc_land_pct = r.get("return_on_capital_and_land_pct", roc_pct)
        land_price = r.get("land_price_usd_ha", 0)

        table_rows.append({
            "Región / Region": r.get("name", key),
            "Cultivos / Crop Mix": crop_mix_str,
            "NPV/ha (USD)": r.get("npv_per_ha", 0),
            "Retorno Capital / ROC (%)": f"{roc_pct:.2f}%",
            "Retorno Cap. + Tierra / ROC & Land (%)": f"{roc_land_pct:.2f}%",
            "Precio Tierra / Land Price (USD/ha)": land_price,
            "Sombra Capital / Cap. Shadow": r.get("capital_shadow_price", 0),
            "Sombra Tierra / Land Shadow (USD/ha)": r.get("land_shadow_price_usd_ha", 0),
            "Flete / Freight (USD/t)": r.get("freight_usd_t", 0),
            "Puerto / Port": f"{r.get('port', '')} ({r.get('distance_km', 0)} km)",
            "Fuente Precios / Price Source": r.get("price_source", ""),
        })

    df = pd.DataFrame(table_rows)

    fig = go.Figure()
    palette = {
        "southeast_buenos_aires": "#2ca02c",
        "pampas_core": "#1f77b4",
        "iowa": "#ff7f0e",
        "mato_grosso": "#9467bd",
    }

    for reg_key, r in regions.items():
        color = palette.get(reg_key, "#333333")
        reg_rates = r.get("internal_rates", [])
        x_vals = [f"{ir['month']} Q{ir['fortnight'] % 2 + 1}" for ir in reg_rates]
        y_vals = [round(ir["rate_annual"] * 100.0, 2) for ir in reg_rates]

        fig.add_trace(go.Scatter(
            x=x_vals,
            y=y_vals,
            mode="lines+markers",
            name=f"{r.get('name', reg_key)}",
            line=dict(color=color, width=2.5),
            marker=dict(size=4),
        ))

    fig.add_hline(
        y=4.0,
        line_dash="dash",
        line_color="#7f7f7f",
        annotation_text="Tasa de mercado / Market rate (4.0%)",
        annotation_position="top right",
    )

    fig.update_layout(
        title="Tasa Interna de Oportunidad de Capital por Quincena (% anual)",
        xaxis_title="Mes Calendario y Quincena",
        yaxis_title="Tasa anual (%)",
        hovermode="x unified",
        template="plotly_white",
        height=450,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    banner_md = f"### 🌐 Referencia Publicada del Observatorio\n" \
                f"**Referencia:** [`observatory/latest.json`](file:///d:/projects/dora-hackathon/observatory/latest.json) · **Fecha:** `{date_str}`\n"
    if commentary:
        banner_md += f"\n> 📝 **Comentario de Mercado (verificado):**\n> {commentary}\n"

    return banner_md, make_observatory_html(map_items), df, fig


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
        app.head = LEAFLET_HEAD
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

                        with gr.Accordion("🗺️ Delimitar Campo en el Mapa / Field on Map", open=True):
                            gr.HTML(LEAFLET_CONTAINER_HTML)
                            polygon_input = gr.Textbox(
                                elem_id="dora_polygon_json",
                                label="GeoJSON Polygon (al dibujar en el mapa o pegar)",
                                lines=2,
                                placeholder='{"type": "Polygon", "coordinates": [[[lon, lat], ...]]}',
                            )
                            apply_map_btn = gr.Button("📍 Aplicar Campo del Mapa / Apply Field", variant="secondary", size="sm")
                            map_status = gr.Markdown("")

                        region_input = gr.Dropdown(
                            choices=[
                                ("Sudeste de Buenos Aires", "southeast_buenos_aires"),
                                ("Iowa, USA", "iowa"),
                            ],
                            value="southeast_buenos_aires",
                            label="Región / Region",
                        )

                        area_input = gr.Number(value=500.0, label="Superficie total (ha)", minimum=1, maximum=100000)
                        crops_input = gr.CheckboxGroup(
                            choices=["trigo", "maíz", "soja", "girasol"],
                            value=["trigo", "maíz", "soja", "girasol"],
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

                        gr.Markdown("#### Decisiones de Tierra y Alquiler / Land Tenure (opcional)")
                        owned_input = gr.Number(value=None, label="Superficie propia (ha, owned_ha, por defecto = total)")
                        rent_in_input = gr.Number(value=0.0, label="Máx. alquiler hacia adentro (ha, max_rent_in_ha)")
                        buy_input = gr.Number(value=0.0, label="Máx. compra de tierra (ha, max_buy_ha)")
                        rent_out_input = gr.Checkbox(value=True, label="Permitir alquilar hacia afuera (allow_rent_out)")

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

                        land_card_output = gr.Markdown("### Decisiones de Tenencia y Tierra")
                        chart_rates_output = gr.Plot(label="¿Cuánto vale un dólar en cada quincena?")
                        chart_resources_output = gr.Plot(label="¿Cuánto vale un dólar adicional de capital o crédito?")
                        resource_cards_output = gr.Markdown("#### Otros Recursos")
                        chart_cash_debt_output = gr.Plot(label="¿Cómo evolucionan la caja y la deuda?")
                        chart_sales_output = gr.Plot(label="Ventas por mes")

                        gr.Markdown("#### Restricciones y Costo de Oportunidad")
                        constraints_output = gr.Dataframe(label="Análisis de Restricciones")

                        gr.Markdown("#### Cuña Fiscal / Tax Wedge Breakdown")
                        tax_wedge_output = gr.Dataframe(label="Desglose Impositivo / Taxes Breakdown")
                        tax_disclaimer_output = gr.Markdown("")

                def on_apply_polygon(poly_str, lang):
                    if not poly_str or not poly_str.strip():
                        return gr.update(), gr.update(), gr.update(), ""
                    try:
                        data = json.loads(poly_str)
                        res = field_from_map(data)
                        area = round(float(res["area_ha"]), 1)
                        reg = res["region"]
                        lat = round(res["centroid"][1], 4)
                        lon = round(res["centroid"][0], 4)
                        if reg == "iowa":
                            crops_choices = ["corn", "soybean"]
                            crops_val = ["corn", "soybean"]
                            reg_display = "Iowa, USA"
                        elif reg == "southeast_buenos_aires":
                            crops_choices = ["trigo", "maíz", "soja", "girasol"]
                            crops_val = ["trigo", "maíz", "soja", "girasol"]
                            reg_display = "Sudeste de Buenos Aires"
                        else:
                            crops_choices = ["trigo", "maíz", "soja", "girasol"]
                            crops_val = ["trigo", "maíz", "soja", "girasol"]
                            reg_display = reg or "Desconocida"

                        msg = f"✅ **Campo delimitado:** {area} ha en **{reg_display}** ({lat}, {lon})."
                        return gr.update(value=area), gr.update(choices=crops_choices, value=crops_val), gr.update(value=reg), msg
                    except Exception as e:
                        return gr.update(), gr.update(), gr.update(), f"❌ **Error al procesar polígono:** {e}"

                def on_region_change(reg):
                    if reg == "iowa":
                        return gr.update(choices=["corn", "soybean"], value=["corn", "soybean"])
                    else:
                        return gr.update(choices=["trigo", "maíz", "soja", "girasol"], value=["trigo", "maíz", "soja", "girasol"])

                apply_map_btn.click(
                    fn=on_apply_polygon,
                    inputs=[polygon_input, lang_state],
                    outputs=[area_input, crops_input, region_input, map_status],
                )
                polygon_input.change(
                    fn=on_apply_polygon,
                    inputs=[polygon_input, lang_state],
                    outputs=[area_input, crops_input, region_input, map_status],
                )
                region_input.change(
                    fn=on_region_change,
                    inputs=[region_input],
                    outputs=[crops_input],
                )

                def on_run(area, crops, own_cap, cred_line, cred_rate, delay, surcharge, stor, p_source, constr, lang, reg, owned, rent_in, buy, rent_out):
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
                        region=reg,
                        owned_ha=owned,
                        max_rent_in_ha=rent_in,
                        allow_rent_out=rent_out,
                        max_buy_ha=buy,
                    )
                    return (
                        res["plan"],
                        res["land_card"],
                        res["chart_rates"],
                        res["chart_resources"],
                        res["resource_cards"],
                        res["chart_cash_debt"],
                        res["chart_sales"],
                        res["constraints"],
                        res["tax_wedge_table"],
                        res["tax_disclaimer"],
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
                        region_input,
                        owned_input,
                        rent_in_input,
                        buy_input,
                        rent_out_input,
                    ],
                    outputs=[
                        plan_output,
                        land_card_output,
                        chart_rates_output,
                        chart_resources_output,
                        resource_cards_output,
                        chart_cash_debt_output,
                        chart_sales_output,
                        constraints_output,
                        tax_wedge_output,
                        tax_disclaimer_output,
                    ],
                )

                # Example button handlers
                def load_example_rationed():
                    return 500.0, 50000.0, 100000.0, 0, 0.0, [["", "", None, "", None]]

                def load_example_supplier():
                    return 500.0, 50000.0, 100000.0, 6, 3.0, [["", "", None, "", None]]

                def load_example_corn():
                    return 500.0, 50000.0, 100000.0, 0, 0.0, [["min_area", "maíz", 150, "", None]]

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
            # TAB 2: REGIONAL OBSERVATORY
            # ------------------------------------------------------------------
            with gr.TabItem("🌍 Regiones / Regional Observatory", id="tab_regions", elem_id="tab_regions"):
                init_banner, init_map_html, init_table, init_fig = get_observatory_ui_data(force_run=False)

                obs_banner = gr.Markdown(init_banner)
                obs_map = gr.HTML(init_map_html)
                obs_table = gr.Dataframe(value=init_table, label="Comparación Regional / Regional Comparison")
                obs_chart = gr.Plot(value=init_fig, label="Evolución de Tasa Interna de Oportunidad")

                refresh_obs_btn = gr.Button("🔄 Actualizar Observatorio / Refresh", variant="secondary", size="sm")

                def on_refresh_observatory():
                    banner, map_html, table_df, fig = get_observatory_ui_data(force_run=True)
                    return banner, map_html, table_df, fig

                refresh_obs_btn.click(
                    fn=on_refresh_observatory,
                    inputs=[],
                    outputs=[obs_banner, obs_map, obs_table, obs_chart],
                )

            # ------------------------------------------------------------------
            # TAB 3: CHAT (Only included if DORA_API_KEY is present)
            # ------------------------------------------------------------------
            if has_chat:
                with gr.TabItem("💬 Chat con DORA / Chat", id="tab_chat", elem_id="tab_chat"):
                    chatbot = gr.Chatbot(height=500, label="DORA Farm Agent")
                    with gr.Row():
                        chat_files = gr.File(
                            label="Fotos de facturas / remitos / presupuestos (JPG/PNG)",
                            file_count="multiple",
                            file_types=["image"],
                            scale=6,
                        )
                        chat_audio = gr.Audio(
                            label="Nota de voz (grabación o archivo)",
                            sources=["upload", "microphone"],
                            type="filepath",
                            scale=6,
                        )
                    with gr.Row():
                        chat_msg = gr.Textbox(
                            placeholder="Consultá sobre tu plan de siembra o enviá facturas/fotos...",
                            label="Tu mensaje",
                            scale=9,
                        )
                        chat_send = gr.Button("Enviar", variant="primary", scale=2)

                    agent_state = gr.State(None)

                    def respond(user_text: str, files: list | None, audio: str | None, history: list, agent_instance: Any, lang: str):
                        global _daily_chat_counter
                        t = STRINGS.get(lang, STRINGS["es"])

                        clean_text = (user_text or "").strip()
                        if not clean_text and not files and not audio:
                            return "", None, None, history, agent_instance

                        if _daily_chat_counter >= DAILY_CHAT_LIMIT:
                            history.append((user_text, t["chat_limit_reached"]))
                            return "", None, None, history, agent_instance

                        _daily_chat_counter += 1

                        if agent_instance is None:
                            from dora.agent import Agent
                            agent_instance = Agent()

                        image_paths = [f.name if hasattr(f, "name") else str(f) for f in files] if files else []
                        audio_path = audio if audio else None

                        reply = agent_instance.ask(clean_text, images=image_paths, audio=audio_path)

                        # Format user display in chat with thumbnails
                        user_display = clean_text
                        if image_paths:
                            thumbs = " ".join(f"📷 *[{os.path.basename(p)}]({p})*" for p in image_paths)
                            user_display = f"{user_display}\n\n{thumbs}".strip()
                        if audio_path:
                            user_display = f"{user_display}\n\n🎙️ *[Nota de voz]*".strip()

                        # Badge formatting
                        if reply.verified:
                            badge = t["chat_badge_verified"]
                        else:
                            unsupp = ", ".join(u.text for u in reply.unsupported)
                            badge = t["chat_badge_unverified"].format(unsupported=unsupp)

                        # Check for record_document in tool calls to show reconciliation table
                        reconciliation_md = ""
                        for tc in reply.tool_calls:
                            if tc.get("tool") == "record_document":
                                try:
                                    # Find result in tool results
                                    doc_res = None
                                    for r_str in getattr(agent_instance, "tool_results", []):
                                        try:
                                            parsed_r = json.loads(r_str)
                                            if "proposals" in parsed_r and "completeness" in parsed_r:
                                                doc_res = parsed_r
                                                break
                                        except Exception:
                                            continue
                                    if doc_res:
                                        rec_lines = ["\n\n### 📑 Conciliación de Documento del Productor:"]
                                        if doc_res.get("missing"):
                                            rec_lines.append(f"> ⚠️ **Faltante para conciliar:** {', '.join(doc_res['missing'])}")
                                        if doc_res.get("proposals"):
                                            rec_lines.append("| Cultivo | Concepto | Costo Propuesto | Ref. Regional | Desviación |")
                                            rec_lines.append("|---|---|---|---|---|")
                                            for prop in doc_res["proposals"]:
                                                flag_str = " ⚠️ (>50%)" if prop.get("deviation_flag") else " ✅"
                                                rec_lines.append(f"| {prop['crop']} | {prop['item']} | USD {prop['proposed_usd_ha']}/ha | USD {prop.get('default_usd_ha', '-')}/ha | {prop.get('deviation_pct', 0)}%{flag_str} |")
                                        if doc_res.get("fx_conversion"):
                                            fx = doc_res["fx_conversion"]
                                            rec_lines.append(f"\n*Conversión ARS/USD BCRA:* {fx.get('rate')} ({fx.get('date')})")
                                        reconciliation_md = "\n".join(rec_lines)
                                except Exception:
                                    pass

                        # Tool calls detail
                        tool_calls_text = ""
                        if reply.tool_calls:
                            summary_text = t["tool_calls_summary"].format(n=len(reply.tool_calls))
                            call_items = []
                            for c in reply.tool_calls:
                                call_items.append(f"- **{c.get('tool')}**: `{c.get('arguments')}`")
                            tool_calls_text = f"\n\n<details><summary>{summary_text}</summary>\n\n" + "\n".join(call_items) + "\n</details>"

                        bot_message = f"{badge}\n\n{reply.text}{reconciliation_md}{tool_calls_text}"
                        history.append((user_display, bot_message))
                        return "", None, None, history, agent_instance

                    chat_send.click(
                        fn=respond,
                        inputs=[chat_msg, chat_files, chat_audio, chatbot, agent_state, lang_state],
                        outputs=[chat_msg, chat_files, chat_audio, chatbot, agent_state],
                    )
                    chat_msg.submit(
                        fn=respond,
                        inputs=[chat_msg, chat_files, chat_audio, chatbot, agent_state, lang_state],
                        outputs=[chat_msg, chat_files, chat_audio, chatbot, agent_state],
                    )

            # Language switch
            def on_lang_change(selected_lang: str):
                is_es = selected_lang == "Español"
                crops_val = ["trigo", "maíz", "soja", "girasol"] if is_es else ["wheat", "corn", "soybean", "sunflower"]
                crops_choices = crops_val
                return "es" if is_es else "en", gr.update(choices=crops_choices, value=crops_val)

            lang_radio.change(
                fn=on_lang_change,
                inputs=[lang_radio],
                outputs=[lang_state, crops_input],
            )

        app.has_chat = has_chat
    return app


if __name__ == "__main__":
    demo = build_app()
    demo.launch(head=getattr(demo, "head", None), theme=getattr(demo, "theme", None))
