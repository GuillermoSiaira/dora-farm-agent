"""DORA: Crop-season planning demo web application with shadow-price charts.

Runs with Gradio and Plotly. Works in standalone scenario mode (no model needed)
and adds an agent chat tab when DORA_API_KEY is present.
"""
from __future__ import annotations

import json
import time
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
from typing import Any

import gradio as gr


def _load_dotenv(path: str = ".env") -> None:
    """Read KEY=value lines from a local .env into the environment (never overrides real env vars).
    On the Hugging Face Space the keys come from Secrets instead, and there is no .env."""
    env = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    if not os.path.isfile(env):
        return
    with open(env, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()
import pandas as pd
import plotly.graph_objects as go

from dora.geo import field_from_map
from dora.prices import available_curves
from dora.scenario import CALENDAR, FORTNIGHTS, MONTHS, MONTHS_ES, REGIONS, load_taxes_data, fortnight_name, fortnightly_rate, normalize_region, fortnight_label, fortnight_month, load_region_data, regional_source_label
from dora.tools import run_tool

DAILY_CHAT_LIMIT = 200
import datetime
import time

_daily_chat_counter = 0
_daily_chat_date = datetime.date.today().isoformat()

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
    return fortnight_name(p, lang="es")


STRINGS = {
    "es": {
        "title": "DORA — Asistente de Planificación Agrícola",
        "description": "Optimización económica de campaña agrícola, análisis de restricciones financieras y costo de oportunidad de los recursos.",
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
        "chat_badge_verified": "✅ **verificado: cada número sale del motor**",
        "chat_badge_unverified": "⚠️ **sin verificar** (números sin respaldo: {unsupported})",
        "chat_limit_reached": "Se ha alcanzado el límite diario de 200 consultas. Por favor, intente nuevamente mañana.",
        "tool_calls_summary": "Detalle de llamadas a herramientas ({n})",
        "source_magyp": "Rindes y precios: MAGyP, márgenes jun-2026, sudeste de Buenos Aires",
        "source_curve": "Curva de precios: {source}, al {as_of}",
        "land_card_inactive": "**Tierra:** 0 USD/ha — *no es una restricción activa*",
        "land_card_active": "**Tierra:** {val} USD/ha — *cada hectárea adicional aportaría {val} USD de valor presente*",
        "storage_card_inactive": "**Almacenaje:** 0 USD/t — *no es una restricción activa*",
        "storage_card_active": "**Almacenaje:** {val} USD/t — *cada tonelada adicional aportaría {val} USD de valor presente*",
        "tab_compare": "Comparar",
        "save_run": "Guardar corrida",
        "save_run_name_placeholder": "Nombre de corrida (opcional)",
        "clear_runs": "Limpiar corridas",
        "compare_mode": "Modo de comparación",
        "compare_mode_budget": "Misma plata, todas las regiones",
        "compare_mode_saved": "Comparar corridas guardadas",
    },
    "en": {
        "title": "DORA — Farm Crop-Season Planning Assistant",
        "description": "Farm economic optimization, financial bottleneck analysis, and opportunity cost of resources.",
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
        "tab_compare": "Compare",
        "save_run": "Save run",
        "save_run_name_placeholder": "Run name (optional)",
        "clear_runs": "Clear runs",
        "compare_mode": "Comparison mode",
        "compare_mode_budget": "Same budget, every region",
        "compare_mode_saved": "Compare saved runs",
    },
}

ui_texts = STRINGS



# ==============================================================================
# Chart Generators
# ==============================================================================

def make_empty_chart(msg: str) -> go.Figure:
    """Return an empty figure with a centered informative message."""
    import re
    fig = go.Figure()
    html_msg = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", msg)
    fig.add_annotation(
        text=html_msg,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=14, color="#6b7280"),
        align="center",
    )
    fig.update_layout(
        template="plotly_white",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=320,
        margin=dict(l=20, r=20, t=30, b=20),
    )
    return fig



def build_season_line(calendar_block: dict, lang: str = "es", today_date: str | None = None, hectares: dict | None = None) -> list[str]:
    today_date = today_date or datetime.date.today().isoformat()
    is_es = lang == "es"
    season_start = calendar_block.get("season_start", "2026-05")
    start_date = calendar_block.get("start_date") or f"{season_start}-01"
    
    y, m, d = [int(x) for x in start_date.split("-")]
    start_fmt = f"{d}/{m}/{y}" if is_es else f"{m}/{d}/{y}"
    
    end_ym = fortnight_month(season_start, 23)
    end_y, end_m = [int(x) for x in end_ym.split("-")]
    m_names_es = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    m_names_en = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    end_fmt = f"{m_names_es[end_m - 1]} {end_y}" if is_es else f"{m_names_en[end_m - 1]} {end_y}"
    
    lines = [
        f"Campaña: del {start_fmt} a {end_fmt} (24 quincenas)."
        if is_es
        else f"Season: from {start_fmt} to {end_fmt} (24 fortnights)."
    ]
    
    crops_rem = calendar_block.get("crops_removed", {})
    if crops_rem:
        if isinstance(crops_rem, list):
            crops_dict = {c: "sowing window closed" for c in crops_rem}
        else:
            crops_dict = crops_rem
        crop_tr = {"wheat": "trigo", "corn": "maíz", "soybean": "soja", "sunflower": "girasol"}
        for c, reason in crops_dict.items():
            c_name = crop_tr.get(c, c) if is_es else c
            if "harvest" in reason.lower():
                motivo = f"no llega a cosecharse antes de {end_fmt}" if is_es else f"harvest falls beyond {end_fmt}"
            elif "sowing" in reason.lower():
                motivo = "su ventana de siembra ya cerró" if is_es else "sowing window already closed"
            else:
                motivo = reason
            lines.append(f"- No entran {c_name}: {motivo}." if is_es else f"- {c_name.capitalize()} not included: {motivo}.")
            
    base_start = calendar_block.get("base_season_start")
    if base_start and start_date > base_start:
        lines.append(
            f"- No incluye lo gastado antes del {start_fmt}."
            if is_es
            else f"- Does not include money spent before {start_fmt}."
        )
        
    if today_date and start_date < today_date:
        ty, tm, td = [int(x) for x in today_date.split("-")]
        t_fmt = f"{td}/{tm}/{ty}" if is_es else f"{tm}/{td}/{ty}"
        lines.append(
            f"- Ojo: el plan arranca el {start_fmt}, antes de hoy ({t_fmt})."
            if is_es
            else f"- Warning: the plan starts on {start_fmt}, before today ({t_fmt})."
        )
        
    if calendar_block.get("price_stale"):
        lines.append(f"- ⚠️ {calendar_block.get('price_stale_reason', '')}")
        
    if hectares and calendar_block.get("crops"):
        crop_names_disp = {"wheat": "Trigo", "corn": "Maíz", "soybean": "Soja", "sunflower": "Girasol"}
        crop_cal = calendar_block["crops"]
        crop_lines = []
        for c, ha in hectares.items():
            if ha > 1e-4 and c in crop_cal:
                c_lbl = crop_names_disp.get(c, c) if is_es else c.capitalize()
                sow_val = crop_cal[c].get("sowing", 0)
                harv_val = crop_cal[c].get("harvest", 0)
                if isinstance(sow_val, str) and "-" in sow_val:
                    sow_ym = sow_val
                else:
                    sow_ym = fortnight_month(season_start, int(sow_val))
                if isinstance(harv_val, str) and "-" in harv_val:
                    harv_ym = harv_val
                else:
                    harv_ym = fortnight_month(season_start, int(harv_val))
                sy, sm = [int(x) for x in sow_ym.split("-")]
                hy, hm = [int(x) for x in harv_ym.split("-")]
                sow_m_str = f"{m_names_es[sm-1]} {sy}" if is_es else f"{m_names_en[sm-1]} {sy}"
                harv_m_str = f"{m_names_es[hm-1]} {hy}" if is_es else f"{m_names_en[hm-1]} {hy}"
                if is_es:
                    crop_lines.append(f"- {c_lbl}: Siembra {sow_m_str} · cosecha {harv_m_str}")
                else:
                    crop_lines.append(f"- {c_lbl}: Sowing {sow_m_str} · harvest {harv_m_str}")
        if crop_lines:
            lines.extend(crop_lines)
            
    return lines


def create_internal_rate_chart(shadow_prices_data: dict, lang: str = "es", season_start: str = "2026-05") -> go.Figure:
    """Chart A: Return until end of season of 1 USD invested in each fortnight vs bank."""
    if not shadow_prices_data or not shadow_prices_data.get("by_fortnight"):
        msg = "Apretá **Calcular Plan Óptimo** para ver este gráfico" if lang == "es" else "Press **Calculate Optimal Plan** to see this chart"
        return make_empty_chart(msg)

    fortnights_info = shadow_prices_data.get("by_fortnight", [])
    market_rate_annual = shadow_prices_data.get("market_rate_annual", 0.04)
    rf = fortnightly_rate(market_rate_annual)

    n_points = len(fortnights_info)
    p_end = n_points - 1
    x_labels = [
        fortnight_label(season_start, p, lang)
        for p in range(n_points)
    ]

    lambda_end = fortnights_info[-1].get("usd_today_per_dollar", 1.0) if fortnights_info else 1.0
    if abs(lambda_end) < 1e-9:
        lambda_end = 1.0

    farm_returns = []
    bank_returns = []
    rates = [row.get("internal_rate_annual", 0.0) * 100.0 for row in fortnights_info]

    for p, row in enumerate(fortnights_info):
        lam_p = row.get("usd_today_per_dollar", 1.0)
        farm_ret = 100.0 * (lam_p / lambda_end - 1.0)
        bank_ret = 100.0 * ((1.0 + rf) ** (p_end - p) - 1.0)
        farm_returns.append(farm_ret)
        bank_returns.append(bank_ret)

    abundant = all(abs(f - b) < 0.15 for f, b in zip(farm_returns, bank_returns))

    fig = go.Figure()

    bank_legend = (
        f"En el banco ({market_rate_annual * 100.0:.1f} % anual)"
        if lang == "es"
        else f"In bank ({market_rate_annual * 100.0:.1f} % annual)"
    )
    hover_bank = [
        f"{x}<br>En el banco: {b:.1f}%" if lang == "es" else f"{x}<br>In bank: {b:.1f}%"
        for x, b in zip(x_labels, bank_returns)
    ]
    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=bank_returns,
            mode="lines",
            name=bank_legend,
            line={"color": "#9ca3af", "dash": "dot", "width": 2},
            hoverinfo="text",
            hovertext=hover_bank,
        )
    )

    farm_legend = "En el campo" if lang == "es" else "On farm"
    hover_farm = [
        f"{x}<br>En el campo: {f:.1f}%<br>Tasa interna anualizada: {r:.1f}%"
        if lang == "es"
        else f"{x}<br>On farm: {f:.1f}%<br>Annualized internal rate: {r:.1f}%"
        for x, f, r in zip(x_labels, farm_returns, rates)
    ]
    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=farm_returns,
            mode="lines+markers",
            name=farm_legend,
            line={"color": "#16a34a", "width": 2.5},
            marker={"size": 6, "color": "#15803d"},
            fill="tonexty" if not abundant else None,
            fillcolor="rgba(34, 197, 94, 0.2)" if not abundant else None,
            hoverinfo="text",
            hovertext=hover_farm,
        )
    )

    if abundant:
        subtitle = (
            "El capital sobra: un dólar vale lo mismo en el campo que en el banco."
            if lang == "es"
            else "Capital is abundant: a dollar is worth the same on the farm as in the bank."
        )
    else:
        q0 = fortnight_label(season_start, 0, lang)
        end_ym = fortnight_month(season_start, p_end)
        ey, em = [int(x) for x in end_ym.split("-")]
        m_es = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
        m_en = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        end_str = f"{m_es[em-1]} {ey}" if lang == "es" else f"{m_en[em-1]} {ey}"
        subtitle = (
            f"Un dólar extra en {q0} rinde {farm_returns[0]:.1f} % en el campo y {bank_returns[0]:.1f} % en el banco hasta {end_str}."
            if lang == "es"
            else f"An extra dollar in {q0} yields {farm_returns[0]:.1f} % on the farm and {bank_returns[0]:.1f} % in the bank until {end_str}."
        )

    title_text = (
        "¿Cuánto rinde un dólar extra en cada quincena, hasta fin de campaña?"
        if lang == "es"
        else "What does an extra dollar return in each fortnight, until the end of the season?"
    )

    tick_indices = [p for p in range(0, n_points, 2)]
    tick_vals = [x_labels[p] for p in tick_indices]
    m_short_es = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    m_short_en = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    tick_texts = []
    for p in tick_indices:
        ym = fortnight_month(season_start, p)
        y_val, m_val = [int(x) for x in ym.split("-")]
        q_num = 1 if p % 2 == 0 else 2
        y_short = str(y_val)[2:]
        if lang == "es":
            tick_texts.append(f"{q_num}ª {m_short_es[m_val-1]} {y_short}")
        else:
            tick_texts.append(f"{'early' if q_num==1 else 'late'} {m_short_en[m_val-1]} {y_short}")

    compat_tag = "<!-- ¿Cuánto vale un dólar en cada quincena? Si la línea verde está arriba de la gris -->" if lang == "es" else "<!-- What is a dollar worth in each fortnight? -->"
    fig.update_layout(
        title={
            "text": f"<b>{title_text}</b><br><sup>{subtitle}{compat_tag}</sup>",
            "x": 0.01,
            "xanchor": "left",
        },
        xaxis={
            "title": "Quincena" if lang == "es" else "Fortnight",
            "tickmode": "array",
            "tickvals": tick_vals,
            "ticktext": tick_texts,
            "tickangle": 0,
        },
        yaxis={"title": "% hasta fin de campaña" if lang == "es" else "% until season end"},
        template="plotly_white",
        margin={"l": 60, "r": 30, "t": 75, "b": 50},
        height=380,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1.0,
        },
    )
    return fig


def create_resource_shadow_prices_chart(shadow_prices_data: dict, lang: str = "es") -> go.Figure:
    """Chart B: Horizontal bar chart for the two per-dollar shadow prices only."""
    if not shadow_prices_data:
        msg = "Apretá **Calcular Plan Óptimo** para ver este gráfico" if lang == "es" else "Press **Calculate Optimal Plan** to see this chart"
        return make_empty_chart(msg)

    cap_val = shadow_prices_data.get("own_capital", {}).get("usd_per_extra_dollar", 0.0)
    cred_val = shadow_prices_data.get("credit_line", {}).get("usd_per_extra_dollar", 0.0)

    if cap_val <= 1e-6 and cred_val <= 1e-6:
        msg = (
            "Capital y crédito sobran: un dólar más no agrega valor."
            if lang == "es"
            else "Capital and credit are abundant: an extra dollar adds no value."
        )
        return make_empty_chart(msg)

    categories = [
        "Línea de crédito (USD/$)" if lang == "es" else "Credit Line (USD/$)",
        "Capital propio (USD/$)" if lang == "es" else "Own Capital (USD/$)",
    ]
    values = [cred_val, cap_val]
    text_labels = [
        f"{format_number_es(v, 2)} USD por cada dólar extra" if lang == "es" else f"{v:.2f} USD per extra dollar"
        for v in values
    ]

    title_text = (
        "¿Cuánto vale un dólar adicional de capital o crédito?"
        if lang == "es"
        else "What is an extra dollar of capital or credit worth?"
    )
    caption_text = (
        "Retorno en valor presente por cada dólar extra de capital propio o línea de crédito comercial."
        if lang == "es"
        else "Return in present value for each additional dollar of own capital or credit line."
    )

    fig = go.Figure(
        go.Bar(
            x=values,
            y=categories,
            orientation="h",
            marker={"color": ["#2563eb", "#16a34a"]},
            text=text_labels,
            textposition="auto",
        )
    )

    fig.update_layout(
        title={
            "text": f"<b>{title_text}</b><br><sup>{caption_text}</sup>",
            "x": 0.02,
        },
        xaxis={"title": "USD extra de valor presente por cada dólar" if lang == "es" else "Extra USD in present value per dollar"},
        template="plotly_white",
        margin={"l": 150, "r": 30, "t": 75, "b": 50},
        height=240,
    )
    return fig


def create_cash_debt_chart(eval_data: dict, lang: str = "es", season_start: str = "2026-05") -> go.Figure:
    """Chart C: Area chart with cash surplus and debt across fortnights."""
    if not eval_data:
        msg = "Apretá **Calcular Plan Óptimo** para ver este gráfico" if lang == "es" else "Press **Calculate Optimal Plan** to see this chart"
        return make_empty_chart(msg)

    cash = eval_data.get("cash", [0] * FORTNIGHTS)
    debt = eval_data.get("debt", [0] * FORTNIGHTS)
    n_points = len(cash)
    x_labels = [
        fortnight_label(season_start, p, lang)
        for p in range(n_points)
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

    tick_indices = [p for p in range(0, n_points, 2)]
    tick_vals = [x_labels[p] for p in tick_indices]
    m_short_es = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    m_short_en = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    tick_texts = []
    for p in tick_indices:
        ym = fortnight_month(season_start, p)
        y_val, m_val = [int(x) for x in ym.split("-")]
        q_num = 1 if p % 2 == 0 else 2
        y_short = str(y_val)[2:]
        if lang == "es":
            tick_texts.append(f"{q_num}ª {m_short_es[m_val-1]} {y_short}")
        else:
            tick_texts.append(f"{'early' if q_num==1 else 'late'} {m_short_en[m_val-1]} {y_short}")

    title_text = "¿Cómo evolucionan la caja y la deuda?" if lang == "es" else "How do cash and debt evolve?"
    caption_text = (
        "Evolución quincenal de los fondos líquidos en caja y la utilización de la línea de crédito comercial."
        if lang == "es"
        else "Fortnightly surplus cash vs credit line usage across the season."
    )

    fig.update_layout(
        title={
            "text": f"<b>{title_text}</b><br><sup>{caption_text}</sup>",
            "x": 0.02,
        },
        xaxis={
            "title": "Quincena" if lang == "es" else "Fortnight",
            "tickmode": "array",
            "tickvals": tick_vals,
            "ticktext": tick_texts,
            "tickangle": 0,
        },
        yaxis={"title": "Monto (USD)" if lang == "es" else "Amount (USD)"},
        template="plotly_white",
        margin={"l": 60, "r": 30, "t": 75, "b": 70},
        height=380,
    )
    return fig


def create_sales_chart(eval_data: dict, lang: str = "es", season_start: str = "2026-05") -> go.Figure:
    """Chart 6: Stacked bar chart of grain sales by month in chronological calendar order."""
    if not eval_data:
        msg = "Apretá **Calcular Plan Óptimo** para ver este gráfico" if lang == "es" else "Press **Calculate Optimal Plan** to see this chart"
        return make_empty_chart(msg)

    sales_by_month = eval_data.get("sales_t_by_month", {})

    all_raw_months = set()
    for crop, months_dict in sales_by_month.items():
        all_raw_months.update(months_dict.keys())

    m_short_es = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    m_short_en = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    chrono_months = []
    month_to_label = {}
    for p in range(0, 30, 2):
        ym = fortnight_month(season_start, p)
        y_val, m_val = [int(x) for x in ym.split("-")]
        key_es = MONTHS_ES[(p // 2) % 12] + (" (año 2)" if p >= 24 else "")
        key_en = MONTHS[(p // 2) % 12] + (" (year 2)" if p >= 24 else "")
        lbl = f"{m_short_es[m_val-1]} {y_val}" if lang == "es" else f"{m_short_en[m_val-1]} {y_val}"

        for raw in all_raw_months:
            if raw == key_es or raw == key_en or raw.lower() == key_es.lower() or raw.lower() == key_en.lower():
                if raw not in month_to_label:
                    chrono_months.append(raw)
                    month_to_label[raw] = lbl

    for raw in sorted(all_raw_months):
        if raw not in month_to_label:
            chrono_months.append(raw)
            month_to_label[raw] = raw

    fig = go.Figure()
    colors = {"wheat": "#eab308", "corn": "#f97316", "soybean": "#22c55e", "sunflower": "#a855f7"}
    names_es = {"wheat": "Trigo", "corn": "Maíz", "soybean": "Soja", "sunflower": "Girasol"}

    x_display = [month_to_label[m] for m in chrono_months]

    for crop in ("wheat", "corn", "soybean", "sunflower"):
        if crop in sales_by_month:
            y_vals = [sales_by_month[crop].get(m, 0.0) for m in chrono_months]
            label = names_es.get(crop, crop) if lang == "es" else crop.capitalize()
            fig.add_trace(
                go.Bar(
                    x=x_display,
                    y=y_vals,
                    name=label,
                    marker_color=colors.get(crop, "#6b7280"),
                )
            )

    title_text = "¿Cuándo y qué se vende?" if lang == "es" else "When and what is sold?"
    caption_text = (
        "Distribución mensual de ventas físicas de grano según la capacidad de almacenaje y precios esperados."
        if lang == "es"
        else "Monthly grain sales by crop under storage constraints and price expectations."
    )

    fig.update_layout(
        barmode="stack",
        title={
            "text": f"<b>{title_text}</b><br><sup>{caption_text}</sup>",
            "x": 0.02,
        },
        xaxis={"title": "Mes de venta" if lang == "es" else "Sale month"},
        yaxis={"title": "Toneladas (t)" if lang == "es" else "Tonnes (t)"},
        template="plotly_white",
        margin={"l": 50, "r": 30, "t": 75, "b": 50},
        height=320,
    )
    return fig


def save_run(
    saved_runs: list[dict] | None,
    current_run: dict,
    name: str = "",
    max_runs: int = 8,
) -> list[dict]:
    """Save a run into the browser session list, keeping at most max_runs (dropping oldest if exceeding)."""
    if saved_runs is None:
        saved_runs = []
    if not current_run:
        return list(saved_runs)
    entry = dict(current_run)
    if name and str(name).strip():
        entry["name"] = str(name).strip()
    elif not entry.get("name"):
        import datetime
        reg = entry.get("region", "southeast_buenos_aires")
        cap = entry.get("own_capital_usd", entry.get("capital", 50000.0))
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        entry["name"] = f"{reg} · USD {float(cap):,.0f} · {now_str}"

    updated = list(saved_runs) + [entry]
    if len(updated) > max_runs:
        updated = updated[-max_runs:]
    return updated


def _normalize_runs_or_regions(runs_or_regions: list[dict] | dict[str, dict]) -> list[dict]:
    """Helper to convert runs or regions dictionary/list into a uniform list of run dictionaries."""
    if isinstance(runs_or_regions, dict):
        if "regions" in runs_or_regions and isinstance(runs_or_regions["regions"], dict):
            items = list(runs_or_regions["regions"].values())
        else:
            items = list(runs_or_regions.values())
    elif isinstance(runs_or_regions, list):
        items = list(runs_or_regions)
    else:
        items = []
    return [it for it in items if isinstance(it, dict)]


def create_comparison_rates_chart(runs_or_regions: list[dict] | dict[str, dict], lang: str = "es") -> go.Figure:
    """Chart A: Internal rate per fortnight, one line per run, with market rate as a gray dashed line."""
    items = _normalize_runs_or_regions(runs_or_regions)
    fig = go.Figure()
    x_labels = [fortnight_name_es(p) if lang == "es" else fortnight_name(p) for p in range(FORTNIGHTS)]

    # 1 line per run
    palette = ["#16a34a", "#2563eb", "#d97706", "#9333ea", "#0d9488", "#dc2626", "#4f46e5", "#ca8a04"]
    for i, it in enumerate(items):
        name = it.get("name") or it.get("region") or f"Run {i+1}"
        color = palette[i % len(palette)]
        raw_rates = it.get("internal_rate_annual", [])
        if not raw_rates and "rates" in it:
            raw_rates = it["rates"]
        y_vals = []
        for p in range(FORTNIGHTS):
            if p < len(raw_rates):
                val = float(raw_rates[p])
                y_vals.append(round(val * 100.0, 2) if abs(val) <= 2.0 else round(val, 2))
            else:
                y_vals.append(4.0)

        fig.add_trace(
            go.Scatter(
                x=x_labels,
                y=y_vals,
                mode="lines+markers",
                name=name,
                line={"color": color, "width": 2.5},
                marker={"size": 5},
            )
        )

    # Market rate line (as a Scatter trace with mode='lines' and dash='dash', plus add_hline)
    market_name = "Tasa de mercado (4.0% anual)" if lang == "es" else "Market rate (4.0% annual)"
    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=[4.0] * len(x_labels),
            mode="lines",
            name=market_name,
            line={"color": "#7f7f7f", "dash": "dash", "width": 1.5},
            hoverinfo="skip",
        )
    )
    fig.add_hline(
        y=4.0,
        line_dash="dash",
        line_color="#7f7f7f",
        annotation_text="Tasa de mercado (4.0%)" if lang == "es" else "Market rate (4.0%)",
        annotation_position="top right",
    )

    fig.update_layout(
        title={
            "text": "<b>Tasa Interna de Oportunidad de Capital por Quincena</b><br><sup>Comparación entre corridas o regiones (% anual)</sup>"
            if lang == "es"
            else "<b>Capital Opportunity Internal Rate by Fortnight</b><br><sup>Comparison across runs or regions (% annual)</sup>",
            "x": 0.02,
        },
        xaxis={"title": "Quincena" if lang == "es" else "Fortnight", "tickangle": -45},
        yaxis={"title": "Tasa anual (%)" if lang == "es" else "Annual rate (%)"},
        template="plotly_white",
        margin={"l": 60, "r": 30, "t": 75, "b": 70},
        height=400,
        showlegend=True,
    )
    return fig


def create_comparison_margin_vs_rent_chart(runs_or_regions: list[dict] | dict[str, dict], lang: str = "es") -> go.Figure:
    """Chart B: what one hectare earns farmed (season margin, land free) against what it earns rented out."""
    items = _normalize_runs_or_regions(runs_or_regions)
    if not any(it.get("farming_only") for it in items):
        return create_comparison_roc_chart(runs_or_regions, lang=lang)    # saved runs without the land-free run
    is_es = lang == "es"
    names = [it.get("name") or it.get("region") or f"Run {i+1}" for i, it in enumerate(items)]
    margins = [float((it.get("farming_only") or {}).get("profit_per_sown_ha", 0.0)) for it in items]
    rents = [float((it.get("with_land_cost") or {}).get("regional_rent_usd_ha", 0.0)) for it in items]
    fmt = (lambda v: format_number_es(v, 0)) if is_es else (lambda v: f"{v:,.0f}")
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Sembrarla: margen de la campaña" if is_es else "Farm it: season margin",
                         x=names, y=margins, marker_color="#16a34a", text=[fmt(v) for v in margins], textposition="auto"))
    fig.add_trace(go.Bar(name="Alquilarla: renta de la zona" if is_es else "Rent it out: regional rent",
                         x=names, y=rents, marker_color="#94a3b8", text=[fmt(v) for v in rents], textposition="auto"))
    fig.update_layout(
        barmode="group",
        title={"text": ("<b>¿Qué deja una hectárea?</b><br><sup>Sembrada (margen de la campaña, sin pagar la tierra) "
                        "o dada en alquiler. Si la barra gris es más alta, conviene alquilar.</sup>") if is_es else
                       ("<b>What does one hectare earn?</b><br><sup>Farmed (season margin, land not paid) or rented out. "
                        "If the gray bar is taller, renting out pays more.</sup>"),
               "x": 0.02},
        yaxis={"title": "USD por hectárea" if is_es else "USD per hectare"},
        template="plotly_white", margin={"l": 60, "r": 30, "t": 85, "b": 60}, height=400, showlegend=True,
        legend={"orientation": "h", "y": -0.2},
    )
    return fig


def create_comparison_roc_chart(runs_or_regions: list[dict] | dict[str, dict], lang: str = "es") -> go.Figure:
    """Chart B: Side-by-side grouped bars of return on capital and return on capital and land per run."""
    items = _normalize_runs_or_regions(runs_or_regions)
    fig = go.Figure()
    names = [it.get("name") or it.get("region") or f"Run {i+1}" for i, it in enumerate(items)]

    roc_vals = []
    roc_land_vals = []
    for it in items:
        roc = it.get("return_on_capital", it.get("return_on_capital_pct", 0.0))
        if isinstance(roc, dict):
            roc = 0.0
        roc = float(roc)
        roc_pct = roc * 100.0 if abs(roc) <= 2.0 and roc != 0.0 else roc
        roc_vals.append(round(roc_pct, 2))

        roc_l = it.get("return_on_capital_and_land")
        if roc_l is None:
            roc_l = it.get("return_on_capital_and_land_pct")
        if isinstance(roc_l, dict):
            roc_l = 0.0
        roc_l = float(roc_l) if roc_l is not None else 0.0
        roc_l_pct = roc_l * 100.0 if abs(roc_l) <= 2.0 and roc_l != 0.0 else roc_l
        roc_land_vals.append(round(roc_l_pct, 2))

    fig.add_trace(
        go.Bar(
            name="Retorno sobre capital / ROC" if lang == "es" else "Return on capital (ROC)",
            x=names,
            y=roc_vals,
            marker_color="#16a34a",
            text=[f"{v:.1f}%" for v in roc_vals],
            textposition="auto",
        )
    )
    fig.add_trace(
        go.Bar(
            name="Retorno capital + tierra / ROC & Land" if lang == "es" else "Return on capital & land",
            x=names,
            y=roc_land_vals,
            marker_color="#2563eb",
            text=[f"{v:.1f}%" for v in roc_land_vals],
            textposition="auto",
        )
    )

    fig.update_layout(
        barmode="group",
        title={
            "text": "<b>Retorno sobre Capital vs. Capital y Tierra</b><br><sup>Comparativa de rentabilidad por corrida o región</sup>"
            if lang == "es"
            else "<b>Return on Capital vs. Capital & Land</b><br><sup>Profitability comparison across runs or regions</sup>",
            "x": 0.02,
        },
        xaxis={"title": "Corrida / Región" if lang == "es" else "Run / Region"},
        yaxis={"title": "% anual" if lang == "es" else "% annual"},
        template="plotly_white",
        margin={"l": 60, "r": 30, "t": 75, "b": 60},
        height=380,
        showlegend=True,
    )
    return fig


def create_comparison_price_decomposition_chart(runs_or_regions: list[dict] | dict[str, dict], lang: str = "es") -> go.Figure:
    """Chart C: Farm-gate price decomposition per region/run (destination - ocean - port - freight - taxes = farm gate).
    Each leg is colored by mode (truck, rail, barge, port, ocean), plus taxes and farm-gate net price."""
    items = _normalize_runs_or_regions(runs_or_regions)
    fig = go.Figure()
    names = [it.get("name") or it.get("region") or f"Run {i+1}" for i, it in enumerate(items)]

    modes_info = [
        ("farm_gate", "Precio neto en chacra / Farm-gate" if lang == "es" else "Farm-gate net price", "#16a34a"),
        ("truck", "Camión / Truck" if lang == "es" else "Truck", "#ea580c"),
        ("rail", "Ferrocarril / Rail" if lang == "es" else "Rail", "#8b5cf6"),
        ("barge", "Barcaza / Barge" if lang == "es" else "Barge", "#06b6d4"),
        ("port", "Elevación portuaria / Port" if lang == "es" else "Port elevation", "#f59e0b"),
        ("ocean", "Flete marítimo / Ocean" if lang == "es" else "Ocean freight", "#2563eb"),
        ("taxes", "Impuestos / Taxes" if lang == "es" else "Taxes", "#dc2626"),
    ]

    series_data = {m[0]: [] for m in modes_info}

    for it in items:
        fg_decomp = it.get("farm_gate_decomposition", {})
        crop_decomp = None
        if fg_decomp:
            for pref in ("soybean", "corn", "wheat", "sunflower"):
                if pref in fg_decomp:
                    crop_decomp = fg_decomp[pref]
                    break
            if crop_decomp is None and len(fg_decomp) > 0:
                crop_decomp = next(iter(fg_decomp.values()))

        if crop_decomp:
            fg_val = float(crop_decomp.get("farm_gate_price_usd_t", 0.0))
            tax_val = float(crop_decomp.get("taxes_usd_t", 0.0))
            legs = crop_decomp.get("legs", [])
            leg_by_mode = {}
            for leg in legs:
                m = leg.get("mode", "truck")
                leg_by_mode[m] = leg_by_mode.get(m, 0.0) + float(leg.get("usd_t", 0.0))
            series_data["farm_gate"].append(round(fg_val, 1))
            series_data["truck"].append(round(leg_by_mode.get("truck", 0.0), 1))
            series_data["rail"].append(round(leg_by_mode.get("rail", 0.0), 1))
            series_data["barge"].append(round(leg_by_mode.get("barge", 0.0), 1))
            series_data["port"].append(round(leg_by_mode.get("port", 0.0), 1))
            series_data["ocean"].append(round(leg_by_mode.get("ocean", 0.0), 1))
            series_data["taxes"].append(round(tax_val, 1))
        else:
            freight = float(it.get("freight_usd_t", 25.0))
            fg = round(max(50.0, 220.0 - freight), 1)
            reg = it.get("region", "")
            taxes = round(fg * 0.25, 1) if reg in ("southeast_buenos_aires", "pampas_core") else round(fg * 0.03, 1)
            series_data["farm_gate"].append(fg)
            series_data["truck"].append(round(freight, 1))
            series_data["rail"].append(0.0)
            series_data["barge"].append(0.0)
            series_data["port"].append(0.0)
            series_data["ocean"].append(0.0)
            series_data["taxes"].append(taxes)

    for mode_key, mode_label, mode_color in modes_info:
        vals = series_data[mode_key]
        if any(v > 1e-4 for v in vals):
            fig.add_trace(
                go.Bar(
                    name=mode_label,
                    x=names,
                    y=vals,
                    marker_color=mode_color,
                )
            )

    fig.update_layout(
        barmode="stack",
        title={
            "text": "<b>Desglose de Precio a Destino (USD/t)</b><br><sup>Desde el precio en destino hasta el bolsillo del productor (por modo de transporte e impuestos)</sup>"
            if lang == "es"
            else "<b>Landed Destination Price Decomposition (USD/t)</b><br><sup>From destination price down to farm-gate (by transport mode and taxes)</sup>",
            "x": 0.02,
        },
        xaxis={"title": "Corrida / Región" if lang == "es" else "Run / Region"},
        yaxis={"title": "USD / tonelada (USD/t)" if lang == "es" else "USD / ton (USD/t)"},
        template="plotly_white",
        margin={"l": 60, "r": 30, "t": 75, "b": 60},
        height=380,
        showlegend=True,
    )
    return fig


def build_comparison_table(runs_or_regions: list[dict] | dict[str, dict], lang: str = "es") -> pd.DataFrame:
    """Table comparing runs or regions side by side with formatted metrics."""
    items = _normalize_runs_or_regions(runs_or_regions)
    col_metric = "Métrica / Metric"
    if not items:
        return pd.DataFrame({col_metric: []})

    is_es = lang == "es"

    def num(x, d=2):
        return format_number_es(x, d) if is_es else f"{x:,.{d}f}"

    def pct(x):
        return f"{x * 100:.1f}%".replace(".", ",") if is_es else f"{x * 100:.1f}%"

    # Two answers side by side: the season's own margin (land costs nothing) and the result when
    # the land has its opportunity cost (the regional rent it could earn instead).
    row_defs = [
        ("h1", "— SOLO LA CAMPAÑA (la tierra no cuesta) —", "— SEASON ONLY (land costs nothing) —"),
        ("f_sown", "Superficie sembrada (ha)", "Sown area (ha)"),
        ("f_crops", "Cultivos", "Crops"),
        ("f_margin", "Margen de la campaña por ha sembrada (USD/ha)", "Season margin per sown ha (USD/ha)"),
        ("f_profit", "Ganancia de la campaña (USD)", "Season profit (USD)"),
        ("f_roc", "Retorno sobre el capital (campaña 14,5 m)", "Return on capital (14.5m season)"),
        ("f_roc_ann", "Retorno sobre el capital (anual vs tasa dep.)", "Return on capital (annual vs deposit rate)"),
        ("h2", "— CON EL COSTO DE LA TIERRA (alquiler de la zona) —", "— WITH THE LAND'S COST (regional rent) —"),
        ("rent", "Alquiler de la zona (USD/ha)", "Regional rent (USD/ha)"),
        ("decision", "Lo que conviene", "Best use"),
        ("w_profit", "Ganancia (USD)", "Profit (USD)"),
        ("w_roc_land", "Retorno sobre capital + tierra (campaña 14,5 m)", "Return on capital + land (14.5m season)"),
        ("w_roc_land_ann", "Retorno sobre capital + tierra (anual vs tasa dep.)", "Return on capital + land (annual vs deposit rate)"),
        ("verdict", "Conclusión", "Bottom line"),
        ("h3", "— OTROS —", "— OTHER —"),
        ("cap_sp", "Cuánto vale un dólar más de capital (USD)", "What an extra dollar of capital is worth (USD)"),
        ("freight", "Flete interno (USD/t)", "Inland freight (USD/t)"),
        ("freight_share", "Incidencia del flete", "Freight share"),
        ("status", "Estado de datos", "Data status"),
    ]

    metrics_col = [es if is_es else en for _, es, en in row_defs]
    data: dict[str, list[Any]] = {col_metric: metrics_col}

    for i, it in enumerate(items):
        name = it.get("name") or it.get("region") or f"Run {i+1}"
        is_ph = bool(it.get("placeholder", False))
        col_name = f"{name} ⚠️ (Provisorio)" if is_ph and is_es else (f"{name} ⚠️ (Provisional)" if is_ph else name)

        fo = it.get("farming_only") or {}
        wl = it.get("with_land_cost") or {}
        lt = it.get("land_tenure", {})

        def crops_of(hectares):
            parts = []
            for c, h in (hectares or {}).items():
                if h > 0.1:
                    c_name = CROP_TRANSLATION_TO_ES.get(c, c) if is_es else c
                    parts.append(f"{c_name}: {num(h, 1)}")
            return ", ".join(parts) if parts else "-"

        # Saved runs from the Scenario tab have no farming_only block: show their own plan there.
        f_hect = fo.get("hectares", it.get("hectares", {}))
        f_sown = fo.get("sown_ha", sum((it.get("hectares") or {}).values()))
        margin = fo.get("profit_per_sown_ha")
        f_profit = fo.get("profit_usd")
        f_roc = fo.get("return_on_capital", it.get("return_on_capital"))
        f_roc_ann = fo.get("return_on_capital_annual", it.get("return_on_capital_annual"))
        if f_roc_ann is None and f_roc is not None and 1.0 + float(f_roc) > 0:
            f_roc_ann = (1.0 + float(f_roc)) ** (24.0 / 29.0) - 1.0
        dep_rate = float(wl.get("deposit_rate_annual", fo.get("deposit_rate_annual", it.get("deposit_rate_annual", 0.04))))

        rent = float(wl.get("regional_rent_usd_ha", lt.get("regional_rent_usd_ha", 0.0)) or 0.0)
        rent_out = float(wl.get("rent_out_ha", lt.get("rent_out_ha", 0.0)) or 0.0)
        rent_in = float(wl.get("rent_in_ha", lt.get("rent_in_ha", 0.0)) or 0.0)
        buy = float(wl.get("buy_ha", lt.get("buy_ha", 0.0)) or 0.0)
        w_sown = float(wl.get("sown_ha", sum((it.get("hectares") or {}).values())))
        parts = []
        if w_sown > 0.1:
            parts.append(("sembrar " if is_es else "farm ") + num(w_sown, 1) + " ha")
        if rent_out > 0.1:
            parts.append(("dar en alquiler " if is_es else "rent out ") + num(rent_out, 1) + " ha")
        if rent_in > 0.1:
            parts.append(("tomar en alquiler " if is_es else "rent in ") + num(rent_in, 1) + " ha")
        if buy > 0.1:
            parts.append(("comprar " if is_es else "buy ") + num(buy, 1) + " ha")
        decision = ", ".join(parts) if parts else ("dejar la plata a plazo fijo" if is_es else "keep the cash on deposit")
        w_profit = wl.get("profit_usd")
        w_roc_land = wl.get("return_on_capital_and_land", it.get("return_on_capital_and_land"))
        w_roc_land_ann = wl.get("return_on_capital_and_land_annual", it.get("return_on_capital_and_land_annual"))
        if w_roc_land_ann is None and w_roc_land is not None and 1.0 + float(w_roc_land) > 0:
            w_roc_land_ann = (1.0 + float(w_roc_land)) ** (24.0 / 29.0) - 1.0

        if margin is not None and rent > 0:
            if margin >= rent:
                verdict = (f"sembrar deja {num(margin, 0)} USD/ha, más que los {num(rent, 0)} del alquiler" if is_es
                           else f"farming earns {num(margin, 0)} USD/ha, more than the {num(rent, 0)} rent")
            else:
                verdict = (f"sembrar deja {num(margin, 0)} USD/ha, menos que los {num(rent, 0)} del alquiler" if is_es
                           else f"farming earns {num(margin, 0)} USD/ha, less than the {num(rent, 0)} rent")
        else:
            verdict = "-"

        cap_sp = float(it.get("capital_shadow_price", 0.0))
        freight = float(it.get("freight_usd_t", 0.0))
        raw_fs = float(it.get("freight_share", 0.0) or 0.0)
        status_str = ("⚠️ Provisorio" if is_es else "⚠️ Provisional") if is_ph else ("Verificado" if is_es else "Verified")

        col_vals = [
            "",
            num(float(f_sown), 1),
            crops_of(f_hect),
            num(float(margin), 0) if margin is not None else "-",
            num(float(f_profit), 0) if f_profit is not None else "-",
            pct(float(f_roc)) if f_roc is not None else "-",
            f"{pct(float(f_roc_ann))} (dep. {pct(dep_rate)})" if f_roc_ann is not None else "-",
            "",
            num(rent, 0) if rent > 0 else "-",
            decision,
            num(float(w_profit), 0) if w_profit is not None else "-",
            pct(float(w_roc_land)) if w_roc_land is not None else "-",
            f"{pct(float(w_roc_land_ann))} (dep. {pct(dep_rate)})" if w_roc_land_ann is not None else "-",
            verdict,
            "",
            num(cap_sp, 4),
            num(freight, 1),
            pct(raw_fs) if raw_fs <= 1.0 else f"{raw_fs:.1f}%",
            status_str,
        ]
        data[col_name] = col_vals

    return pd.DataFrame(data)


# ==============================================================================
# Backend Runner Function
# ==============================================================================


def parse_constraints_input(constraints_input: Any) -> list[dict]:
    """Parse constraints dataframe, list of dicts, or list of lists into engine constraint format."""
    if constraints_input is None:
        return []
    if isinstance(constraints_input, list) and all(isinstance(x, dict) for x in constraints_input):
        return constraints_input
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
    deposit_rate_pct: float = 4.0,
    start_date: str | None = None,
    supplier_delay: int = 0,
    supplier_surcharge_pct: float = 0.0,
    storage_capacity_t: float = 1000.0,
    price_source: str = "MAGyP default",
    constraints_df: Any = None,
    lang: str = "es",
    region: str = "southeast_buenos_aires",
    owned_ha: float | None = None,
    max_rent_in_ha: float = 0.0,
    allow_rent_out: bool = False,
    max_buy_ha: float = 0.0,
    livestock: list[str] | None = None,
    livestock_only_ha: float = 0.0,
    max_rent_out_ha: float | None = None,
    regional_rent_usd_ha: float | None = None,
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
        "deposit_rate_annual": float(deposit_rate_pct) / 100.0,
        "input_payment_delay_fortnights": int(supplier_delay),
        "input_delay_surcharge": float(supplier_surcharge_pct) / 100.0,
        "storage_capacity_t": float(storage_capacity_t),
        "region": norm_reg,
        "lang": lang,
    }
    if start_date:
        s_date_str = str(start_date).strip()
        if "/" in s_date_str:
            parts = s_date_str.split("/")
            if len(parts) == 3:
                try:
                    d_int, m_int, y_int = int(parts[0]), int(parts[1]), int(parts[2])
                    scenario_payload["start_date"] = f"{y_int:04d}-{m_int:02d}-{d_int:02d}"
                except ValueError:
                    scenario_payload["start_date"] = s_date_str
            else:
                scenario_payload["start_date"] = s_date_str
        elif s_date_str.lower() in ("season", "base"):
            pass
        elif s_date_str:
            scenario_payload["start_date"] = s_date_str

    if owned_ha:                                   # an empty or 0 field means "all of area_ha is owned"
        scenario_payload["owned_ha"] = float(owned_ha)
    if max_rent_in_ha > 0:
        scenario_payload["max_rent_in_ha"] = float(max_rent_in_ha)
    scenario_payload["allow_rent_out"] = bool(allow_rent_out)
    if max_rent_out_ha is not None and max_rent_out_ha != "":
        try:
            scenario_payload["max_rent_out_ha"] = float(max_rent_out_ha)
        except (ValueError, TypeError):
            pass
    if regional_rent_usd_ha is not None and regional_rent_usd_ha != "":
        try:
            scenario_payload["regional_rent_usd_ha"] = float(regional_rent_usd_ha)
        except (ValueError, TypeError):
            pass
    if max_buy_ha > 0:
        scenario_payload["max_buy_ha"] = float(max_buy_ha)
    if livestock:
        scenario_payload["livestock"] = list(livestock)
    if livestock_only_ha > 0:
        scenario_payload["livestock_only_ha"] = float(livestock_only_ha)

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

    tax_raw = run_tool("tax_wedge", json.dumps({"scenario": scenario_payload, "lang": lang}))
    tax_res = json.loads(tax_raw) if tax_raw else {}

    # 1. Build Plan Card
    is_es = lang == "es"
    sc_meta = build_res.get("scenario", {})
    npv = eval_res.get("npv_usd", 0.0)
    unsown = eval_res.get("unsown_ha", 0.0)
    max_cred = eval_res.get("max_credit_usd", 0.0)
    hectares = eval_res.get("hectares", {})
    cal_block = eval_res.get("calendar", {})
    season_start_actual = cal_block.get("season_start", REGIONS[norm_reg].get("season_start", "2026-05"))

    # Peak credit fortnight with year
    debt_list = eval_res.get("debt", [])
    if debt_list and max(debt_list) > 1e-6:
        peak_idx = max(range(len(debt_list)), key=lambda p: debt_list[p])
        max_fortnight_str = fortnight_label(season_start_actual, peak_idx, lang=lang)
    else:
        max_fortnight_str = eval_res.get("max_credit_fortnight", "N/A")

    crop_names_display = {
        "wheat": "Trigo" if is_es else "Wheat",
        "corn": "Maíz" if is_es else "Corn",
        "soybean": "Soja" if is_es else "Soybean",
        "sunflower": "Girasol" if is_es else "Sunflower",
    }

    npv_fmt = format_number_es(npv) if is_es else f"{npv:,.2f}"
    cred_fmt = format_number_es(int(round(max_cred))) if is_es else f"{max_cred:,.0f}"

    sy, sm = [int(x) for x in season_start_actual.split("-")]
    m_names_es = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    m_names_en = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    pv_mon_str = m_names_es[sm-1] + f" {sy}" if is_es else m_names_en[sm-1] + f" {sy}"
    pv_note = f"Valor presente al {pv_mon_str}" if is_es else f"Present value as of {pv_mon_str}"

    npv_after_it = tax_res.get("npv_after_income_tax_usd", npv)
    npv_after_it_fmt = format_number_es(npv_after_it) if is_es else f"{npv_after_it:,.2f}"

    if norm_reg in ("southeast_buenos_aires", "pampas_core"):
        tax_clarity_line = (
            f"El VAN ya descuenta retenciones (están en el precio), Ingresos Brutos, débitos y créditos e Inmobiliario; "
            f"no descuenta Ganancias. Después de Ganancias: USD {npv_after_it_fmt}."
            if is_es
            else f"The NPV already discounts export duties (factored into prices), gross receipts, transaction and land taxes; "
                 f"it does not discount income tax. After income tax: USD {npv_after_it_fmt}."
        )
    else:
        in_npv_names = [tx["name"] for tx in tax_res.get("taxes", []) if tx.get("in_npv") is True]
        not_in_npv_names = [tx["name"] for tx in tax_res.get("taxes", []) if tx.get("in_npv") is False]
        in_str = ", ".join(in_npv_names) if in_npv_names else ("impuestos directos" if is_es else "direct taxes")
        not_str = ", ".join(not_in_npv_names) if not_in_npv_names else ("Ganancias" if is_es else "Income tax")
        tax_clarity_line = (
            f"El VAN ya descuenta {in_str}; no descuenta {not_str}. Después de Ganancias: USD {npv_after_it_fmt}."
            if is_es
            else f"The NPV already discounts {in_str}; it does not discount {not_str}. After income tax: USD {npv_after_it_fmt}."
        )

    plan_md_lines = [
        f"### **Valor Presente Neto (NPV):** USD {npv_fmt}"
        if is_es
        else f"### **Net Present Value (NPV):** USD {npv_fmt}",
        f"*{pv_note}*",
        f"*{tax_clarity_line}*",
        "",
    ]

    season_lines = build_season_line(cal_block, lang=lang, hectares=hectares)
    plan_md_lines.extend(season_lines)
    plan_md_lines.append("")
    plan_md_lines.append("#### **Siembra propuesta:**" if is_es else "#### **Crop Allocation:**")

    has_farmer_override = False
    for c, ha in hectares.items():
        c_label = crop_names_display.get(c, c)
        ha_fmt = format_number_es(ha, 1) if is_es else f"{ha:.1f}"

        price_orig = sc_meta.get(f"price_{c}", {}).get("origin", "")
        yield_orig = sc_meta.get(f"yield_{c}", {}).get("origin", "")
        farmer_tags = []
        if price_orig == "farmer":
            farmer_tags.append("precio informado" if is_es else "farmer price")
            has_farmer_override = True
        if yield_orig == "farmer":
            farmer_tags.append("rinde informado" if is_es else "farmer yield")
            has_farmer_override = True

        tag_str = f" *({', '.join(farmer_tags)})*" if farmer_tags else ""
        plan_md_lines.append(f"- **{c_label}**: {ha_fmt} ha{tag_str}")

    rent_out_val = eval_res.get("land_tenure", {}).get("rent_out_ha", 0.0)
    rent_usd = eval_res.get("regional_rent_usd_ha", 0.0)
    rent_inc = eval_res.get("rent_out_income_usd", round(rent_out_val * rent_usd, 2))
    if rent_out_val > 1e-4:
        ro_ha_fmt = format_number_es(rent_out_val, 1) if is_es else f"{rent_out_val:.1f}"
        ro_rent_fmt = format_number_es(rent_usd, 0) if rent_usd == int(rent_usd) else (format_number_es(rent_usd, 1) if is_es else f"{rent_usd:.1f}")
        ro_inc_fmt = format_number_es(int(round(rent_inc))) if is_es else f"{int(round(rent_inc)):,}"
        if is_es:
            plan_md_lines.append(f"- **Dado en alquiler:** {ro_ha_fmt} ha a {ro_rent_fmt} USD/ha ({ro_inc_fmt} USD)")
        else:
            plan_md_lines.append(f"- **Rented out:** {ro_ha_fmt} ha at {ro_rent_fmt} USD/ha ({ro_inc_fmt} USD)")

    if unsown > 1e-3:
        unsown_fmt = format_number_es(unsown, 1) if is_es else f"{unsown:.1f}"
        plan_md_lines.append(
            f"- *Superficie sin sembrar:* {unsown_fmt} ha"
            if is_es
            else f"- *Unsown area:* {unsown_fmt} ha"
        )

    tc = eval_res.get("tenure_comparison")
    if tc:
        fo_val = tc.get("farm_only_npv_usd", 0.0)
        ra_val = tc.get("rent_all_npv_usd", 0.0)
        be_val = tc.get("break_even_rent_usd_ha", 0.0)
        best_code = tc.get("best", "farm")
        fo_fmt = format_number_es(fo_val, 2) if is_es else f"{fo_val:,.2f}"
        ra_fmt = format_number_es(ra_val, 2) if is_es else f"{ra_val:,.2f}"
        be_fmt = format_number_es(be_val, 2) if is_es else f"{be_val:,.2f}"
        is_ph = eval_res.get("regional_rent_placeholder", False)
        ro_rent_fmt = format_number_es(rent_usd, 0) if rent_usd == int(rent_usd) else (format_number_es(rent_usd, 1) if is_es else f"{rent_usd:.1f}")

        if rent_out_val > 1e-4:
            if is_es:
                best_desc = "alquilar todo" if best_code == "rent_out" else ("sembrar todo" if best_code == "farm" else "una combinación de siembra y alquiler")
                ph_note = " (alquiler estimado: cargá el tuyo en Opciones avanzadas)" if is_ph else ""
                plan_md_lines.append(f"Sembrando todo lo que alcanza: VAN USD {fo_fmt}. Alquilando todo: VAN USD {ra_fmt}. El plan elige {best_desc}.{ph_note}")
            else:
                best_desc = "renting all out" if best_code == "rent_out" else ("farming as much as possible" if best_code == "farm" else "a combination of farming and renting out")
                ph_note = " (estimated rent: enter yours in Advanced options)" if is_ph else ""
                plan_md_lines.append(f"Farming as much as possible: NPV USD {fo_fmt}. Renting all out: NPV USD {ra_fmt}. The plan chooses {best_desc}.{ph_note}")
        else:
            diff = ra_val - eval_res.get("npv_usd", fo_val)
            if is_es:
                diff_fmt = f"+{format_number_es(diff, 2)}" if diff >= 0 else f"-{format_number_es(abs(diff), 2)}"
                ph_note = " (alquiler estimado: cargá el que te ofrecen en Opciones avanzadas)" if is_ph else ""
                plan_md_lines.append(f"Si alquilaras todo a {ro_rent_fmt} USD/ha: VAN {ra_fmt} ({diff_fmt} USD). Alquilar conviene si te pagan más de {be_fmt} USD/ha.{ph_note}")
            else:
                diff_fmt = f"{diff:+,.2f}"
                ph_note = " (estimated rent: enter the offer in Advanced options)" if is_ph else ""
                plan_md_lines.append(f"If you rented everything out at {ro_rent_fmt} USD/ha: NPV {ra_fmt} ({diff_fmt} USD). Renting out pays more if you get over {be_fmt} USD/ha.{ph_note}")

    ls_names_display = {
        "cow_calf": "Cría vacuna (rodeo propio)" if is_es else "Cow-calf (owned herd)",
        "cow_calf_herd_purchase": "Cría vacuna (compra de hacienda)" if is_es else "Cow-calf (herd purchase)",
        "steer_fattening": "Invernada / engorde" if is_es else "Steer fattening",
    }
    hectares_ls = eval_res.get("hectares_livestock", {})
    if hectares_ls:
        plan_md_lines.append("")
        plan_md_lines.append("#### **Ganadería propuesta:**" if is_es else "#### **Livestock Allocation:**")
        for a, ha in hectares_ls.items():
            if ha > 1e-6:
                a_label = ls_names_display.get(a, a)
                ha_fmt = format_number_es(ha, 1) if is_es else f"{ha:.1f}"
                plan_md_lines.append(f"- **{a_label}**: {ha_fmt} ha")
    elif norm_reg in ("southeast_buenos_aires", "pampas_core"):
        plan_md_lines.append("")
        plan_md_lines.append(
            "Ganadería: no incluida. Marcá cría o invernada arriba para que compita por la tierra."
            if is_es
            else "Livestock: not included. Check cow-calf or steer fattening above to compete for land."
        )

    plan_md_lines.append("")
    if max_cred <= 1e-4:
        plan_md_lines.append(
            "**Pico de crédito utilizado:** USD 0"
            if is_es
            else "**Peak credit used:** USD 0"
        )
    elif max_cred >= credit_line_usd - 1:
        plan_md_lines.append(
            f"**Pico de crédito utilizado:** USD {cred_fmt} ({max_fortnight_str}): usás toda la línea; más crédito cambiaría el plan."
            if is_es
            else f"**Peak credit used:** USD {cred_fmt} ({max_fortnight_str}): you are using the entire line; more credit would change the plan."
        )
    else:
        plan_md_lines.append(
            f"**Pico de crédito utilizado:** USD {cred_fmt} ({max_fortnight_str})"
            if is_es
            else f"**Peak credit used:** USD {cred_fmt} ({max_fortnight_str})"
        )

    routes_list = eval_res.get("routes", [])
    if routes_list:
        plan_md_lines.append("")
        plan_md_lines.append("#### **Logística y Rutas de Flete:**" if is_es else "#### **Freight Routes & Logistics:**")
        rdata = load_region_data(norm_reg)
        p_point = rdata.get("price_point")
        inland_f = eval_res.get("freight_usd_t", 0.0)
        if p_point == "local_elevator" and inland_f <= 1e-4:
            lugar = "Sorriso" if norm_reg == "mato_grosso" else ("elevador local" if is_es else "local elevator")
            b_str = "-20 a -25" if norm_reg == "mato_grosso" else "-15"
            if is_es:
                plan_md_lines.append(f"- Precio puesto en {lugar} (el flete al puerto ya está descontado en la base: {b_str} USD/t).")
            else:
                plan_md_lines.append(f"- Delivered price at {lugar} (freight to port is already discounted in the basis: {b_str} USD/t).")
        else:
            primary_route = None
            for r_item in routes_list:
                r_name = r_item.get("name", r_item.get("id"))
                if is_es and "Direct freight" in r_name:
                    r_name = r_name.replace("Direct freight", "Flete directo")
                r_tonnes = r_item.get("tonnes", 0.0)
                if r_tonnes > 1e-3:
                    if primary_route is None:
                        primary_route = r_item
                    tonnes_fmt = format_number_es(r_tonnes, 1) if is_es else f"{r_tonnes:.1f}"
                    sp = r_item.get("capacity_shadow_price_usd_t", 0.0)
                    sp_str = f" *(valor de mayor capacidad: +{sp:.2f} USD/t)*" if (sp > 1e-4 and is_es) else (f" *(higher capacity value: +{sp:.2f} USD/t)*" if sp > 1e-4 else "")
                    plan_md_lines.append(f"- **{r_name}**: {tonnes_fmt} t{sp_str}")
            if len(routes_list) > 1:
                for alt in routes_list:
                    if alt.get("tonnes", 0.0) < 1e-3:
                        alt_name = alt.get("name", alt.get("id"))
                        if is_es and "Direct freight" in alt_name:
                            alt_name = alt_name.replace("Direct freight", "Flete directo")
                        note = "*(la alternativa pagaría menos)*" if is_es else "*(alternative route would pay less)*"
                        plan_md_lines.append(f"- *{alt_name}*: 0.0 t {note}")

    # Fuentes: build accurately per region
    rdata = load_region_data(norm_reg)
    r_date = rdata.get("date", "2026-06")
    ry, rm = [int(x) for x in r_date.split("-")]
    m_short_es = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    m_short_en = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    date_str = f"{m_short_es[rm-1]} {ry}" if is_es else f"{m_short_en[rm-1]} {ry}"

    if norm_reg == "pampas_core":
        fuente = "MAGyP"
        reg_lbl = "Zona Núcleo (Pergamino)" if is_es else "Pampas core (Pergamino)"
    elif norm_reg == "southeast_buenos_aires":
        fuente = "MAGyP"
        reg_lbl = "Sudeste de Buenos Aires" if is_es else "Southeast Buenos Aires"
    elif norm_reg == "iowa":
        fuente = "Iowa State University Extension"
        reg_lbl = "Iowa"
    elif norm_reg == "mato_grosso":
        fuente = "IMEA"
        reg_lbl = "Mato Grosso (Sorriso)"
    else:
        fuente = regional_source_label(norm_reg)
        reg_lbl = REGIONS.get(norm_reg, {}).get("name", norm_reg)

    source_line = (
        f"- Rindes, precios y costos: {fuente}, {date_str}, {reg_lbl}"
        if is_es
        else f"- Yields, prices and costs: {fuente}, {date_str}, {reg_lbl}"
    )

    plan_md_lines.append("")
    plan_md_lines.append("---")
    plan_md_lines.append("**Fuentes:**" if is_es else "**Sources:**")
    if eval_res.get("price_source"):
        plan_md_lines.append(f"- {t['source_curve'].format(source=eval_res['price_source'], as_of='')}")
    plan_md_lines.append(source_line)
    if has_farmer_override:
        plan_md_lines.append(
            "- Valores propios del productor marcados arriba"
            if is_es
            else "- Custom farmer inputs marked above"
        )

    if eval_res.get("warning"):
        plan_md_lines.append(f"> ⚠️ *{eval_res['warning']}*")

    plan_markdown = "\n".join(plan_md_lines)

    # 2. Charts
    fig_a = create_internal_rate_chart(shadow_res, lang=lang, season_start=season_start_actual)
    fig_b = create_resource_shadow_prices_chart(shadow_res, lang=lang)
    fig_c = create_cash_debt_chart(eval_res, lang=lang, season_start=season_start_actual)
    fig_sales = create_sales_chart(eval_res, lang=lang, season_start=season_start_actual)

    # Value cards for Land and Storage (Fix 2 & SPEC-23 & SPEC-37)
    land_val = shadow_res.get("land", {}).get("usd_per_extra_ha", 0.0)
    stor_val = shadow_res.get("storage", {}).get("usd_per_extra_tonne", 0.0)

    if land_val < 1e-4:
        land_card = "Tierra: una hectárea más no agrega valor (sobra tierra para los fondos disponibles)." if is_es else "Land: an extra hectare adds no value (land is abundant for available funds)."
    else:
        land_fmt = format_number_es(land_val, 2) if is_es else f"{land_val:.2f}"
        if eval_res.get("land_tenure", {}).get("rent_out_ha", 0.0) > 1e-4:
            motivo = "lo que te pagan por alquilarla" if is_es else "what you are paid to rent it out"
        elif eval_res.get("unsown_ha", 0.0) > 1e-3:
            rot_cap_found = False
            for c in eval_res.get("constraints", []):
                if c.get("binding") and "share" in c.get("type", "").lower():
                    crop_nm = CROP_TRANSLATION_TO_ES.get(c.get("crop"), c.get("crop")) if is_es else c.get("crop")
                    pct_val = int(round(c.get("value", 0.5) * 100)) if c.get("value", 0) <= 1.0 else int(round(c.get("value", 50)))
                    motivo = f"porque la {crop_nm} está en su tope del {pct_val} % del campo" if is_es else f"because {crop_nm} is at its {pct_val}% cap"
                    rot_cap_found = True
                    break
            if not rot_cap_found:
                soy_ha = hectares.get("soybean", 0.0)
                tot_a = float(area_ha)
                if tot_a > 0 and abs(soy_ha / tot_a - 0.5) < 0.05:
                    motivo = "porque la soja está en su tope del 50 % del campo" if is_es else "because soybean is at its 50% cap"
                    rot_cap_found = True
            if not rot_cap_found:
                motivo = "no: falta plata para sembrarla" if is_es else "no: lack of capital to sow it"
        else:
            motivo = "rinde neto de la mejor rotación posible" if is_es else "net margin of the best possible rotation"

        rot_compat = (
            f"<!-- aunque quedan {unsown_fmt} ha sin sembrar: el valor viene de la rotación (con una hectárea más podés sembrar más del cultivo que está en su tope) -->"
            if (is_es and unsown > 0)
            else (
                f"<!-- even though {unsown:.1f} ha remain unsown: the value comes from the rotation (with an extra hectare you can sow more of the crop that is at its cap) -->"
                if (not is_es and unsown > 0)
                else ""
            )
        )
        land_card = f"Tierra: una hectárea más te vale {land_fmt} USD: {motivo}.{rot_compat}" if is_es else f"Land: an extra hectare is worth {land_fmt} USD: {motivo}.{rot_compat}"

    if stor_val < 1e-4:
        storage_card = "Almacenaje: 0 USD/t — no es una restricción activa" if is_es else "Storage: 0 USD/t — not an active constraint"
    else:
        stor_fmt = format_number_es(stor_val, 2) if is_es else f"{stor_val:.2f}"
        storage_card = f"Almacenaje: {stor_fmt} USD/t — cada tonelada adicional aportaría {stor_fmt} USD de valor presente" if is_es else f"Storage: {stor_fmt} USD/t — each additional tonne would add {stor_fmt} USD in present value"

    low_cards = []
    low_sp = eval_res.get("livestock_only_shadow_price_usd_ha", 0.0)
    if low_sp > 1e-4:
        low_fmt = format_number_es(low_sp, 2) if is_es else f"{low_sp:.2f}"
        low_label = "- **Tierra ganadera / bajo:**" if is_es else "- **Livestock low land:**"
        low_cards.append(f"{low_label} {low_fmt} USD/ha")

    extra_cards_str = ("\n" + "\n".join(low_cards)) if low_cards else ""
    res_hdr = "#### Otros recursos:" if is_es else "#### Other resources:"
    resource_cards_md = f"{res_hdr}\n- {land_card}\n- {storage_card}{extra_cards_str}"

    # 3. Constraints Table
    constraints_out = []
    for c in eval_res.get("constraints", []):
        cost = c.get("opportunity_cost", 0)
        cost_fmt = format_number_es(cost, 2) if is_es else f"{cost:.2f}"
        crop_val = c.get("crop", "")
        crop_display = CROP_TRANSLATION_TO_ES.get(crop_val, crop_val) if is_es else crop_val

        if is_es:
            constraints_out.append({
                "Restricción": c.get("label") or c.get("meaning") or f"{c.get('type')} {crop_display}",
                "Límite": c.get("limit", c.get("value", "-")),
                "Usado": c.get("used", "-"),
                "Costo de oportunidad": cost_fmt,
            })
        else:
            constraints_out.append({
                "Constraint": c.get("label") or c.get("meaning") or f"{c.get('type')} {crop_display}",
                "Limit": c.get("limit", c.get("value", "-")),
                "Used": c.get("used", "-"),
                "Opportunity cost": cost_fmt,
            })
    if constraints_out:
        constraints_table_df = pd.DataFrame(constraints_out)
    else:
        constraints_table_df = pd.DataFrame(columns=["Restricción", "Límite", "Usado", "Costo de oportunidad"] if is_es else ["Constraint", "Limit", "Used", "Opportunity cost"])

    lt = eval_res.get("land_tenure", {})
    comp = eval_res.get("land_comparison", "")
    season_m = lt.get("season_months", 14.5)
    season_m_str = format_number_es(season_m, 1) if is_es else f"{season_m:.1f}"

    roc_season_pct = lt.get("return_on_capital_pct", round(lt.get("return_on_capital", 0.0) * 100.0, 1))
    roc_annual_pct = lt.get("return_on_capital_annual_pct", round(lt.get("return_on_capital_annual", 0.0) * 100.0, 1))
    dep_rate_pct = lt.get("deposit_rate_annual_pct", round(lt.get("deposit_rate_annual", 0.04) * 100.0, 1))

    roc_land_season_pct = lt.get("return_on_capital_and_land_pct")
    roc_land_annual_pct = lt.get("return_on_capital_and_land_annual_pct")
    lp_val = lt.get("land_price_usd_ha")
    if lp_val is None:
        lp_meta = sc_meta.get("land_price_usd_ha")
        lp_val = lp_meta.get("value", 0.0) if isinstance(lp_meta, dict) else lp_meta
    try:
        land_price_val = float(lp_val or 0.0)
    except (TypeError, ValueError):
        land_price_val = 0.0

    owned_val = lt.get("owned_ha", area_ha)
    rent_in_val = lt.get("rent_in_ha", 0.0)
    rent_out_val = lt.get("rent_out_ha", 0.0)
    buy_val = lt.get("buy_ha", 0.0)

    if is_es:
        owned_fmt = format_number_es(owned_val, 1) if owned_val is not None else "0"
        rent_in_fmt = format_number_es(rent_in_val, 1)
        rent_out_fmt = format_number_es(rent_out_val, 1)
        buy_fmt = format_number_es(buy_val, 1)
        roc_s_fmt = format_number_es(roc_season_pct, 1)
        roc_a_fmt = format_number_es(roc_annual_pct, 1)
        dep_fmt = format_number_es(dep_rate_pct, 1)

        ret_lines = [
            f"- **Retorno sobre el capital:** {roc_s_fmt}% en la campaña (12 meses de producción, ventas hasta {season_m_str} meses) ({roc_a_fmt}% anual vs. tasa depósito {dep_fmt}%)"
        ]
        if roc_land_season_pct is not None:
            roc_ls_fmt = format_number_es(roc_land_season_pct, 1)
            roc_la_fmt = format_number_es(roc_land_annual_pct, 1)
            ret_lines.append(
                f"- **Retorno sobre capital y tierra:** {roc_ls_fmt}% en la campaña ({season_m_str} meses) (12 meses de producción, ventas hasta {season_m_str} meses) ({roc_la_fmt}% anual vs. tasa depósito {dep_fmt}%)"
            )

        land_card_md = (
            f"### Decisiones de tenencia y tierra:\n"
            f"- **Tierra propia:** {owned_fmt} ha | "
            f"**Tomada en alquiler:** {rent_in_fmt} ha | "
            f"**Dada en alquiler:** {rent_out_fmt} ha | "
            f"**Comprada:** {buy_fmt} ha\n"
            + "\n".join(ret_lines)
        )
    else:
        owned_fmt = f"{float(owned_val):.1f}" if owned_val is not None else "0"
        rent_in_fmt = f"{float(rent_in_val):.1f}"
        rent_out_fmt = f"{float(rent_out_val):.1f}"
        buy_fmt = f"{float(buy_val):.1f}"
        roc_s_fmt = f"{roc_season_pct:.1f}"
        roc_a_fmt = f"{roc_annual_pct:.1f}"
        dep_fmt = f"{dep_rate_pct:.1f}"

        ret_lines = [
            f"- **Return on capital:** {roc_s_fmt}% for the season (12 production months, sales up to {season_m_str} months) ({roc_a_fmt}% annual vs. deposit rate {dep_fmt}%)"
        ]
        if roc_land_season_pct is not None:
            roc_ls_fmt = f"{roc_land_season_pct:.1f}"
            roc_la_fmt = f"{roc_land_annual_pct:.1f}"
            ret_lines.append(
                f"- **Return on capital and land:** {roc_ls_fmt}% for the season ({season_m_str} months) (12 production months, sales up to {season_m_str} months) ({roc_la_fmt}% annual vs. deposit rate {dep_fmt}%)"
            )

        land_card_md = (
            f"### Land decisions and tenure:\n"
            f"- **Owned land:** {owned_fmt} ha | "
            f"**Rented in:** {rent_in_fmt} ha | "
            f"**Rented out:** {rent_out_fmt} ha | "
            f"**Bought:** {buy_fmt} ha\n"
            + "\n".join(ret_lines)
        )

    # Tax table
    tax_rows = []
    taxes_ar_placeholder = bool(load_taxes_data(norm_reg).get("placeholder", False))
    gross_rev = eval_res.get("gross_revenue_usd", 0.0)

    for tx in tax_res.get("taxes", []):
        is_export = tx.get("key") == "export_duties" or tx.get("tax") == "export_duties"
        usd_val = tx.get("usd", 0.0)
        in_npv_val = tx.get("in_npv")

        if in_npv_val is True:
            in_npv_str = "sí" if is_es else "Yes"
        elif in_npv_val is False:
            in_npv_str = "no" if is_es else "No"
        else:
            in_npv_str = "no aplica" if is_es else "N/A"

        if is_export and (in_npv_val is None or norm_reg in ("iowa", "mato_grosso")):
            usd_fmt = "no aplica" if is_es else "N/A"
            in_npv_str = "no aplica" if is_es else "N/A"
        else:
            usd_fmt = format_number_es(usd_val, 2) if is_es else f"{usd_val:,.2f}"
            if is_export and taxes_ar_placeholder and norm_reg in ("southeast_buenos_aires", "pampas_core"):
                usd_fmt += " (alícuotas a verificar (placeholder))" if is_es else " (rates to be verified (placeholder))"

        pct_val = tx.get("percent_gross_revenue", 0.0)
        pct_fmt = (format_number_es(pct_val, 2) + "%") if is_es else f"{pct_val:.2f}%"
        src_str = tx.get("source", "")
        if is_es:
            tax_rows.append({
                "Impuesto": tx.get("name"),
                "¿Ya está en el VAN?": in_npv_str,
                "Monto (USD)": usd_fmt,
                "% Ingreso Bruto": pct_fmt,
                "Fuente": src_str,
            })
        else:
            tax_rows.append({
                "Tax": tx.get("name"),
                "In NPV?": in_npv_str,
                "Amount (USD)": usd_fmt,
                "% Gross Revenue": pct_fmt,
                "Source": src_str,
            })

    in_npv_usd = tax_res.get("taxes_in_npv_usd", 0.0)
    not_in_npv_usd = tax_res.get("taxes_not_in_npv_usd", tax_res.get("income_tax_npv_usd", 0.0))
    npv_after_it_val = tax_res.get("npv_after_income_tax_usd", npv - not_in_npv_usd)

    in_pct = (in_npv_usd / gross_rev * 100.0) if gross_rev > 0 else 0.0
    not_in_pct = (not_in_npv_usd / gross_rev * 100.0) if gross_rev > 0 else 0.0

    in_pct_fmt = (format_number_es(in_pct, 2) + "%") if is_es else f"{in_pct:.2f}%"
    not_in_pct_fmt = (format_number_es(not_in_pct, 2) + "%") if is_es else f"{not_in_pct:.2f}%"

    if is_es:
        tax_rows.append({
            "Impuesto": "Ya descontados en el VAN",
            "¿Ya está en el VAN?": "sí",
            "Monto (USD)": format_number_es(in_npv_usd, 2),
            "% Ingreso Bruto": in_pct_fmt,
            "Fuente": "-",
        })
        tax_rows.append({
            "Impuesto": "A descontar: Ganancias",
            "¿Ya está en el VAN?": "no",
            "Monto (USD)": format_number_es(not_in_npv_usd, 2),
            "% Ingreso Bruto": not_in_pct_fmt,
            "Fuente": "-",
        })
        tax_rows.append({
            "Impuesto": "VAN después de Ganancias",
            "¿Ya está en el VAN?": "-",
            "Monto (USD)": format_number_es(npv_after_it_val, 2),
            "% Ingreso Bruto": "-",
            "Fuente": "-",
        })
    else:
        tax_rows.append({
            "Tax": "Already in NPV",
            "In NPV?": "Yes",
            "Amount (USD)": f"{in_npv_usd:,.2f}",
            "% Gross Revenue": in_pct_fmt,
            "Source": "-",
        })
        tax_rows.append({
            "Tax": "To discount: Income tax",
            "In NPV?": "No",
            "Amount (USD)": f"{not_in_npv_usd:,.2f}",
            "% Gross Revenue": not_in_pct_fmt,
            "Source": "-",
        })
        tax_rows.append({
            "Tax": "NPV after income tax",
            "In NPV?": "-",
            "Amount (USD)": f"{npv_after_it_val:,.2f}",
            "% Gross Revenue": "-",
            "Source": "-",
        })

    tax_wedge_df = pd.DataFrame(tax_rows)

    if is_es:
        disc_lines = []
        if norm_reg in ("southeast_buenos_aires", "pampas_core"):
            disc_lines.append("*Nota: los precios de MAGyP son FAS (ya netos de derechos de exportación).*")
        disc_lines.append("*Ganancias al 35 % de sociedades; una persona humana paga escala progresiva.*")
        tax_disclaimer_str = "\n\n".join(disc_lines)
    else:
        disc_lines = []
        if norm_reg in ("southeast_buenos_aires", "pampas_core"):
            disc_lines.append("*Note: MAGyP prices are FAS (already net of export duties).*")
        disc_lines.append("*Income tax calculated at 35% corporate rate; individuals pay progressive brackets.*")
        tax_disclaimer_str = "\n\n".join(disc_lines)

    # Break-even prices (SPEC-39)
    unsown_crops = [c for c in eval_res.get("hectares", {}) if eval_res["hectares"][c] <= 1e-4]
    be_rows = []
    be_fn_rows = []
    be_visible = False
    if unsown_crops:
        try:
            from dora.tools import break_even_prices
            be_res = break_even_prices(scenario_payload, verify=True, lang=lang)
            be_crops = be_res.get("crops", [])
            if be_crops:
                be_visible = True
                for cr in be_crops:
                    c_name = CROP_TRANSLATION_TO_ES.get(cr["crop"], cr["crop"]).capitalize() if is_es else cr["crop"].capitalize()
                    best = cr["best"]
                    ver_str = ("Sí" if cr["verified"] is True else ("No" if cr["verified"] is False else "-")) if is_es else ("Yes" if cr["verified"] is True else ("No" if cr["verified"] is False else "-"))
                    rise_str = f"+{format_number_es(best['rise_pct'], 1)}%" if is_es else f"+{best['rise_pct']:.1f}%"
                    if is_es:
                        be_rows.append({
                            "Cultivo": c_name,
                            "Mejor quincena para vender": best["label"],
                            "Precio hoy (USD/t)": best["price_now_usd_t"],
                            "Precio para que entre (USD/t)": best["price_needed_usd_t"],
                            "Suba": rise_str,
                            "Verificado": ver_str,
                        })
                    else:
                        be_rows.append({
                            "Crop": c_name,
                            "Best fortnight to sell": best["label"],
                            "Price today (USD/t)": best["price_now_usd_t"],
                            "Price needed (USD/t)": best["price_needed_usd_t"],
                            "Rise": rise_str,
                            "Verified": ver_str,
                        })

                    for fn in cr.get("by_fortnight", []):
                        fn_rise = f"+{format_number_es(fn['rise_pct'], 1)}%" if is_es else f"+{fn['rise_pct']:.1f}%"
                        if is_es:
                            be_fn_rows.append({
                                "Cultivo": c_name,
                                "Quincena": fn["label"],
                                "Precio hoy (USD/t)": fn["price_now_usd_t"],
                                "Precio para que entre (USD/t)": fn["price_needed_usd_t"],
                                "Suba": fn_rise,
                            })
                        else:
                            be_fn_rows.append({
                                "Crop": c_name,
                                "Fortnight": fn["label"],
                                "Price today (USD/t)": fn["price_now_usd_t"],
                                "Price needed (USD/t)": fn["price_needed_usd_t"],
                                "Rise": fn_rise,
                            })
        except Exception:
            pass

    be_df = pd.DataFrame(be_rows)
    be_fn_df = pd.DataFrame(be_fn_rows)

    rates_list = [r.get("rate_annual", 0.04) for r in shadow_res.get("capital", {}).get("rates_per_fortnight", [])]
    run_entry = {
        "region": norm_reg,
        "name": f"{REGIONS.get(norm_reg, {}).get('name', norm_reg)} · USD {own_capital_usd:,.0f}",
        "npv_usd": npv,
        "npv_per_ha": round(npv / area_ha, 2) if area_ha > 0 else 0.0,
        "return_on_capital": round(roc_season_pct / 100.0, 4),
        "return_on_capital_and_land": round(roc_land_season_pct / 100.0, 4) if (land_price_val > 0 and roc_land_season_pct is not None) else None,
        "hectares": hectares,
        "rent_in_ha": lt.get("rent_in_ha", 0.0),
        "buy_ha": lt.get("buy_ha", 0.0),
        "capital_shadow_price": shadow_res.get("own_capital", {}).get("usd_per_extra_dollar", 0.0),
        "land_shadow_price_usd_ha": land_val,
        "internal_rate_annual": rates_list,
        "freight_usd_t": float(REGIONS.get(norm_reg, {}).get("default_freight_usd_t", 25.0)),
        "freight_share": 0.12,
        "placeholder": bool(REGIONS.get(norm_reg, {}).get("placeholder", False)),
    }

    return {
        "npv": npv,
        "npv_usd": npv,
        "plan": plan_markdown,
        "plan_dict": eval_res,
        "run_entry": run_entry,
        "scenario_payload": scenario_payload,
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
        "tax_disclaimer": tax_disclaimer_str,
        "break_even_table": be_df,
        "break_even_fn_table": be_fn_df,
        "break_even_visible": be_visible,
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
  if (window._observatoryContainer !== container) {
    if (window._observatoryMap) {
      try { window._observatoryMap.remove(); } catch(e) {}
      window._observatoryMap = null;
    }
    window._observatoryMapInitialized = false;
    window._observatoryContainer = container;
  }
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

  var isEn = container.getAttribute('data-lang') === 'en';

  // Returns move with prices and can all sit above any fixed cut-off, so the
  // color ranks the regions against each other: darker is a higher return.
  var rocs = regionsData.map(function(r) { return Number(r.return_on_capital_pct) || 0; });
  var rocMin = Math.min.apply(null, rocs), rocMax = Math.max.apply(null, rocs);
  var rampColors = ['#e5f5e0', '#78c679', '#31a354', '#006837'];
  function getColor(roc) {
    if (!(rocMax > rocMin)) return rampColors[3];
    var i = Math.round((roc - rocMin) / (rocMax - rocMin) * 3);
    return rampColors[Math.max(0, Math.min(3, i))];
  }

  function fmt(x, digits) {
    var n = Number(x);
    if (!isFinite(n)) return String(x);
    return n.toLocaleString(isEn ? 'en-US' : 'es-AR', {minimumFractionDigits: digits, maximumFractionDigits: digits});
  }

  var modeColors = {
    'truck': '#ea580c',
    'rail': '#8b5cf6',
    'barge': '#06b6d4'
  };
  var modeNames = isEn
    ? {'truck': 'Truck', 'rail': 'Rail', 'barge': 'Barge', 'ocean': 'Ship'}
    : {'truck': 'Camión', 'rail': 'Tren', 'barge': 'Barcaza', 'ocean': 'Barco'};

  // Ocean legs are not drawn: a straight line from a port to Shanghai crosses
  // continents and pulls the eye away from the regions. Each port gets an
  // anchor instead, and the ship's cost goes in its tooltip.
  var bounds = [];
  var ports = {};
  regionsData.forEach(function(r) {
    (r.routes || []).forEach(function(rt) {
      (rt.legs || []).forEach(function(lg) {
        if (!lg.coords || lg.coords.length < 2) return;
        if (lg.mode === 'ocean') {
          var key = lg.coords[0].join(',');
          if (!ports[key]) ports[key] = {coords: lg.coords[0], name: lg.from, to: lg.to, costs: []};
          if (ports[key].costs.indexOf(lg.usd_t) < 0) ports[key].costs.push(lg.usd_t);
          return;
        }
        bounds.push(lg.coords[0], lg.coords[1]);
        var line = L.polyline(lg.coords, {
          color: modeColors[lg.mode] || '#666666',
          weight: 4,
          opacity: 0.85
        }).addTo(map);
        line.bindTooltip(
          '<b>' + (modeNames[lg.mode] || lg.mode) + '</b>: ' + (lg.from || '') + ' &rarr; ' + (lg.to || '') +
          '<br>USD ' + fmt(lg.usd_t, 1) + '/t' +
          (lg.source ? '<br><small>' + (isEn ? 'Source: ' : 'Fuente: ') + lg.source + '</small>' : ''),
          {sticky: true}
        );
      });
    });
  });

  Object.keys(ports).forEach(function(key) {
    var p = ports[key];
    var icon = L.divIcon({className: 'dora-port-icon', html: '⚓', iconSize: [18, 18], iconAnchor: [9, 9]});
    var costs = p.costs.map(function(c) { return fmt(c, 1); }).join(' / ');
    L.marker(p.coords, {icon: icon}).addTo(map).bindTooltip(
      '<b>' + p.name + '</b><br>' + modeNames.ocean + ' &rarr; ' + p.to + ': USD ' + costs + '/t'
    );
  });

  var best = null;
  regionsData.forEach(function(r) {
    if (r.coords && (best === null || r.return_on_capital_pct > best.return_on_capital_pct)) best = r;
  });

  regionsData.forEach(function(r) {
    if (!r.coords || r.coords.length < 2) return;
    bounds.push([r.coords[0], r.coords[1]]);
    var isBest = best && r.key === best.key;
    var marker = L.circleMarker(r.coords, {
      radius: isBest ? 14 : 11,
      fillColor: getColor(r.return_on_capital_pct),
      color: isBest ? '#111827' : '#1b4d24',
      weight: isBest ? 3 : 2,
      opacity: 1,
      fillOpacity: 0.9
    }).addTo(map);

    // Two regions close together (Pergamino and Balcarce) would stack their
    // labels over each other and over the routes to the north: their labels go
    // sideways, the northern one to the left and the southern one to the right.
    var direction = 'top';
    regionsData.forEach(function(o) {
      if (o === r || !o.coords) return;
      if (Math.abs(o.coords[0] - r.coords[0]) < 8 && Math.abs(o.coords[1] - r.coords[1]) < 8) {
        direction = r.coords[0] < o.coords[0] ? 'right' : 'left';
      }
    });
    var offsets = {'top': [0, -12], 'left': [-14, 0], 'right': [14, 0]};
    var label = '<b>' + (isBest ? '★ ' : '') + r.name + (r.placeholder ? ' ⚠️' : '') + '</b><br>' +
      (isEn ? 'Return ' : 'Retorno ') + fmt(r.return_on_capital_pct, 1) + ' %' +
      ' · ' + (isEn ? 'freight ' : 'flete ') + fmt(r.freight_usd_t, 0) + ' USD/t';
    marker.bindTooltip(label, {
      permanent: true,
      direction: direction,
      offset: offsets[direction],
      className: 'dora-region-label'
    });

    var popupHtml = '<b>' + r.name + '</b>' +
      (r.placeholder ? '<br><span style="color:#b91c1c; font-weight:bold;">⚠️ ' + (isEn ? 'Provisional data' : 'Datos provisorios') + '</span>' : '') + '<br>' +
      (isEn ? 'Return on capital: ' : 'Retorno sobre el capital: ') + '<b>' + fmt(r.return_on_capital_pct, 1) + ' %</b><br>' +
      (isEn ? 'NPV per ha: ' : 'VAN por ha: ') + '<b>USD ' + fmt(r.npv_per_ha, 0) + '</b><br>' +
      (isEn ? 'Port: ' : 'Puerto: ') + r.port + ' (' + fmt(r.distance_km, 0) + ' km)<br>' +
      (isEn ? 'Freight to port: ' : 'Flete al puerto: ') + 'USD ' + fmt(r.freight_usd_t, 1) + '/t<br>' +
      (isEn ? 'Prices: ' : 'Precios: ') + r.price_source;
    marker.bindPopup(popupHtml);
  });

  // The tab may be hidden when the map is built; bounds are fitted once the
  // container has a size (see the interval below).
  window._observatoryBounds = bounds;
  window._observatoryBoundsFitted = false;
  if (bounds.length > 0 && container.offsetWidth > 0) {
    map.invalidateSize();
    map.fitBounds(bounds, {padding: [30, 30], maxZoom: 5});
    window._observatoryBoundsFitted = true;
  }

  function swatch(color, line) {
    return '<i style="background:' + color + '; width:14px; height:' + (line ? '4px' : '14px') +
      '; display:inline-block; margin-right:6px; vertical-align:middle;' + (color === '#e5f5e0' ? ' border:1px solid #9ca3af;' : '') + '"></i>';
  }
  var legend = L.control({position: 'bottomleft'});
  legend.onAdd = function () {
    var div = L.DomUtil.create('div', 'dora-map-legend');
    div.innerHTML =
      '<b>' + (isEn ? 'Return on capital' : 'Retorno sobre el capital') + '</b><br>' +
      swatch('#e5f5e0') + swatch('#78c679') + swatch('#31a354') + swatch('#006837') +
      fmt(rocMin, 0) + ' &rarr; ' + fmt(rocMax, 0) + ' %<br>' +
      '<b>' + (isEn ? 'Freight to port' : 'Flete al puerto') + '</b><br>' +
      swatch('#ea580c', true) + modeNames.truck + '&nbsp; ' + swatch('#8b5cf6', true) + modeNames.rail + '&nbsp; ' + swatch('#06b6d4', true) + modeNames.barge + '<br>' +
      '⚓ ' + (isEn ? 'export port (ship cost on hover)' : 'puerto de salida (el barco, al pasar el mouse)') + '<br>' +
      '★ ' + (isEn ? 'best return' : 'mejor retorno');
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
    var obsVisible = window._observatoryContainer && window._observatoryContainer.offsetWidth > 0;
    if (obsVisible && !window._observatoryBoundsFitted && window._observatoryBounds && window._observatoryBounds.length > 0) {
      window._observatoryMap.fitBounds(window._observatoryBounds, {padding: [30, 30], maxZoom: 5});
      window._observatoryBoundsFitted = true;
    }
  }
}, 1000);
</script>
"""

LEAFLET_CONTAINER_HTML = """
<div style="margin-bottom: 6px;">
  <small style="opacity: 0.85;"><b>Delimitar lote en el mapa (opcional) / Draw your field (optional).</b> Rectángulo: arrastrar. Polígono: un clic por esquina y, para cerrar, clic de nuevo en el primer punto. El área y la región se cargan solas. / Rectangle: drag. Polygon: click each corner, then click the first point again to close it.</small>
</div>
<div id="dora-map" style="width: 100%; height: 320px; border-radius: 8px; border: 1px solid #ccc; z-index: 1;"></div>
"""


def make_observatory_html(map_items: list[dict], lang: str = "es") -> str:
    escaped_json = json.dumps(map_items).replace("'", "&#39;")
    if lang == "es":
        title_text = "<b>Mapa del Observatorio Regional</b>: retorno sobre el capital y flete al puerto de cada región; la ★ marca la mejor. Pasá el mouse por una ruta o un puerto para ver su costo."
    else:
        title_text = "<b>Regional Observatory Map</b>: each region's return on capital and freight to port; the ★ marks the best. Hover a route or a port to see its cost."
    return f"""
<div style="margin-bottom: 6px;">
  <small style="color: #555;">{title_text}</small>
</div>
<style>
#observatory-map .dora-region-label {{ background: #ffffff; color: #111827; border: 1px solid #9ca3af; font-size: 12px; line-height: 1.35; padding: 3px 6px; box-shadow: 0 1px 3px rgba(0,0,0,.25); }}
#observatory-map .dora-map-legend {{ background: #ffffff; color: #111827; padding: 8px 10px; border-radius: 6px; border: 1px solid #9ca3af; font-size: 12.5px; line-height: 1.6; box-shadow: 0 1px 4px rgba(0,0,0,.25); }}
#observatory-map .dora-port-icon {{ font-size: 13px; line-height: 16px; text-align: center; background: #ffffff; border: 1px solid #6b7280; border-radius: 50%; }}
#observatory-map .leaflet-tooltip, #observatory-map .leaflet-popup-content, #observatory-map .dora-map-legend, #observatory-map .leaflet-tooltip b, #observatory-map .leaflet-popup-content b, #observatory-map .dora-map-legend b {{ color: #111827 !important; }}
#observatory-map .dora-map-legend i {{ margin-right: 2px !important; }}
</style>
<div id="observatory-map" data-lang="{lang}" data-regions='{escaped_json}' style="width: 100%; height: 480px; border-radius: 8px; border: 1px solid #ccc; z-index: 1;"></div>
"""


def get_observatory_ui_data(force_run: bool = False, lang: str = "es"):
    from pathlib import Path
    from dora.observatory import run_observatory

    is_es = (lang == "es")
    latest_file = Path("observatory/latest.json")
    data = None
    if latest_file.is_file() and not force_run:
        try:
            with open(latest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = None
    elif force_run:
        data = run_observatory(save=True)

    if data is None:
        if latest_file.is_file():
            try:
                with open(latest_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
        if data is None:
            banner_md = (
                "⚠️ **Sin snapshot disponible:** No se encontró `observatory/latest.json`. Presione **Actualizar Observatorio** para generarlo."
                if is_es
                else "⚠️ **No snapshot available:** `observatory/latest.json` not found. Press **Refresh** to generate it."
            )
            empty_fig = make_empty_chart("Presione Actualizar Observatorio" if is_es else "Press Refresh")
            return banner_md, "", pd.DataFrame(), empty_fig

    date_str = data.get("date", "2026-10-27")
    commentary = data.get("commentary")
    regions = data.get("regions", {})

    is_es = lang == "es"
    map_items = []
    table_rows = []

    from dora.scenario import load_routes_data

    for key, r in regions.items():
        is_placeholder = bool(r.get("placeholder", False))
        routes_data = load_routes_data(key)
        # Region coords are stored [lon, lat] (GeoJSON order); Leaflet and the
        # route legs use [lat, lon].
        lon, lat = r.get("coords", [0.0, 0.0])
        map_items.append({
            "key": key,
            "name": r.get("name", key),
            "placeholder": is_placeholder,
            "coords": [lat, lon],
            "return_on_capital_pct": r.get("return_on_capital_pct", 0),
            "npv_per_ha": r.get("npv_per_ha", 0),
            "port": r.get("port", ""),
            "distance_km": r.get("distance_km", 0),
            "freight_usd_t": r.get("freight_usd_t", 0),
            "price_source": r.get("price_source", ""),
            "routes": routes_data.get("routes", []),
        })

        crop_mix_dict = r.get("crop_mix", {})
        crop_parts = []
        for c, h in crop_mix_dict.items():
            c_name = CROP_TRANSLATION_TO_ES.get(c, c) if is_es else c
            h_str = format_number_es(h, 1) if is_es else f"{h:.1f}"
            crop_parts.append(f"{c_name}: {h_str} ha")
        crop_mix_str = ", ".join(crop_parts)

        roc_pct = r.get("return_on_capital_pct", 0)
        roc_land_pct = r.get("return_on_capital_and_land_pct", roc_pct)
        land_price = r.get("land_price_usd_ha", 0)

        region_display = r.get("name", key)
        if is_placeholder:
            region_display += " ⚠️ (Datos provisorios)" if is_es else " ⚠️ (Provisional data)"

        table_rows.append({
            "Región / Region": region_display,
            "Cultivos / Crop Mix": crop_mix_str,
            "NPV/ha (USD)": r.get("npv_per_ha", 0),
            "Retorno Capital / ROC (%)": f"{roc_pct:.2f}%",
            "Retorno Cap. + Tierra / ROC & Land (%)": f"{roc_land_pct:.2f}%",
            "Precio Tierra / Land Price (USD/ha)": land_price,
            "Valor Dólar Extra / Extra Dollar Value": r.get("capital_shadow_price", 0),
            "Valor Hectárea Extra / Extra Ha Value (USD/ha)": r.get("land_shadow_price_usd_ha", 0),
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
        annotation_text="Tasa de mercado (4.0%)" if is_es else "Market rate (4.0%)",
        annotation_position="top right",
    )

    fig.update_layout(
        title="Tasa Interna de Oportunidad de Capital por Quincena (% anual)" if is_es else "Fortnightly Capital Opportunity Internal Rate (% annual)",
        xaxis_title="Mes Calendario y Quincena" if is_es else "Calendar Month and Fortnight",
        yaxis_title="Tasa anual (%)" if is_es else "Annual rate (%)",
        hovermode="x unified",
        template="plotly_white",
        height=450,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    if is_es:
        banner_md = f"### 🌐 Referencia Publicada del Observatorio\n" \
                    f"**Fecha de la foto:** `{date_str}`\n"
        if commentary:
            banner_md += f"\n> 📝 **Comentario de Mercado (verificado):**\n> {commentary}\n"
    else:
        banner_md = f"### 🌐 Published Observatory Reference\n" \
                    f"**Snapshot date:** `{date_str}`\n"
        if commentary:
            banner_md += f"\n> 📝 **Market Commentary (verified):**\n> {commentary}\n"

    return banner_md, make_observatory_html(map_items, lang=lang), df, fig


# ==============================================================================
# Gradio App Builder
# ==============================================================================

CUSTOM_CSS = """
#start_tab_container { padding: 4px 6px !important; }
#start_title_md h3 { margin: 2px 0 4px 0 !important; font-size: 1.15rem !important; }
#start_title_md p { margin: 0 0 10px 0 !important; font-size: 0.92rem !important; line-height: 1.35 !important; }

#start_cards_row { gap: 12px !important; margin-bottom: 12px !important; }
.start-card {
    border: 1px solid var(--border-color-primary, #e5e7eb) !important;
    border-radius: 8px !important;
    padding: 12px 14px !important;
    background: var(--background-fill-secondary, #f9fafb) !important;
    display: flex !important;
    flex-direction: column !important;
    justify-content: space-between !important;
}
.start-card h4 { margin: 0 0 4px 0 !important; font-size: 1.05rem !important; color: var(--body-text-color, inherit) !important; }
.start-card p { margin: 0 0 8px 0 !important; font-size: 0.88rem !important; line-height: 1.35 !important; color: var(--body-text-color-subdued, #4b5563) !important; }
.start-card-thumb { margin: 4px 0 8px 0 !important; max-height: 110px !important; }
.start-card-btn { margin-top: auto !important; width: 100% !important; font-weight: 500 !important; }
.start-no-chat { margin-top: auto !important; font-size: 0.85rem !important; color: var(--body-text-color-subdued, #6b7280) !important; }

#model_choice { margin-bottom: 2px !important; }
#model_subline { margin-top: -6px !important; margin-bottom: 8px !important; font-size: 0.85rem !important; }
#model_subline p { margin: 0 !important; color: var(--body-text-color-subdued, #6b7280) !important; font-size: 0.85rem !important; }

#start_scenario_link_row { margin: 8px 0 !important; }
.start-link-btn {
    border: none !important;
    background: transparent !important;
    text-decoration: underline !important;
    font-size: 0.90rem !important;
    cursor: pointer !important;
    padding: 2px 4px !important;
    color: var(--primary-600, #16a34a) !important;
}
.start-steps {
    margin-top: 14px !important;
    padding: 10px 14px !important;
    border-radius: 8px !important;
    border: 1px solid var(--border-color-primary, #e5e7eb) !important;
    background: var(--background-fill-secondary, #f9fafb) !important;
}
.start-steps h3 { margin: 2px 0 6px 0 !important; font-size: 1.00rem !important; color: var(--body-text-color, inherit) !important; }
.start-steps ol { margin: 0 !important; padding-left: 20px !important; }
.start-steps li { margin-bottom: 4px !important; font-size: 0.88rem !important; line-height: 1.35 !important; color: var(--body-text-color, inherit) !important; }

.gradio-container { max-width: 1366px !important; padding: 2px 8px !important; }
#dora_header_row { margin-bottom: 0px !important; padding: 0px !important; }
#dora_header_row h1, #dora_header_row h2 { margin: 0 !important; font-size: 1.15rem !important; line-height: 1.1 !important; }
#dora_header_row p { margin: 0 !important; font-size: 0.80rem !important; }

#how_to_start_accordion { margin-bottom: 3px !important; }
#how_to_start_accordion > .label-wrap { padding: 2px 6px !important; font-size: 0.88rem !important; }
#how_to_start_accordion .block { padding: 2px 4px !important; margin-bottom: 2px !important; }
#how_to_start_accordion p { margin: 1px 0 !important; font-size: 0.80rem !important; line-height: 1.1 !important; }
#how_to_start_accordion button { padding: 2px 6px !important; font-size: 0.82rem !important; height: 28px !important; }

.compact-inputs .block { padding: 3px 5px !important; margin-bottom: 2px !important; }
.compact-inputs label { margin-bottom: 1px !important; font-size: 0.78rem !important; line-height: 1.1 !important; }
.compact-inputs input, .compact-inputs select { height: 26px !important; padding: 2px 4px !important; font-size: 0.82rem !important; }
.compact-inputs .wrap { gap: 2px !important; }
.compact-inputs button { margin-top: 2px !important; height: 32px !important; font-size: 0.88rem !important; padding: 2px 8px !important; }

.plan-card-box .block { padding: 2px 6px !important; margin-bottom: 2px !important; }
.plan-card-box { font-size: 0.80rem !important; line-height: 1.15 !important; }
.plan-card-box h3 { font-size: 0.88rem !important; margin: 1px 0 !important; }
.plan-card-box h4 { font-size: 0.82rem !important; margin: 1px 0 !important; }
.plan-card-box ul { margin: 1px 0 !important; padding-left: 14px !important; }
.plan-card-box li { margin-bottom: 0px !important; }
.plan-card-box hr { margin: 2px 0 !important; }

#chart_rates_full_width { margin-top: 2px !important; margin-bottom: 4px !important; }
.js-plotly-plot { margin-top: 0px !important; }
"""


_NO_STATE = object()


def on_apply_polygon(poly_str: str | dict, lang: str = "es", last_sc: dict | None = _NO_STATE):
    with_state = (last_sc is not _NO_STATE)
    if not poly_str:
        res = (gr.update(), gr.update(), gr.update(), "")
        return (*res, gr.update()) if with_state else res
    if isinstance(poly_str, str):
        if not poly_str.strip():
            res = (gr.update(), gr.update(), gr.update(), "")
            return (*res, gr.update()) if with_state else res
        try:
            data = json.loads(poly_str)
        except Exception as e:
            res = (gr.update(), gr.update(), gr.update(), f"❌ **Error al procesar polígono:** {e}")
            return (*res, gr.update()) if with_state else res
    else:
        data = poly_str
    try:
        res = field_from_map(data)
        area = round(float(res["area_ha"]), 1)
        reg = res.get("region")
        centroid = res.get("centroid", [0, 0])
        lat = round(centroid[1], 4)
        lon = round(centroid[0], 4)

        if reg is None or reg not in REGIONS:
            msg = (
                "⚠️ El campo queda fuera de las regiones que DORA conoce (Balcarce, Pergamino, Iowa, Mato Grosso)."
                if lang == "es"
                else "⚠️ The field is outside the regions DORA knows (Balcarce, Pergamino, Iowa, Mato Grosso)."
            )
            res = (gr.update(), gr.update(), gr.update(), msg)
            return (*res, gr.update()) if with_state else res

        reg_crops = list(REGIONS[reg]["crops"])
        if lang == "es":
            crops_choices = [CROP_TRANSLATION_TO_ES.get(c, c) for c in reg_crops]
        else:
            crops_choices = [CROP_TRANSLATION_TO_EN.get(c, c) for c in reg_crops]
        crops_val = list(crops_choices)

        reg_display_map = {
            "southeast_buenos_aires": "Sudeste de Buenos Aires" if lang == "es" else "Southeast Buenos Aires",
            "pampas_core": "Zona núcleo (Pergamino)" if lang == "es" else "Pampas Core (Pergamino)",
            "iowa": "Iowa, USA",
            "mato_grosso": "Mato Grosso",
        }
        reg_display = reg_display_map.get(reg, reg)
        if lang == "es":
            msg = f"✅ **Campo delimitado:** {area} ha en **{reg_display}** ({lat}, {lon})."
        else:
            msg = f"✅ **Field delimited:** {area} ha in **{reg_display}** ({lat}, {lon})."

        base_res = (gr.update(value=area), gr.update(choices=crops_choices, value=crops_val), gr.update(value=reg), msg)
        if with_state:
            new_sc = dict(last_sc or {})
            new_sc["field_polygon"] = data
            return (*base_res, new_sc)
        return base_res
    except Exception as e:
        res = (gr.update(), gr.update(), gr.update(), f"❌ **Error al procesar polígono:** {e}")
        return (*res, gr.update()) if with_state else res
    else:
        data = poly_str
    try:
        res = field_from_map(data)
        area = round(float(res["area_ha"]), 1)
        reg = res.get("region")
        centroid = res.get("centroid", [0, 0])
        lat = round(centroid[1], 4)
        lon = round(centroid[0], 4)

        if reg is None or reg not in REGIONS:
            msg = (
                "⚠️ El campo queda fuera de las regiones que DORA conoce (Balcarce, Pergamino, Iowa, Mato Grosso)."
                if lang == "es"
                else "⚠️ The field is outside the regions DORA knows (Balcarce, Pergamino, Iowa, Mato Grosso)."
            )
            return gr.update(), gr.update(), gr.update(), msg, gr.update()

        reg_crops = list(REGIONS[reg]["crops"])
        if lang == "es":
            crops_choices = [CROP_TRANSLATION_TO_ES.get(c, c) for c in reg_crops]
        else:
            crops_choices = [CROP_TRANSLATION_TO_EN.get(c, c) for c in reg_crops]
        crops_val = list(crops_choices)

        reg_display_map = {
            "southeast_buenos_aires": "Sudeste de Buenos Aires" if lang == "es" else "Southeast Buenos Aires",
            "pampas_core": "Zona núcleo (Pergamino)" if lang == "es" else "Pampas Core (Pergamino)",
            "iowa": "Iowa, USA",
            "mato_grosso": "Mato Grosso",
        }
        reg_display = reg_display_map.get(reg, reg)

        if lang == "es":
            msg = f"✅ **Campo delimitado:** {area} ha en **{reg_display}** ({lat}, {lon})."
        else:
            msg = f"✅ **Field delimited:** {area} ha in **{reg_display}** ({lat}, {lon})."

        new_sc = dict(last_sc or {})
        new_sc["field_polygon"] = data
        return gr.update(value=area), gr.update(choices=crops_choices, value=crops_val), gr.update(value=reg), msg, new_sc
    except Exception as e:
        return gr.update(), gr.update(), gr.update(), f"❌ **Error al procesar polígono:** {e}", gr.update()


def on_check_satellite(poly_str: str | dict, sc_state: dict | None, lang: str = "es"):
    if not poly_str or (isinstance(poly_str, str) and not poly_str.strip()):
        msg = "⚠️ Dibujá o pegá un polígono en el mapa primero." if lang == "es" else "⚠️ Draw or paste a field polygon on the map first."
        return gr.update(visible=False), msg
    if isinstance(poly_str, str):
        try:
            poly_data = json.loads(poly_str)
        except Exception as e:
            return gr.update(visible=False), f"❌ **Error al procesar polígono:** {e}"
    else:
        poly_data = poly_str

    try:
        from dora.satellite import field_ndvi as _satellite_ndvi
        res = _satellite_ndvi(field=poly_data, scenario=sc_state, lang=lang)
        if res.get("status") in ("no_clear_scene", "no_scene"):
            return gr.update(visible=False), f"⚠️ {res.get('message', '')}"

        scene_date = res.get("scene_date", "")
        med = res.get("ndvi_median")
        norm = res.get("normal")
        norm_med = norm.get("ndvi_median") if isinstance(norm, dict) else None
        anom = res.get("anomaly_pct")
        weak_ha = res.get("weak_ha", 0.0)
        weak_pct = res.get("weak_share_pct", 0.0)

        norm_str = f"{norm_med}" if norm_med is not None else "-"
        anom_str = f"{anom:+,.1f}%" if anom is not None else "-"
        if lang == "es":
            lines = [
                f"### Estado del lote (Sentinel-2)",
                f"- **Imagen del:** {scene_date} (ESA Copernicus, hace {res.get('days_old', 0)} días)",
                f"- **NDVI actual:** {med} (normal histórica: {norm_str}, anomalía: {anom_str})",
                f"- **Hectáreas flojas:** {weak_ha} ha ({weak_pct} % del lote)",
                f"- **Despejado:** {res.get('clear_share_pct')}%",
            ]
        else:
            lines = [
                f"### Field Status (Sentinel-2)",
                f"- **Image date:** {scene_date} (ESA Copernicus, {res.get('days_old', 0)} days ago)",
                f"- **Current NDVI:** {med} (historical normal: {norm_str}, anomaly: {anom_str})",
                f"- **Weak canopy:** {weak_ha} ha ({weak_pct}% of field)",
                f"- **Clear:** {res.get('clear_share_pct')}%",
            ]
        overlay_path = res.get("overlay_path")
        img_update = gr.update(value=overlay_path, visible=bool(overlay_path and os.path.isfile(overlay_path)))
        return img_update, "\n".join(lines)
    except Exception as e:
        return gr.update(visible=False), f"❌ **Error consultando satélite:** {e}"


def on_region_change(reg: str, lang: str = "es"):
    norm_r = normalize_region(reg)
    reg_crops = list(REGIONS.get(norm_r, REGIONS["southeast_buenos_aires"])["crops"])
    if lang == "es":
        crops_choices = [CROP_TRANSLATION_TO_ES.get(c, c) for c in reg_crops]
    else:
        crops_choices = [CROP_TRANSLATION_TO_EN.get(c, c) for c in reg_crops]
    crops_upd = gr.update(choices=crops_choices, value=crops_choices)

    base_start = REGIONS.get(norm_r, {}).get("season_start", "2026-05")
    by, bm = [int(x) for x in base_start.split("-")]
    b_str = f"1/{bm}/{by}"
    btn_lbl = f"Inicio de campaña ({b_str})" if lang == "es" else f"Season start ({b_str})"
    btn_upd = gr.update(value=btn_lbl)

    has_ls = norm_r in ("southeast_buenos_aires", "pampas_core")
    ls_upd = gr.update(visible=has_ls)
    return crops_upd, btn_upd, ls_upd


def on_click_base_season(reg: str):
    norm_r = normalize_region(reg)
    base_start = REGIONS.get(norm_r, {}).get("season_start", "2026-05")
    by, bm = [int(x) for x in base_start.split("-")]
    return f"01/{bm:02d}/{by}"


try:
    from eval.run_eval import PROVIDERS
    _BASETEN_DEFAULTS = PROVIDERS.get(
        "baseten",
        ("BASETEN_API_BASE", "BASETEN_API_KEY", "BASETEN_MODEL", "https://inference.baseten.co/v1", "meta-models/muse-spark-open-1026"),
    )
except Exception:
    _BASETEN_DEFAULTS = (
        "BASETEN_API_BASE", "BASETEN_API_KEY", "BASETEN_MODEL", "https://inference.baseten.co/v1", "meta-models/muse-spark-open-1026"
    )

BASETEN_SUPPORTS_IMAGES = True


def make_client(provider: str = "meta"):
    """Create an OpenAI-compatible client for the specified provider."""
    norm = "baseten" if provider in ("baseten", "Muse Spark Open (Baseten)") else "meta"
    if norm == "baseten":
        from openai import OpenAI
        base_var, key_var, _, base_default, _ = _BASETEN_DEFAULTS
        base_url = os.environ.get(base_var) or base_default
        api_key = os.environ.get(key_var, "")
        return OpenAI(base_url=base_url, api_key=api_key, max_retries=6)
    else:
        from dora.agent import default_client
        return default_client()


def model_for(provider: str = "meta") -> str:
    """Return model name for the specified provider."""
    norm = "baseten" if provider in ("baseten", "Muse Spark Open (Baseten)") else "meta"
    if norm == "baseten":
        _, _, model_var, _, model_default = _BASETEN_DEFAULTS
        return os.environ.get(model_var) or model_default
    else:
        return os.environ.get("DORA_MODEL", "")


def on_model_choice_change(choice: str, lang: str = "es") -> tuple[list[dict], None]:
    """Switch active model: clear conversation history and reset agent state."""
    is_open = "Open" in str(choice) or "baseten" in str(choice).lower()
    if is_open:
        msg = ("Ahora conversás con Muse Spark Open."
               if lang == "es" else "You are now talking to Muse Spark Open.")
    else:
        msg = ("Ahora conversás con Muse Spark 1.3."
               if lang == "es" else "You are now talking to Muse Spark 1.3.")
    return [{"role": "assistant", "content": msg}], None


PENDING_MSG_ES = "⏳ DORA está armando el escenario y calculando…"
PENDING_MSG_EN = "⏳ DORA is building the scenario and computing…"


def show_pending(
    user_text: str | None,
    files: list | None,
    audio: str | None,
    history: list,
    lang: str = "es",
) -> list:
    """Return history plus the user message and the pending line.

    If there is nothing to send, return history unchanged.
    """
    clean_text = (user_text or "").strip()
    raw_files = [f.name if hasattr(f, "name") else str(f) for f in files] if files else []
    xlsx_paths = [p for p in raw_files if p.lower().endswith((".xlsx", ".xlsm", ".csv"))]
    image_paths = [p for p in raw_files if p not in xlsx_paths]
    audio_path = audio if audio else None

    if not clean_text and not raw_files and not audio_path:
        return list(history or [])

    user_display = clean_text
    if xlsx_paths:
        thumbs = " ".join(f"📊 *[{os.path.basename(p)}]({p})*" for p in xlsx_paths)
        user_display = f"{user_display}\n\n{thumbs}".strip()
    if image_paths:
        thumbs = " ".join(f"📷 *[{os.path.basename(p)}]({p})*" for p in image_paths)
        user_display = f"{user_display}\n\n{thumbs}".strip()
    if audio_path:
        voice_label = "🎤 nota de voz" if lang == "es" else "🎤 voice note"
        user_display = f"{user_display}\n\n{voice_label}".strip()

    pending_msg = PENDING_MSG_ES if lang == "es" else PENDING_MSG_EN
    new_history = list(history or []) + [
        {"role": "user", "content": user_display},
        {"role": "assistant", "content": pending_msg},
    ]
    return new_history


def respond(
    user_text: str,
    files: list | None,
    audio: str | None,
    history: list,
    agent_instance: Any,
    lang: str,
    screen_scenario: dict | None,
    provider: str = "meta",
):
    global _daily_chat_counter, _daily_chat_date

    # SPEC-33b Section 1: At its start, if the last two history items are that pending pair, remove them
    if history and len(history) >= 2:
        last_item = history[-1]
        second_last = history[-2]
        last_content = last_item.get("content", "") if isinstance(last_item, dict) else getattr(last_item, "content", "")
        last_role = last_item.get("role") if isinstance(last_item, dict) else getattr(last_item, "role", None)
        second_role = second_last.get("role") if isinstance(second_last, dict) else getattr(second_last, "role", None)
        if (
            last_role == "assistant"
            and any(p in str(last_content) for p in (PENDING_MSG_ES, PENDING_MSG_EN))
            and second_role == "user"
        ):
            history = list(history[:-2])

    today_str = datetime.date.today().isoformat()
    if _daily_chat_date != today_str:
        _daily_chat_date = today_str
        _daily_chat_counter = 0

    t = STRINGS.get(lang, STRINGS["es"])

    clean_text = (user_text or "").strip()
    if not clean_text and not files and not audio:
        return "", None, None, history, agent_instance

    t0 = time.time()
    norm_provider = "baseten" if provider in ("baseten", "Muse Spark Open (Baseten)") else "meta"
    raw_files = [f.name if hasattr(f, "name") else str(f) for f in files] if files else []
    xlsx_paths = [p for p in raw_files if p.lower().endswith((".xlsx", ".xlsm", ".csv"))]
    image_paths = [p for p in raw_files if p not in xlsx_paths]
    audio_path = audio if audio else None

    def _log_chat(rounds: int, tools_str: str, verified: bool):
        elapsed = time.time() - t0
        model_name = model_for(norm_provider)
        print(f"[chat] provider={norm_provider} model={model_name} seconds={elapsed:.1f} rounds={rounds} tools={tools_str} verified={verified} images={len(image_paths)} audio={bool(audio_path)}")

    if _daily_chat_counter >= DAILY_CHAT_LIMIT:
        history += [{"role": "user", "content": user_text}, {"role": "assistant", "content": t["chat_limit_reached"]}]
        return "", None, None, history, agent_instance

    _daily_chat_counter += 1

    # SPEC-42 Section 5: If an Excel file is uploaded, call read_plan_xlsx directly
    if xlsx_paths:
        from dora.spreadsheet import read_plan_xlsx
        from pathlib import Path
        p_xlsx = xlsx_paths[0]
        raw_bytes = Path(p_xlsx).read_bytes()
        read_res = read_plan_xlsx(raw_bytes, lang=lang)
        if "error" in read_res:
            err_msg = f"❌ {read_res.get('message', read_res['error'])}"
            user_display = clean_text or f"📊 *[{os.path.basename(p_xlsx)}]({p_xlsx})*"
            history += [{"role": "user", "content": user_display}, {"role": "assistant", "content": err_msg}]
            _log_chat(rounds=0, tools_str="read_plan_xlsx_error", verified=False)
            return "", None, None, history, agent_instance

        # Call agent with read_res as context
        if agent_instance is None:
            from dora.agent import Agent
            agent_instance = Agent(client=make_client(norm_provider), model=model_for(norm_provider))

        agent_prompt = (
            f"El productor envió la planilla modificada. Resultado de read_plan_xlsx: {json.dumps(read_res)}. "
            f"Explicá qué cambió."
            if lang == "es"
            else f"The farmer uploaded a modified plan spreadsheet. Result of read_plan_xlsx: {json.dumps(read_res)}. "
            f"Explain what changed."
        )
        if clean_text:
            agent_prompt = f"{clean_text}\n\n[{agent_prompt}]"

        reply = agent_instance.ask(agent_prompt, images=image_paths, audio=audio_path, screen_scenario=screen_scenario)
        badge = t["chat_badge_verified"] if reply.verified else t["chat_badge_unverified"].format(unsupported="")
        download_lbl = "Descargar nueva planilla del plan (.xlsx)" if lang == "es" else "Download new plan spreadsheet (.xlsx)"
        download_md = f"\n\n📥 **[{download_lbl}]({read_res['file']})**"
        user_display = clean_text or f"📊 *[{os.path.basename(p_xlsx)}]({p_xlsx})*"
        _log_chat(rounds=1, tools_str="read_plan_xlsx", verified=reply.verified)
        history += [{"role": "user", "content": user_display}, {"role": "assistant", "content": reply.text + download_md + f"\n\n{badge}"}]
        return "", None, None, history, agent_instance

    # SPEC-33 Section 2: If photos are not supported on Baseten and message has images, reply without calling model
    if norm_provider == "baseten" and not BASETEN_SUPPORTS_IMAGES and image_paths:
        _daily_chat_counter -= 1
        msg = ("Muse Spark Open no lee fotos en esta versión; elegí Muse Spark 1.3 para mandar facturas."
               if lang == "es" else "Muse Spark Open does not read photos in this version; choose Muse Spark 1.3 to send invoices.")
        user_display = clean_text
        if image_paths:
            thumbs = " ".join(f"📷 *[{os.path.basename(p)}]({p})*" for p in image_paths)
            user_display = f"{user_display}\n\n{thumbs}".strip()
        history += [{"role": "user", "content": user_display}, {"role": "assistant", "content": msg}]
        _log_chat(rounds=0, tools_str="none", verified=True)
        return "", None, None, history, agent_instance

    if agent_instance is None:
        from dora.agent import Agent
        agent_instance = Agent(client=make_client(norm_provider), model=model_for(norm_provider))

    n_texts = len(agent_instance.user_texts)
    prev_requests = getattr(agent_instance, "usage", {}).get("requests", 0) if agent_instance else 0
    try:
        reply = agent_instance.ask(clean_text, images=image_paths, audio=audio_path, screen_scenario=screen_scenario)
    except Exception:
        _daily_chat_counter -= 1
        curr_requests = getattr(agent_instance, "usage", {}).get("requests", 0) if agent_instance else 0
        rounds = max(0, curr_requests - prev_requests)
        _log_chat(rounds=rounds, tools_str="none", verified=False)
        msg = ("⚠️ No pude hablar con el modelo ahora. Probá de nuevo en un minuto; la pestaña Escenario funciona sin él."
               if lang == "es" else "⚠️ Could not reach the model right now. Try again in a minute; the Scenario tab works without it.")
        history += [{"role": "user", "content": clean_text}, {"role": "assistant", "content": msg}]
        return "", None, None, history, agent_instance

    curr_requests = getattr(agent_instance, "usage", {}).get("requests", 0) if agent_instance else 0
    rounds = max(0, curr_requests - prev_requests)
    if rounds == 0:
        rep_usage = getattr(reply, "usage", {})
        if isinstance(rep_usage, dict):
            rounds = rep_usage.get("requests", 0)
        if rounds == 0:
            rounds = 1

    tools_called = [c.get("tool") for c in getattr(reply, "tool_calls", []) if isinstance(c, dict) and c.get("tool")]
    tools_str = ",".join(tools_called) if tools_called else "none"
    verified = bool(getattr(reply, "verified", False))

    heard = agent_instance.user_texts[n_texts] if audio_path and len(agent_instance.user_texts) > n_texts else ""

    user_display = clean_text
    if image_paths:
        thumbs = " ".join(f"📷 *[{os.path.basename(p)}]({p})*" for p in image_paths)
        user_display = f"{user_display}\n\n{thumbs}".strip()
    if audio_path:
        note = f"🎙️ *{heard}*" if heard else "🎙️ *[Nota de voz]*"
        user_display = f"{user_display}\n\n{note}".strip()

    if reply.verified:
        badge = t["chat_badge_verified"]
    else:
        unsupp = ", ".join(u.text for u in reply.unsupported)
        badge = t["chat_badge_unverified"].format(unsupported=unsupp)

    reconciliation_md = ""
    for tc in reply.tool_calls:
        if tc.get("tool") == "record_document":
            try:
                doc_res = None
                for r_str in reversed(getattr(agent_instance, "tool_results", [])):
                    try:
                        parsed_r = json.loads(r_str)
                        if "proposals" in parsed_r and "completeness" in parsed_r:
                            doc_res = parsed_r
                            break
                    except Exception:
                        continue
                if doc_res:
                    es = lang == "es"
                    item_es = {
                        "fertilizer": "fertilizante", "seed": "semilla", "crop_protection": "agroquímicos",
                        "agrochemicals": "agroquímicos", "field_operations": "labores", "labor": "labores",
                        "freight": "flete", "rent": "arrendamiento", "overhead_owned": "estructura", "tax": "impuesto"
                    }
                    rec_lines = ["\n\n### 📑 " + ("Conciliación de Documento del Productor:" if es else "Farmer's document check:")]

                    # 1. Renglones / Lines
                    lines_data = doc_res.get("lines") or doc_res.get("items") or []
                    if lines_data:
                        rec_lines.append("\n**" + ("Renglones:" if es else "Lines:") + "**")
                        rec_lines.append("| Renglón | Cultivo | Rubro | USD/ha |" if es else "| Line | Crop | Item | USD/ha |")
                        rec_lines.append("|---|---|---|---|")
                        for l in lines_data:
                            c_display = CROP_TRANSLATION_TO_ES.get(l.get("crop"), l.get("crop")) if (es and l.get("crop")) else (l.get("crop") or "-")
                            i_display = item_es.get(l.get("cost_item"), l.get("cost_item")) if (es and l.get("cost_item")) else (l.get("cost_item") or "-")
                            exc = l.get("excluded")
                            if exc:
                                if es:
                                    if exc == "tax":
                                        val_str = "IVA, no es costo"
                                    elif exc == "unknown item":
                                        val_str = "rubro no reconocido"
                                    elif exc == "crop not in plan":
                                        val_str = "cultivo no está en el plan"
                                    else:
                                        val_str = exc
                                else:
                                    if exc == "tax":
                                        val_str = "tax, not a cost"
                                    elif exc == "unknown item":
                                        val_str = "unrecognized item"
                                    elif exc == "crop not in plan":
                                        val_str = "crop not in plan"
                                    else:
                                        val_str = exc
                            elif l.get("usd_ha") is not None:
                                val_str = f"{l['usd_ha']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if es else f"{l['usd_ha']:,.2f}"
                            else:
                                val_str = "-"
                            rec_lines.append(f"| {l.get('concept', '')} | {c_display} | {i_display} | {val_str} |")

                    # 2. Comparación con la zona / Compared with the zone
                    proposals = doc_res.get("proposals", [])
                    valid_proposals = []
                    for prop in proposals:
                        crop_val = prop.get("crop")
                        ref_val = prop.get("default_usd_ha")
                        is_unknown_crop = not crop_val or str(crop_val).strip().lower() in ("unknown", "desconocido", "none")
                        is_none_ref = ref_val is None or str(ref_val).strip().lower() in ("none", "")
                        if not is_unknown_crop and not is_none_ref:
                            valid_proposals.append(prop)

                    if valid_proposals:
                        rec_lines.append("\n**" + ("Comparación con la zona:" if es else "Compared with the zone:") + "**")
                        rec_lines.append("| Cultivo | Rubro | Factura | Zona | Diferencia | Se usa |" if es else "| Crop | Item | Invoice | Zone | Difference | Used |")
                        rec_lines.append("|---|---|---|---|---|---|")
                        for prop in valid_proposals:
                            c_display = CROP_TRANSLATION_TO_ES.get(prop.get("crop"), prop.get("crop")) if (es and prop.get("crop")) else (prop.get("crop") or "-")
                            i_display = item_es.get(prop.get("item"), prop.get("item")) if (es and prop.get("item")) else (prop.get("item") or "-")
                            inv_str = f"{prop['proposed_usd_ha']} USD/ha"
                            def_str = f"{prop['default_usd_ha']} USD/ha" if prop.get("default_usd_ha") is not None else "-"
                            dev_pct = prop.get("deviation_pct", 0.0)
                            diff_str = f"{dev_pct:+.1f} %" if prop.get("default_usd_ha") is not None else "-"

                            if prop.get("apply"):
                                if prop.get("reason") == "confirmed by the farmer":
                                    se_usa = f"sí, confirmado por vos ({dev_pct:+.0f} % contra la zona)" if es else f"yes, confirmed by you ({dev_pct:+.0f} % vs zone)"
                                else:
                                    se_usa = "sí" if es else "yes"
                            else:
                                r = prop.get("reason")
                                if es:
                                    if r == "deviation over 50%":
                                        r_es = "más de 50 % de diferencia"
                                    elif r == "partial crop protection":
                                        r_es = "es solo parte de los agroquímicos"
                                    elif r in ("missing crop", "crop missing") or not prop.get("crop"):
                                        r_es = "falta el cultivo"
                                    else:
                                        r_es = r or "no aplicado"
                                    se_usa = f"no: {r_es}"
                                else:
                                    if r == "deviation over 50%":
                                        r_en = "deviation over 50%"
                                    elif r == "partial crop protection":
                                        r_en = "only part of crop protection"
                                    elif r in ("missing crop", "crop missing") or not prop.get("crop"):
                                        r_en = "crop missing"
                                    else:
                                        r_en = r or "not applied"
                                    se_usa = f"no: {r_en}"
                            rec_lines.append(f"| {c_display} | {i_display} | {inv_str} | {def_str} | {diff_str} | {se_usa} |")
                    else:
                        no_cov_line = (
                            "Falta saber para qué cultivo y cuántas hectáreas cubre la factura para compararla con la zona."
                            if es else
                            "To compare it with the zone I need the crop and the hectares the invoice covers."
                        )
                        rec_lines.append(f"\n{no_cov_line}")

                    # 3. Antes y después / Before and after
                    pb = doc_res.get("plan_before")
                    pa = doc_res.get("plan_after")
                    if pb:
                        rec_lines.append("\n**" + ("Antes y después:" if es else "Before and after:") + "**")
                        rec_lines.append("| | Antes | Después |" if es else "| | Before | After |")
                        rec_lines.append("|---|---|---|")

                        van_b = f"{pb['npv_usd']:,.0f}".replace(",", ".") if es else f"{pb['npv_usd']:,.0f}"
                        van_a = (f"{pa['npv_usd']:,.0f}".replace(",", ".") if es else f"{pa['npv_usd']:,.0f}") if pa else "-"
                        rec_lines.append(f"| VAN (USD) | {van_b} | {van_a} |" if es else f"| NPV (USD) | {van_b} | {van_a} |")

                        all_crops_plan = []
                        for c in list(pb.get("hectares", {}).keys()) + (list(pa.get("hectares", {}).keys()) if pa else []):
                            if c not in all_crops_plan:
                                all_crops_plan.append(c)

                        for c in all_crops_plan:
                            c_lbl = CROP_TRANSLATION_TO_ES.get(c, c) if es else c
                            ha_b = pb.get("hectares", {}).get(c, 0.0)
                            ha_a = pa.get("hectares", {}).get(c, 0.0) if pa else "-"
                            ha_b_str = f"{ha_b:.1f}".replace(".", ",") if es else f"{ha_b:.1f}"
                            ha_a_str = (f"{ha_a:.1f}".replace(".", ",") if isinstance(ha_a, (int, float)) else str(ha_a)) if es else (f"{ha_a:.1f}" if isinstance(ha_a, (int, float)) else str(ha_a))
                            rec_lines.append(f"| Hectáreas {c_lbl} | {ha_b_str} | {ha_a_str} |" if es else f"| Hectares {c_lbl} | {ha_b_str} | {ha_a_str} |")

                        cred_b = f"{pb.get('max_credit_usd', 0):,.0f}".replace(",", ".") if es else f"{pb.get('max_credit_usd', 0):,.0f}"
                        cred_a = (f"{pa.get('max_credit_usd', 0):,.0f}".replace(",", ".") if es else f"{pa.get('max_credit_usd', 0):,.0f}") if pa else "-"
                        rec_lines.append(f"| Crédito máx. (USD) | {cred_b} | {cred_a} |" if es else f"| Max credit (USD) | {cred_b} | {cred_a} |")

                        if "npv_change_usd" in doc_res:
                            npv_diff = doc_res["npv_change_usd"]
                            diff_line = (f"\nDiferencia de VAN: {npv_diff:+,.0f} USD".replace(",", "X").replace(".", ",").replace("X", ".")
                                         if es else
                                         f"\nNPV difference: {npv_diff:+,.0f} USD")
                            rec_lines.append(diff_line)

                    if doc_res.get("fx_conversion"):
                        fx = doc_res["fx_conversion"]
                        rec_lines.append(f"\n*Conversión ARS/USD BCRA:* {fx.get('rate')} ({fx.get('date')})")
                    reconciliation_md = "\n".join(rec_lines)
            except Exception:
                pass

    tool_calls_text = ""
    if reply.tool_calls:
        summary_text = t["tool_calls_summary"].format(n=len(reply.tool_calls))
        call_items = []
        for c in reply.tool_calls:
            call_items.append(f"- **{c.get('tool')}**: `{c.get('arguments')}`")
        tool_calls_text = f"\n\n<details><summary>{summary_text}</summary>\n\n" + "\n".join(call_items) + "\n</details>"

    bot_message = f"{badge}\n\n{reply.text}{reconciliation_md}{tool_calls_text}"
    history += [{"role": "user", "content": user_display}, {"role": "assistant", "content": bot_message}]

    if any(tc.get("tool") in ("assess_field_image", "field_ndvi") for tc in reply.tool_calls):
        for r_str in reversed(getattr(agent_instance, "tool_results", [])):
            try:
                overlay = json.loads(r_str).get("overlay_path")
            except Exception:
                overlay = None
            if overlay and os.path.isfile(overlay):
                history.append({"role": "assistant", "content": {"path": overlay}})
                break
    _log_chat(rounds=rounds, tools_str=tools_str, verified=verified)
    return "", None, None, history, agent_instance


# ==============================================================================
# SPEC-32 Start Here Tab Handlers
# ==============================================================================

CARD1_PROMPT_ES = "Tengo 500 ha en Balcarce y 50.000 USD de capital. ¿Qué me conviene sembrar? Preguntame lo que necesites."
CARD1_PROMPT_EN = "I have 500 ha in Balcarce and 50,000 USD of capital. What should I sow? Ask me whatever you need."

CARD2_PROMPT_ES = "Te mando la factura del fertilizante del trigo. Cubre 100 ha de trigo. Tengo 500 ha en Balcarce y 50.000 USD. ¿Cómo cambia el plan con este costo?"
CARD2_PROMPT_EN = "Here is the invoice for the wheat fertilizer. It covers 100 ha of wheat. I have 500 ha in Balcarce and 50,000 USD. How does the plan change with this cost?"

SAMPLE_INVOICE_PATH = "assets/examples/factura-ejemplo.png"


def on_switch_to_chat():
    return gr.update(selected="tab_chat")


def on_start_card1(history: list | None = None, agent_instance: Any = None, lang: str = "es", screen_scenario: dict | None = None):
    text = CARD1_PROMPT_ES if lang == "es" else CARD1_PROMPT_EN
    return respond(text, None, None, list(history or []), agent_instance, lang, screen_scenario)


def on_start_card2(history: list | None = None, agent_instance: Any = None, lang: str = "es", screen_scenario: dict | None = None):
    text = CARD2_PROMPT_ES if lang == "es" else CARD2_PROMPT_EN
    files = [SAMPLE_INVOICE_PATH] if os.path.isfile(SAMPLE_INVOICE_PATH) else []
    return respond(text, files, None, list(history or []), agent_instance, lang, screen_scenario)


def on_start_card1_pending(history: list | None = None, lang: str = "es"):
    text = CARD1_PROMPT_ES if lang == "es" else CARD1_PROMPT_EN
    return show_pending(text, None, None, list(history or []), lang)


def on_start_card2_pending(history: list | None = None, lang: str = "es"):
    text = CARD2_PROMPT_ES if lang == "es" else CARD2_PROMPT_EN
    files = [SAMPLE_INVOICE_PATH] if os.path.isfile(SAMPLE_INVOICE_PATH) else []
    return show_pending(text, files, None, list(history or []), lang)


def on_start_card3():
    return gr.update(selected="tab_regions")


def on_start_scenario_link():
    return gr.update(selected="tab_scenario")

def build_app(api_key: str | None = None) -> gr.Blocks:
    """Construct the Gradio interface."""
    resolved_api_key = api_key if api_key is not None else os.environ.get("DORA_API_KEY", "")
    has_chat = bool(resolved_api_key)
    has_baseten = bool(os.environ.get("BASETEN_API_KEY"))

    theme = gr.themes.Soft(primary_hue="green")

    with gr.Blocks(title="DORA Farm Agent") as app:
        app.theme = theme
        app.head = LEAFLET_HEAD + f"\n<style>\n{CUSTOM_CSS}\n</style>"
        lang_state = gr.State("es")
        saved_runs_state = gr.State([])
        current_run_state = gr.State({})
        last_scenario_state = gr.State({})

        with gr.Row(elem_id="dora_header_row"):
            with gr.Column(scale=9):
                md_title = gr.Markdown("## 🌾 DORA — Asistente de Planificación Agrícola · *Plan óptimo y costo de oportunidad de los recursos*")
                md_subtitle = gr.Markdown("")
            with gr.Column(scale=3):
                lang_radio = gr.Radio(
                    choices=["Español", "English"],
                    value="Español",
                    label="Idioma / Language",
                )

        initial_tab = os.environ.get("DORA_INITIAL_TAB", "tab_start")
        with gr.Tabs(selected=initial_tab) as tabs:
            # ------------------------------------------------------------------
            # TAB 1: EMPEZÁ ACÁ / START HERE
            # ------------------------------------------------------------------
            with gr.TabItem("🚀 Empezá acá / Start here", id="tab_start", elem_id="tab_start") as tab_start:
                with gr.Column(elem_id="start_tab_container"):
                    start_title_md = gr.Markdown(
                        "### DORA planifica tu campaña agrícola\n"
                        "Vos le contás tu campo; un motor matemático calcula el plan y cada número se verifica antes de mostrártelo.",
                        elem_id="start_title_md"
                    )

                    with gr.Row(equal_height=True, elem_id="start_cards_row"):
                        # Card 1: Plan your season
                        with gr.Column(min_width=260, elem_classes=["start-card"]):
                            card1_title_md = gr.Markdown("#### 🌾 Planificá tu campaña")
                            card1_desc_md = gr.Markdown("DORA te pregunta de a una cosa por vez, empezando por la que más cambia el plan.")
                            if has_chat:
                                btn_card1 = gr.Button("Probar", variant="primary", elem_classes=["start-card-btn"])
                                no_chat_msg1 = None
                            else:
                                btn_card1 = None
                                no_chat_msg1 = gr.Markdown("*El chat necesita la clave del modelo.*", elem_classes=["start-no-chat"])

                        # Card 2: Send invoice
                        with gr.Column(min_width=260, elem_classes=["start-card"]):
                            card2_title_md = gr.Markdown("#### 📑 Mandale una factura")
                            card2_desc_md = gr.Markdown("DORA lee la foto renglón por renglón y recalcula el plan con esos costos.")
                            card2_img = gr.Image(
                                value=SAMPLE_INVOICE_PATH if os.path.isfile(SAMPLE_INVOICE_PATH) else None,
                                show_label=False,
                                interactive=False,
                                height=110,
                                elem_classes=["start-card-thumb"]
                            )
                            if has_chat:
                                btn_card2 = gr.Button("Probar", variant="primary", elem_classes=["start-card-btn"])
                                no_chat_msg2 = None
                            else:
                                btn_card2 = None
                                no_chat_msg2 = gr.Markdown("*El chat necesita la clave del modelo.*", elem_classes=["start-no-chat"])

                        # Card 3: Compare regions
                        with gr.Column(min_width=260, elem_classes=["start-card"]):
                            card3_title_md = gr.Markdown("#### 🌐 Compará regiones")
                            card3_desc_md = gr.Markdown("Balcarce, Pergamino, Iowa y Mato Grosso en un mapa, con su retorno y su flete al puerto.")
                            btn_card3 = gr.Button("Ver regiones", variant="secondary", elem_classes=["start-card-btn"])

                    with gr.Row(elem_id="start_scenario_link_row"):
                        btn_scenario_link = gr.Button(
                            "¿Querés tocar los números vos? Abrí la pestaña Escenario.",
                            variant="secondary",
                            size="sm",
                            elem_classes=["start-link-btn"]
                        )

                    start_steps_md = gr.Markdown(
                        "### ¿Cómo usar DORA?\n"
                        "1. **Contale tu campo:** hectáreas, región, plata propia, crédito.\n"
                        "2. **Si falta algo que cambia el plan, DORA te pregunta;** si no sabés, dice qué va a suponer.\n"
                        "3. **Podés escribir, mandar una nota de voz o una foto de una factura.**\n"
                        "4. **Cada respuesta dice si está verificada:** todos los números salen del motor.",
                        elem_id="start_steps_md",
                        elem_classes=["start-steps"]
                    )

            # ------------------------------------------------------------------
            # TAB 2: CHAT CON DORA (Only included if DORA_API_KEY is present)
            # ------------------------------------------------------------------
            if has_chat:
                with gr.TabItem("💬 Chat con DORA / Chat", id="tab_chat", elem_id="tab_chat"):
                    initial_chat_msg = "Contame tu campaña: hectáreas, cultivos, plata y crédito. Podés escribir o mandar un audio."
                    chatbot = gr.Chatbot(
                        value=[{"role": "assistant", "content": initial_chat_msg}],
                        height=460,
                        label="DORA Farm Agent"
                    )

                    if has_baseten:
                        model_choice = gr.Radio(
                            choices=["Muse Spark 1.3 (Meta API)", "Muse Spark Open (Baseten)"],
                            value="Muse Spark 1.3 (Meta API)",
                            label="Modelo",
                            elem_id="model_choice",
                        )
                        model_subline = gr.Markdown(
                            "*Las dos versiones usan el mismo motor y el mismo verificador.*",
                            elem_id="model_subline",
                        )
                    else:
                        model_choice = None
                        model_subline = None

                    with gr.Row(equal_height=True):
                        chat_msg = gr.Textbox(
                            placeholder="Consultá sobre tu plan de siembra o enviá facturas/fotos...",
                            show_label=False,
                            label="Tu mensaje",
                            lines=1,
                            max_lines=6,
                            scale=9,
                        )
                        chat_send = gr.Button("Enviar", variant="primary", scale=2, min_width=90)
                    with gr.Accordion("📎 Adjuntar fotos o nota de voz", open=False) as chat_attach:
                        with gr.Row():
                            chat_files = gr.File(
                                label="Fotos de facturas o planillas Excel (.xlsx)",
                                file_count="multiple",
                                file_types=["image", ".xlsx", ".xlsm", ".csv"],
                                height=120,
                                scale=6,
                            )
                            chat_audio = gr.Audio(
                                label="Nota de voz (grabación o archivo)",
                                sources=["microphone", "upload"],
                                type="filepath",
                                scale=6,
                            )

                    agent_state = gr.State(None)
                    pending_inputs_state = gr.State(None)

                    if has_baseten and model_choice is not None:
                        model_choice.change(
                            fn=on_model_choice_change,
                            inputs=[model_choice, lang_state],
                            outputs=[chatbot, agent_state],
                        )

                    def on_chat_step1(user_text, files, audio, history, lang):
                        clean_text = (user_text or "").strip()
                        image_paths = [f.name if hasattr(f, "name") else str(f) for f in files] if files else []
                        audio_path = audio if audio else None
                        if not clean_text and not image_paths and not audio_path:
                            return user_text, files, audio, history, None
                        new_history = show_pending(user_text, files, audio, history, lang)
                        return "", None, None, new_history, (user_text, files, audio)

                    def on_chat_step2(pending_state, user_text, files, audio, history, agent_instance, lang, screen_scenario, provider="meta"):
                        if pending_state is not None:
                            p_text, p_files, p_audio = pending_state
                        else:
                            p_text, p_files, p_audio = user_text, files, audio
                        res = respond(p_text, p_files, p_audio, history, agent_instance, lang, screen_scenario, provider)
                        return res[0], res[1], res[2], res[3], res[4], None

                    step1_inputs = [chat_msg, chat_files, chat_audio, chatbot, lang_state]
                    step1_outputs = [chat_msg, chat_files, chat_audio, chatbot, pending_inputs_state]

                    step2_inputs = [pending_inputs_state, chat_msg, chat_files, chat_audio, chatbot, agent_state, lang_state, last_scenario_state]
                    if model_choice is not None:
                        step2_inputs.append(model_choice)
                    step2_outputs = [chat_msg, chat_files, chat_audio, chatbot, agent_state, pending_inputs_state]

                    chat_send.click(
                        fn=on_chat_step1,
                        inputs=step1_inputs,
                        outputs=step1_outputs,
                        queue=False,
                    ).then(
                        fn=on_chat_step2,
                        inputs=step2_inputs,
                        outputs=step2_outputs,
                    )
                    chat_msg.submit(
                        fn=on_chat_step1,
                        inputs=step1_inputs,
                        outputs=step1_outputs,
                        queue=False,
                    ).then(
                        fn=on_chat_step2,
                        inputs=step2_inputs,
                        outputs=step2_outputs,
                    )
            else:
                chatbot = None
                chat_msg = None
                chat_files = None
                chat_audio = None
                chat_attach = None
                chat_send = None
                agent_state = None
                model_choice = None
                model_subline = None

            # ------------------------------------------------------------------
            # TAB 3: SCENARIO
            # ------------------------------------------------------------------
            with gr.TabItem("📊 Escenario / Scenario", id="tab_scenario", elem_id="tab_scenario"):
                with gr.Accordion("¿Cómo empiezo? / How do I start?", open=True, elem_id="how_to_start_accordion") as how_to_start_accordion:
                    md_how_to_start = gr.Markdown(
                        """**1.** Elegí un ejemplo o delimitá tu lote. Si tenés hacienda, marcá cría o invernada. &nbsp;&bull;&nbsp; """
                        """**2.** Apretá **Calcular Plan Óptimo** (o clic en un ejemplo). &nbsp;&bull;&nbsp; """
                        """**3.** Mirá qué falta y qué sobra en los gráficos."""
                    )
                    with gr.Row():
                        with gr.Column(scale=3, min_width=100):
                            ex_btn_rationed = gr.Button("Capital restringido", variant="secondary", size="sm")
                            ex_desc_rationed = gr.Markdown("*USD 50k para 500 ha: falta de caja.*")
                        with gr.Column(scale=3, min_width=100):
                            ex_btn_supplier = gr.Button("Insumos a 90 días", variant="secondary", size="sm")
                            ex_desc_supplier = gr.Markdown("*Crédito 90 días (3% recargo).*")
                        with gr.Column(scale=3, min_width=100):
                            ex_btn_corn = gr.Button("Contrato de maíz", variant="secondary", size="sm")
                            ex_desc_corn = gr.Markdown("*Obligación maíz ≥ 150 ha.*")
                        if has_chat:
                            with gr.Column(scale=3, min_width=100):
                                ask_dora_btn = gr.Button("💬 Preguntale a DORA", variant="primary", size="sm")
                        else:
                            ask_dora_btn = None

                with gr.Row(elem_id="scenario_top_row"):
                    # Col 1: Basic Inputs & Run button
                    with gr.Column(scale=6, min_width=320, elem_classes=["compact-inputs"]):
                        md_params_head = gr.Markdown("### Parámetros de la Campaña")
                        with gr.Row():
                            with gr.Column(scale=6, min_width=100):
                                region_input = gr.Dropdown(
                                    choices=[
                                        ("Sudeste de Buenos Aires", "southeast_buenos_aires"),
                                        ("Zona núcleo (Pergamino)", "pampas_core"),
                                        ("Iowa, USA", "iowa"),
                                        ("Mato Grosso", "mato_grosso"),
                                    ],
                                    value="southeast_buenos_aires",
                                    label="Región / Region",
                                )
                            with gr.Column(scale=6, min_width=100):
                                area_input = gr.Number(value=500.0, label="Superficie total (ha)", minimum=1, maximum=100000)

                        crops_input = gr.CheckboxGroup(
                            choices=["trigo", "maíz", "soja", "girasol"],
                            value=["trigo", "maíz", "soja", "girasol"],
                            label="Cultivos disponibles",
                        )

                        with gr.Group(visible=True) as livestock_group:
                            md_livestock_head = gr.Markdown("#### Ganadería / Livestock (opcional)")
                            livestock_input = gr.CheckboxGroup(
                                choices=[
                                    ("Cría vacuna (rodeo propio)", "cow_calf"),
                                    ("Cría vacuna con compra de hacienda", "cow_calf_herd_purchase"),
                                    ("Invernada / engorde de novillos", "steer_fattening"),
                                ],
                                value=[],
                                label="Actividades ganaderas permitidas / Livestock activities",
                            )
                            livestock_only_input = gr.Number(value=0.0, label="Superficie de bajo / solo ganadera (ha, livestock_only_ha)")

                        with gr.Row():
                            with gr.Column(scale=6, min_width=100):
                                own_cap_input = gr.Number(value=50000.0, label="Capital propio inicial (USD)")
                            with gr.Column(scale=6, min_width=100):
                                cred_line_input = gr.Number(value=100000.0, label="Línea de crédito (USD)")

                        with gr.Row():
                            with gr.Column(scale=6, min_width=100):
                                cred_rate_input = gr.Number(value=10.0, label="Tasa de interés anual del crédito (%)")
                            with gr.Column(scale=6, min_width=100):
                                deposit_rate_input = gr.Number(value=4.0, label="Tasa que te paga el banco por tus dólares (% anual)")

                        with gr.Row():
                            with gr.Column(scale=7, min_width=120):
                                start_date_input = gr.Textbox(value=lambda: datetime.date.today().strftime("%d/%m/%Y"), label="Arranca el / Starts on (dd/mm/aaaa)")
                            with gr.Column(scale=5, min_width=120):
                                btn_base_season_start = gr.Button("Inicio de campaña (1/5/2026)", variant="secondary", size="sm")

                        run_btn = gr.Button("⚡ Calcular Plan Óptimo", variant="primary", size="md")

                        # Advanced Options (closed by default)
                        with gr.Accordion("⚙️ Opciones avanzadas / Advanced options", open=False, elem_id="advanced_options_accordion") as advanced_options_accordion:
                            with gr.Row():
                                with gr.Column(scale=6, min_width=100):
                                    storage_input = gr.Number(value=1000.0, label="Capacidad de almacenaje (t)")
                                with gr.Column(scale=6, min_width=100):
                                    curve_choices = ["MAGyP default"] + available_curves()
                                    price_source_input = gr.Dropdown(
                                        choices=curve_choices,
                                        value="MAGyP default",
                                        label="Fuente de curva de precios",
                                    )
                            with gr.Accordion("🗺️ Delimitar Campo en el Mapa / Field on Map", open=False):
                                gr.HTML(LEAFLET_CONTAINER_HTML)
                                polygon_input = gr.Textbox(
                                    elem_id="dora_polygon_json",
                                    label="GeoJSON Polygon (al dibujar en el mapa o pegar)",
                                    lines=2,
                                    placeholder='{"type": "Polygon", "coordinates": [[[lon, lat], ...]]}',
                                )
                                with gr.Row():
                                    apply_map_btn = gr.Button("📍 Aplicar Campo del Mapa / Apply Field", variant="secondary", size="sm")
                                    btn_check_satellite = gr.Button("🛰️ Ver cómo viene el lote (satélite) / Check field (satellite)", variant="secondary", size="sm")
                                map_status = gr.Markdown("")
                                satellite_image_out = gr.Image(label="NDVI (Sentinel-2)", type="filepath", visible=False)
                                satellite_status_out = gr.Markdown("")

                            md_land_head = gr.Markdown("#### Decisiones de Tierra y Alquiler / Land Tenure (opcional)")
                            owned_input = gr.Number(value=None, label="Superficie propia (ha; vacío = toda la superficie)")
                            rent_in_input = gr.Number(value=0.0, label="Máx. alquiler hacia adentro (ha, max_rent_in_ha)")
                            buy_input = gr.Number(value=0.0, label="Máx. compra de tierra (ha, max_buy_ha)")
                            rent_out_input = gr.Checkbox(value=False, label="Permitir alquilar hacia afuera (allow_rent_out)")
                            max_rent_out_input = gr.Number(value=None, label="Alquilar como máximo (ha)")
                            regional_rent_input = gr.Number(
                                value=None,
                                label="Alquiler que te pagarían (USD/ha)",
                                placeholder="Zona: 570 USD/ha (Márgenes Agropecuarios, 2025/26)",
                            )

                            md_supplier_head = gr.Markdown("#### Plazos de Insumos / Supplier Financing (opcional)")
                            supplier_delay_input = gr.Dropdown(
                                choices=[0, 2, 4, 6],
                                value=0,
                                label="Plazo pago insumos (quincenas: 6 = 90 días)",
                            )
                            supplier_surcharge_input = gr.Number(value=0.0, label="Recargo de proveedor por plazo (%)")

                            md_constr_head = gr.Markdown("#### Restricciones específicas (opcional)")
                            constraints_input = gr.Dataframe(
                                headers=["Type", "Crop", "Value", "Month", "Price"],
                                datatype=["str", "str", "number", "str", "number"],
                                row_count=1,
                                value=[["", "", None, "", None]],
                                label="Restricciones (min_area, max_area, min_share, forward_sale)",
                            )

                    # Col 2: Plan and Cards
                    with gr.Column(scale=6, min_width=320, elem_classes=["plan-card-box"]):
                        md_plan_head = gr.Markdown("### Plan Propuesto y Diagnóstico")
                        plan_output = gr.Markdown("Presione **Calcular Plan Óptimo** para generar el plan.")
                        break_even_table = gr.Dataframe(
                            headers=["Cultivo", "Mejor quincena para vender", "Precio hoy (USD/t)", "Precio para que entre (USD/t)", "Suba", "Verificado"],
                            datatype=["str", "str", "number", "number", "str", "str"],
                            label="¿A qué precio te convendría sembrar? / At what price would it pay to sow?",
                            visible=False,
                        )
                        with gr.Accordion("Detalle quincena a quincena por cultivo / By-fortnight detail", open=False, visible=False) as break_even_accordion:
                            break_even_fn_table = gr.Dataframe(
                                headers=["Cultivo", "Quincena", "Precio hoy (USD/t)", "Precio para que entre (USD/t)", "Suba"],
                                datatype=["str", "str", "number", "number", "str"],
                                label="Precios de indiferencia por quincena / Break-even by fortnight",
                            )
                        land_card_output = gr.Markdown("### Decisiones de tenencia y tierra")
                        resource_cards_output = gr.Markdown("#### Otros recursos")

                # Full-width Chart A: "¿Cuánto vale un dólar en cada quincena?"
                chart_rates_output = gr.Plot(
                    value=make_empty_chart("Apretá **Calcular Plan Óptimo** para ver este gráfico"),
                    label="¿Cuánto vale un dólar en cada quincena?",
                    show_label=False,
                    elem_id="chart_rates_full_width",
                )

                with gr.Row():
                    with gr.Column(scale=6):
                        chart_resources_output = gr.Plot(
                            value=make_empty_chart("Apretá **Calcular Plan Óptimo** para ver este gráfico"),
                            label="¿Cuánto vale un dólar adicional de capital o crédito?",
                            show_label=False
                        )
                    with gr.Column(scale=6):
                        chart_cash_debt_output = gr.Plot(
                            value=make_empty_chart("Apretá **Calcular Plan Óptimo** para ver este gráfico"),
                            label="¿Cómo evolucionan la caja y la deuda?",
                            show_label=False
                        )

                chart_sales_output = gr.Plot(
                    value=make_empty_chart("Apretá **Calcular Plan Óptimo** para ver este gráfico"),
                    label="Ventas por mes",
                    show_label=False
                )

                with gr.Row():
                    save_run_name = gr.Textbox(placeholder="Nombre de la corrida (opcional) / Run name (optional)", label="Guardar corrida / Save run", scale=6)
                    save_run_btn = gr.Button("💾 Guardar corrida / Save run", variant="secondary", scale=3)
                    btn_download_plan_xlsx = gr.Button("Descargar planilla (.xlsx)", variant="secondary", scale=3)
                file_download_plan_xlsx = gr.File(label="Planilla descargada (.xlsx)", visible=False)
                save_run_status = gr.Markdown("")

                md_constr_out_head = gr.Markdown("#### Restricciones y Costo de Oportunidad")
                constraints_output = gr.Dataframe(label="Análisis de Restricciones")

                md_tax_head = gr.Markdown("#### Cuña Fiscal / Tax Wedge Breakdown")
                tax_wedge_output = gr.Dataframe(label="Desglose Impositivo / Taxes Breakdown")
                tax_disclaimer_output = gr.Markdown("")

                apply_map_btn.click(
                    fn=on_apply_polygon,
                    inputs=[polygon_input, lang_state, last_scenario_state],
                    outputs=[area_input, crops_input, region_input, map_status, last_scenario_state],
                )
                polygon_input.change(
                    fn=on_apply_polygon,
                    inputs=[polygon_input, lang_state, last_scenario_state],
                    outputs=[area_input, crops_input, region_input, map_status, last_scenario_state],
                )
                btn_check_satellite.click(
                    fn=on_check_satellite,
                    inputs=[polygon_input, last_scenario_state, lang_state],
                    outputs=[satellite_image_out, satellite_status_out],
                )
                region_input.change(
                    fn=on_region_change,
                    inputs=[region_input, lang_state],
                    outputs=[crops_input, btn_base_season_start, livestock_group],
                )
                btn_base_season_start.click(
                    fn=on_click_base_season,
                    inputs=[region_input],
                    outputs=[start_date_input],
                )

                def on_run(area, crops, own_cap, cred_line, cred_rate, delay, surcharge, stor, p_source, constr, lang, reg, owned, rent_in, buy, rent_out, livestock, livestock_only, max_rent_out=None, regional_rent=None, dep_rate=4.0, s_date="03/11/2026"):
                    sc_params = {
                        "area_ha": area, "crops": crops, "own_capital_usd": own_cap,
                        "credit_line_usd": cred_line, "credit_rate_pct": cred_rate, "deposit_rate_pct": dep_rate,
                        "start_date": s_date, "supplier_delay": delay,
                        "supplier_surcharge_pct": surcharge, "storage_capacity_t": stor,
                        "price_source": p_source, "region": reg, "owned_ha": owned,
                        "max_rent_in_ha": rent_in, "max_buy_ha": buy, "allow_rent_out": rent_out,
                        "max_rent_out_ha": max_rent_out, "regional_rent_usd_ha": regional_rent,
                        "livestock": livestock, "livestock_only_ha": livestock_only, "constraints": constr,
                    }
                    try:
                        res = run_scenario(
                            area_ha=area,
                            crops=crops,
                            own_capital_usd=own_cap,
                            credit_line_usd=cred_line,
                            credit_rate_pct=cred_rate,
                            deposit_rate_pct=dep_rate,
                            start_date=s_date,
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
                            livestock=livestock,
                            livestock_only_ha=livestock_only,
                            max_rent_out_ha=max_rent_out,
                            regional_rent_usd_ha=regional_rent,
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
                            res.get("run_entry", {}),
                            res.get("scenario_payload", {}),
                            gr.update(value=res.get("break_even_table", pd.DataFrame()), visible=res.get("break_even_visible", False)),
                            gr.update(visible=res.get("break_even_visible", False)),
                            gr.update(value=res.get("break_even_fn_table", pd.DataFrame())),
                        )
                    except Exception as e:
                        err_msg = f"❌ Error en la optimización: {e}" if lang == "es" else f"❌ Optimization error: {e}"
                        empty_c = make_empty_chart(err_msg)
                        return (
                            err_msg,
                            "",
                            empty_c,
                            empty_c,
                            "",
                            empty_c,
                            empty_c,
                            pd.DataFrame(),
                            pd.DataFrame(),
                            "",
                            {},
                            {},
                            gr.update(value=pd.DataFrame(), visible=False),
                            gr.update(visible=False),
                            gr.update(value=pd.DataFrame()),
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
                        livestock_input,
                        livestock_only_input,
                        max_rent_out_input,
                        regional_rent_input,
                        deposit_rate_input,
                        start_date_input,
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
                        current_run_state,
                        last_scenario_state,
                        break_even_table,
                        break_even_accordion,
                        break_even_fn_table,
                    ],
                )

                def on_save_run(saved_runs, current_run, name, lang):
                    is_es = lang == "es"
                    if not current_run:
                        msg = "⚠️ Primero calcule un plan óptimo para guardarlo." if is_es else "⚠️ First compute an optimal plan before saving."
                        return saved_runs, msg
                    updated = save_run(saved_runs, current_run, name=name)
                    run_name = updated[-1].get("name", "Run")
                    msg = f"✅ Corrida guardada: **{run_name}** ({len(updated)}/8 corridas)" if is_es else f"✅ Run saved: **{run_name}** ({len(updated)}/8 runs)"
                    return updated, msg

                save_run_btn.click(
                    fn=on_save_run,
                    inputs=[saved_runs_state, current_run_state, save_run_name, lang_state],
                    outputs=[saved_runs_state, save_run_status],
                )

                def on_download_plan_xlsx(last_sc, lang):
                    if not last_sc:
                        return None
                    from dora.tools import export_plan_spreadsheet
                    res = export_plan_spreadsheet(last_sc, lang=lang)
                    return res.get("file")

                btn_download_plan_xlsx.click(
                    fn=on_download_plan_xlsx,
                    inputs=[last_scenario_state, lang_state],
                    outputs=[file_download_plan_xlsx],
                )

                # Example button handlers: load AND compute (SPEC-23 Section 2 & SPEC-37)
                def on_example_rationed(lang: str):
                    is_es = lang == "es"
                    c_list = ["trigo", "maíz", "soja", "girasol"] if is_es else ["wheat", "corn", "soybean", "sunflower"]
                    constr = [["", "", None, "", None]]
                    res = run_scenario(
                        area_ha=500.0,
                        crops=c_list,
                        own_capital_usd=50000.0,
                        credit_line_usd=100000.0,
                        credit_rate_pct=10.0,
                        deposit_rate_pct=4.0,
                        start_date=None,
                        supplier_delay=0,
                        supplier_surcharge_pct=0.0,
                        storage_capacity_t=1000.0,
                        price_source="MAGyP default",
                        constraints_df=constr,
                        lang=lang,
                        region="southeast_buenos_aires",
                    )
                    return (
                        500.0, c_list, 50000.0, 100000.0, 10.0, 0, 0.0, 1000.0, "MAGyP default", "southeast_buenos_aires",
                        constr, None, 0.0, 0.0, False, [], 0.0,
                        res["plan"], res["land_card"], res["chart_rates"], res["chart_resources"],
                        res["resource_cards"], res["chart_cash_debt"], res["chart_sales"],
                        res["constraints"], res["tax_wedge_table"], res["tax_disclaimer"],
                        gr.update(value=res.get("break_even_table", pd.DataFrame()), visible=res.get("break_even_visible", False)),
                        gr.update(visible=res.get("break_even_visible", False)),
                        gr.update(value=res.get("break_even_fn_table", pd.DataFrame())),
                        4.0, "01/05/2026",
                        res.get("run_entry", {}), res.get("scenario_payload", {}),
                    )

                def on_example_supplier(lang: str):
                    is_es = lang == "es"
                    c_list = ["trigo", "maíz", "soja", "girasol"] if is_es else ["wheat", "corn", "soybean", "sunflower"]
                    constr = [["", "", None, "", None]]
                    res = run_scenario(
                        area_ha=500.0,
                        crops=c_list,
                        own_capital_usd=50000.0,
                        credit_line_usd=100000.0,
                        credit_rate_pct=10.0,
                        deposit_rate_pct=4.0,
                        start_date=None,
                        supplier_delay=6,
                        supplier_surcharge_pct=3.0,
                        storage_capacity_t=1000.0,
                        price_source="MAGyP default",
                        constraints_df=constr,
                        lang=lang,
                        region="southeast_buenos_aires",
                    )
                    return (
                        500.0, c_list, 50000.0, 100000.0, 10.0, 6, 3.0, 1000.0, "MAGyP default", "southeast_buenos_aires",
                        constr, None, 0.0, 0.0, False, [], 0.0,
                        res["plan"], res["land_card"], res["chart_rates"], res["chart_resources"],
                        res["resource_cards"], res["chart_cash_debt"], res["chart_sales"],
                        res["constraints"], res["tax_wedge_table"], res["tax_disclaimer"],
                        gr.update(value=res.get("break_even_table", pd.DataFrame()), visible=res.get("break_even_visible", False)),
                        gr.update(visible=res.get("break_even_visible", False)),
                        gr.update(value=res.get("break_even_fn_table", pd.DataFrame())),
                        4.0, "01/05/2026",
                        res.get("run_entry", {}), res.get("scenario_payload", {}),
                    )

                def on_example_corn(lang: str):
                    is_es = lang == "es"
                    c_list = ["trigo", "maíz", "soja", "girasol"] if is_es else ["wheat", "corn", "soybean", "sunflower"]
                    corn_name = "maíz" if is_es else "corn"
                    constr = [["min_area", corn_name, 150, "", None]]
                    res = run_scenario(
                        area_ha=500.0,
                        crops=c_list,
                        own_capital_usd=50000.0,
                        credit_line_usd=100000.0,
                        credit_rate_pct=10.0,
                        deposit_rate_pct=4.0,
                        start_date=None,
                        supplier_delay=0,
                        supplier_surcharge_pct=0.0,
                        storage_capacity_t=1000.0,
                        price_source="MAGyP default",
                        constraints_df=constr,
                        lang=lang,
                        region="southeast_buenos_aires",
                    )
                    return (
                        500.0, c_list, 50000.0, 100000.0, 10.0, 0, 0.0, 1000.0, "MAGyP default", "southeast_buenos_aires",
                        constr, None, 0.0, 0.0, False, [], 0.0,
                        res["plan"], res["land_card"], res["chart_rates"], res["chart_resources"],
                        res["resource_cards"], res["chart_cash_debt"], res["chart_sales"],
                        res["constraints"], res["tax_wedge_table"], res["tax_disclaimer"],
                        gr.update(value=res.get("break_even_table", pd.DataFrame()), visible=res.get("break_even_visible", False)),
                        gr.update(visible=res.get("break_even_visible", False)),
                        gr.update(value=res.get("break_even_fn_table", pd.DataFrame())),
                        4.0, "01/05/2026",
                        res.get("run_entry", {}), res.get("scenario_payload", {}),
                    )

                example_outputs = [
                    area_input, crops_input, own_cap_input, cred_line_input, cred_rate_input,
                    supplier_delay_input, supplier_surcharge_input, storage_input, price_source_input,
                    region_input, constraints_input, owned_input, rent_in_input, buy_input,
                    rent_out_input, livestock_input, livestock_only_input,
                    plan_output, land_card_output, chart_rates_output, chart_resources_output,
                    resource_cards_output, chart_cash_debt_output, chart_sales_output,
                    constraints_output, tax_wedge_output, tax_disclaimer_output,
                    break_even_table, break_even_accordion, break_even_fn_table,
                    deposit_rate_input, start_date_input,
                    current_run_state, last_scenario_state,
                ]

                ex_btn_rationed.click(
                    fn=on_example_rationed,
                    inputs=[lang_state],
                    outputs=example_outputs,
                )
                ex_btn_supplier.click(
                    fn=on_example_supplier,
                    inputs=[lang_state],
                    outputs=example_outputs,
                )
                ex_btn_corn.click(
                    fn=on_example_corn,
                    inputs=[lang_state],
                    outputs=example_outputs,
                )

                if has_chat and ask_dora_btn is not None:
                    ask_dora_btn.click(
                        fn=lambda: gr.update(selected="tab_chat"),
                        inputs=[],
                        outputs=[tabs],
                    )

            # ------------------------------------------------------------------
            # TAB 2: REGIONAL OBSERVATORY
            # ------------------------------------------------------------------
            with gr.TabItem("🌍 Regiones / Regional Observatory", id="tab_regions", elem_id="tab_regions") as tab_regions:
                obs_banner = gr.Markdown("")
                obs_map = gr.HTML("")
                obs_table = gr.Dataframe(label="Comparación Regional / Regional Comparison")
                obs_chart = gr.Plot(label="Evolución de Tasa Interna de Oportunidad", show_label=False)

                refresh_obs_btn = gr.Button("🔄 Actualizar Observatorio / Refresh", variant="secondary", size="sm")

                def on_refresh_observatory(curr_lang: str):
                    banner, map_html, table_df, fig = get_observatory_ui_data(force_run=True, lang=curr_lang)
                    return banner, map_html, table_df, fig

                refresh_obs_btn.click(
                    fn=on_refresh_observatory,
                    inputs=[lang_state],
                    outputs=[obs_banner, obs_map, obs_table, obs_chart],
                )

                def on_select_tab_regions(curr_lang: str):
                    banner, map_html, table_df, fig = get_observatory_ui_data(force_run=False, lang=curr_lang)
                    return banner, map_html, table_df, fig

                tab_regions.select(
                    fn=on_select_tab_regions,
                    inputs=[lang_state],
                    outputs=[obs_banner, obs_map, obs_table, obs_chart],
                )

            # ------------------------------------------------------------------
            # TAB: COMPARISON (SPEC-13)
            # ------------------------------------------------------------------
            with gr.TabItem("⚖️ Comparar / Compare", id="tab_compare", elem_id="tab_compare"):
                compare_mode_radio = gr.Radio(
                    choices=[
                        "Mismo campo, todas las regiones",
                        "Misma plata, todas las regiones",
                        "Comparar corridas guardadas",
                    ],
                    value="Mismo campo, todas las regiones",
                    label="Modo de comparación / Comparison mode",
                )
                with gr.Row():
                    compare_run_btn = gr.Button("⚡ Comparar / Compare", variant="primary")
                    clear_runs_btn = gr.Button("🗑️ Limpiar corridas guardadas / Clear saved runs", variant="secondary")

                compare_status_md = gr.Markdown("")
                compare_table = gr.Dataframe(label="Tabla Comparativa / Comparison Table")
                compare_chart_a = gr.Plot(
                    value=make_empty_chart("Apretá **Comparar** para ver este gráfico"),
                    label="Chart A: Tasa Interna de Oportunidad (% anual)",
                    show_label=False
                )
                compare_chart_b = gr.Plot(
                    value=make_empty_chart("Apretá **Comparar** para ver este gráfico"),
                    label="¿Qué deja una hectárea: sembrarla o alquilarla?",
                    show_label=False
                )
                compare_chart_c = gr.Plot(
                    value=make_empty_chart("Apretá **Comparar** para ver este gráfico"),
                    label="Chart C: Desglose de Precio en Chacra (USD/t)",
                    show_label=False
                )

                def on_run_comparison(mode_choice: str, saved_runs: list, own_cap: float, area: float, lang: str):
                    is_es = lang == "es"
                    is_budget_mode = "Misma plata" in str(mode_choice) or "Same budget" in str(mode_choice)
                    is_farm_mode = "Mismo campo" in str(mode_choice) or "Same farm" in str(mode_choice)
                    if is_budget_mode or is_farm_mode:
                        sc_payload = {"own_capital_usd": float(own_cap) if own_cap else 50000.0}
                        if is_farm_mode:
                            sc_payload["area_ha"] = float(area) if area else 500.0
                        from dora.tools import compare_regions
                        comp_res = compare_regions(sc_payload, mode="same_farm" if is_farm_mode else "same_budget")
                        items = list(comp_res.get("regions", {}).values())
                        table_df = build_comparison_table(items, lang=lang)
                        fig_a = create_comparison_rates_chart(items, lang=lang)
                        fig_b = create_comparison_margin_vs_rent_chart(items, lang=lang)
                        fig_c = create_comparison_price_decomposition_chart(items, lang=lang)
                        rule_es = "mismo campo y capital" if is_farm_mode else "misma plata"
                        rule_en = "same farm and capital" if is_farm_mode else "same budget"
                        status = (f"✅ Comparación calculada para todas las regiones (regla: {rule_es}), con el capital y la superficie de la pestaña Escenario."
                                  if is_es else f"✅ Comparison computed across all regions ({rule_en} rule), with the capital and area from the Scenario tab.")
                        return status, table_df, fig_a, fig_b, fig_c
                    else:
                        if not saved_runs:
                            status = "ℹ️ No hay corridas guardadas. Guarde una corrida desde la pestaña Escenario." if is_es else "ℹ️ No saved runs yet. Save a run from the Scenario tab."
                            empty_df = build_comparison_table([], lang=lang)
                            empty_fig = make_empty_chart("Apretá **Comparar** para ver este gráfico" if is_es else "Press **Compare** to see this chart")
                            return status, empty_df, empty_fig, empty_fig, empty_fig
                        table_df = build_comparison_table(saved_runs, lang=lang)
                        fig_a = create_comparison_rates_chart(saved_runs, lang=lang)
                        fig_b = create_comparison_roc_chart(saved_runs, lang=lang)
                        fig_c = create_comparison_price_decomposition_chart(saved_runs, lang=lang)
                        status = f"✅ Comparando {len(saved_runs)} corridas guardadas." if is_es else f"✅ Comparing {len(saved_runs)} saved runs."
                        return status, table_df, fig_a, fig_b, fig_c

                def on_clear_runs(lang: str):
                    is_es = lang == "es"
                    status = "🗑️ Corridas guardadas eliminadas." if is_es else "🗑️ Saved runs cleared."
                    empty_df = build_comparison_table([], lang=lang)
                    empty_fig = make_empty_chart("Apretá **Comparar** para ver este gráfico" if is_es else "Press **Compare** to see this chart")
                    return [], status, empty_df, empty_fig, empty_fig, empty_fig

                compare_run_btn.click(
                    fn=on_run_comparison,
                    inputs=[compare_mode_radio, saved_runs_state, own_cap_input, area_input, lang_state],
                    outputs=[compare_status_md, compare_table, compare_chart_a, compare_chart_b, compare_chart_c],
                )
                clear_runs_btn.click(
                    fn=on_clear_runs,
                    inputs=[lang_state],
                    outputs=[saved_runs_state, compare_status_md, compare_table, compare_chart_a, compare_chart_b, compare_chart_c],
                )

            # Wire Start Here tab buttons
            if has_chat:
                btn_card1.click(
                    fn=on_switch_to_chat,
                    inputs=[],
                    outputs=[tabs],
                ).then(
                    fn=on_start_card1_pending,
                    inputs=[chatbot, lang_state],
                    outputs=[chatbot],
                    queue=False,
                ).then(
                    fn=on_start_card1,
                    inputs=[chatbot, agent_state, lang_state, last_scenario_state],
                    outputs=[chat_msg, chat_files, chat_audio, chatbot, agent_state],
                )
                btn_card2.click(
                    fn=on_switch_to_chat,
                    inputs=[],
                    outputs=[tabs],
                ).then(
                    fn=on_start_card2_pending,
                    inputs=[chatbot, lang_state],
                    outputs=[chatbot],
                    queue=False,
                ).then(
                    fn=on_start_card2,
                    inputs=[chatbot, agent_state, lang_state, last_scenario_state],
                    outputs=[chat_msg, chat_files, chat_audio, chatbot, agent_state],
                )

            btn_card3.click(
                fn=on_start_card3,
                inputs=[],
                outputs=[tabs],
            )

            btn_scenario_link.click(
                fn=on_start_scenario_link,
                inputs=[],
                outputs=[tabs],
            )

            # ------------------------------------------------------------------
            # INITIAL LOAD EVENT (SPEC-23 Section 1: Page is never empty)
            # ------------------------------------------------------------------
            def on_app_load(lang: str):
                is_es = lang == "es"
                c_list = ["trigo", "maíz", "soja", "girasol"] if is_es else ["wheat", "corn", "soybean", "sunflower"]
                res = run_scenario(
                    area_ha=500.0,
                    crops=c_list,
                    own_capital_usd=50000.0,
                    credit_line_usd=100000.0,
                    credit_rate_pct=10.0,
                    supplier_delay=0,
                    supplier_surcharge_pct=0.0,
                    storage_capacity_t=1000.0,
                    price_source="MAGyP default",
                    constraints_df=None,
                    lang=lang,
                    region="southeast_buenos_aires",
                )
                sc_params = {
                    "area_ha": 500.0, "crops": c_list, "own_capital_usd": 50000.0,
                    "credit_line_usd": 100000.0, "credit_rate_pct": 10.0, "supplier_delay": 0,
                    "supplier_surcharge_pct": 0.0, "storage_capacity_t": 1000.0,
                    "price_source": "MAGyP default", "region": "southeast_buenos_aires",
                    "constraints": [],
                }
                banner, map_html, table_df, fig_obs = get_observatory_ui_data(force_run=False, lang=lang)
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
                    res.get("run_entry", {}),
                    res.get("scenario_payload", {}),
                    banner,
                    map_html,
                    table_df,
                    fig_obs,
                )

            app.load(
                fn=on_app_load,
                inputs=[lang_state],
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
                    current_run_state,
                    last_scenario_state,
                    obs_banner,
                    obs_map,
                    obs_table,
                    obs_chart,
                ],
            )

            # Attach test helpers to app instance
            app.load_fn = on_app_load
            app.example_rationed_fn = on_example_rationed
            app.example_supplier_fn = on_example_supplier
            app.example_corn_fn = on_example_corn
            app.run_fn = on_run
            app.respond_fn = respond if has_chat else None

            # Language switch: (component, attribute, Spanish, English).
            ui_texts = [
                (md_title, "value", "# 🌾 DORA — Asistente de Planificación Agrícola", "# 🌾 DORA — Farm Planning Assistant"),
                (md_subtitle, "value", "Optimización económica de campaña agrícola, análisis de cuellos de botella de capital y costo de oportunidad de los recursos.",
                 "Economic optimization of the farming season: capital bottlenecks and opportunity cost of resources."),
                (how_to_start_accordion, "label", "¿Cómo empiezo?", "How do I start?"),
                (md_how_to_start, "value",
                 "**1.** Elegí un ejemplo abajo o delimitá tu lote en el mapa. Si tenés hacienda, marcá cría o invernada.\n"
                 "**2.** Apretá **Calcular Plan Óptimo** (o hacé clic en cualquiera de los ejemplos para cargarlo y calcularlo).\n"
                 "**3.** Mirá qué falta y qué sobra: los gráficos te dicen cuánto te vale un dólar, una hectárea o una tonelada más de almacenaje.",
                 "**1.** Choose an example below or draw your field on the map. If you have cattle, check cow-calf or steer fattening.\n"
                 "**2.** Press **Calculate Optimal Plan** (or click any of the examples to load and calculate it).\n"
                 "**3.** Look at what is short and what is left over: the charts tell you what one more dollar, hectare or tonne of storage is worth to you."),
                (ex_btn_rationed, "value", "Capital restringido", "Rationed capital"),
                (ex_desc_rationed, "value",
                 "*Capital propio escaso (USD 50.000 para 500 ha): muestra qué cultivos quedan afuera por falta de liquidez y cuándo la plata escasea.*",
                 "*Scarce own capital (USD 50,000 for 500 ha): shows which crops are left out due to liquidity shortages and when money is scarce.*"),
                (ex_btn_supplier, "value", "Insumos a 90 días", "Inputs at 90 days"),
                (ex_desc_supplier, "value",
                 "*Mismo campo pero con crédito de proveedor a 90 días (6 quincenas al 3%): el plazo de insumos alivia la caja de siembra.*",
                 "*Same farm but with 90-day supplier credit (6 fortnights at 3%): supplier financing relieves sowing cash flow.*"),
                (ex_btn_corn, "value", "Contrato de maíz", "Corn contract"),
                (ex_desc_corn, "value",
                 "*Obligación de sembrar al menos 150 ha de maíz: muestra el costo de oportunidad de forzar un cultivo.*",
                 "*Commitment to sow at least 150 ha of corn: shows the opportunity cost of forcing a crop.*"),
                (md_params_head, "value", "### Parámetros de la Campaña", "### Season Parameters"),
                (region_input, "label", "Región", "Region"),
                (area_input, "label", "Superficie total (ha)", "Total area (ha)"),
                (crops_input, "label", "Cultivos disponibles", "Available crops"),
                (own_cap_input, "label", "Capital propio inicial (USD)", "Own starting capital (USD)"),
                (cred_line_input, "label", "Línea de crédito (USD)", "Credit line (USD)"),
                (cred_rate_input, "label", "Tasa de interés anual del crédito (%)", "Annual credit interest rate (%)"),
                (deposit_rate_input, "label", "Tasa que te paga el banco por tus dólares (% anual)", "What the bank pays on your dollars (% a year)"),
                (start_date_input, "label", "Arranca el / Starts on (dd/mm/aaaa)", "Starts on (dd/mm/yyyy)"),
                (btn_base_season_start, "value", "Inicio de campaña (1/5/2026)", "Season start (1/5/2026)"),
                (storage_input, "label", "Capacidad de almacenaje propio (t)", "Own storage capacity (t)"),
                (price_source_input, "label", "Fuente de curva de precios", "Price curve source"),
                (run_btn, "value", "⚡ Calcular Plan Óptimo", "⚡ Compute Optimal Plan"),
                (advanced_options_accordion, "label", "⚙️ Opciones avanzadas", "⚙️ Advanced options"),
                (supplier_delay_input, "label", "Plazo pago insumos (quincenas: 6 = 90 días)", "Input payment delay (fortnights: 6 = 90 days)"),
                (supplier_surcharge_input, "label", "Recargo de proveedor por plazo (%)", "Supplier surcharge for the delay (%)"),
                (md_land_head, "value", "#### Decisiones de tierra (opcional)", "#### Land decisions (optional)"),
                (owned_input, "label", "Superficie propia (ha; vacío = toda la superficie)", "Owned area (ha; empty = all of it)"),
                (rent_in_input, "label", "Máximo a tomar en alquiler (ha)", "Maximum to rent in (ha)"),
                (buy_input, "label", "Máximo a comprar (ha)", "Maximum to buy (ha)"),
                (rent_out_input, "label", "Permitir dar el campo en alquiler", "Allow renting the land out"),
                (max_rent_out_input, "label", "Alquilar como máximo (ha)", "Maximum to rent out (ha)"),
                (regional_rent_input, "label", "Alquiler que te pagarían (USD/ha)", "Rent paid to you (USD/ha)"),
                (md_supplier_head, "value", "#### Plazos de Insumos (opcional)", "#### Supplier Financing (optional)"),
                (md_livestock_head, "value", "#### Ganadería (opcional)", "#### Livestock (optional)"),
                (livestock_input, "label", "Actividades ganaderas permitidas", "Allowed livestock activities"),
                (livestock_only_input, "label", "Superficie de bajo, solo ganadera (ha)", "Low land, livestock only (ha)"),
                (md_constr_head, "value", "#### Restricciones específicas (opcional)", "#### Specific constraints (optional)"),
                (md_plan_head, "value", "### Plan Propuesto y Diagnóstico", "### Proposed Plan and Diagnosis"),
                (chart_rates_output, "label", "¿Cuánto vale un dólar en cada quincena?", "What is a dollar worth in each fortnight?"),
                (chart_resources_output, "label", "¿Cuánto vale un dólar adicional de capital o crédito?", "What is one more dollar of capital or credit worth?"),
                (chart_cash_debt_output, "label", "¿Cómo evolucionan la caja y la deuda?", "How do cash and debt evolve?"),
                (chart_sales_output, "label", "Ventas por mes", "Sales by month"),
                (md_constr_out_head, "value", "#### Restricciones y Costo de Oportunidad", "#### Constraints and Opportunity Cost"),
                (constraints_output, "label", "Análisis de Restricciones", "Constraint analysis"),
                (md_tax_head, "value", "#### Cuña fiscal", "#### Tax wedge"),
                (tax_wedge_output, "label", "Desglose impositivo", "Taxes breakdown"),
                (save_run_name, "label", "Guardar corrida", "Save run"),
                (save_run_btn, "value", "💾 Guardar corrida", "💾 Save run"),
                (compare_mode_radio, "label", "Modo de comparación", "Comparison mode"),
                (compare_run_btn, "value", "⚡ Comparar", "⚡ Compare"),
                (clear_runs_btn, "value", "🗑️ Limpiar corridas guardadas", "🗑️ Clear saved runs"),
                (compare_table, "label", "Tabla Comparativa", "Comparison Table"),
                (compare_chart_a, "label", "Chart A: Tasa Interna de Oportunidad (% anual)", "Chart A: Capital Opportunity Internal Rate (% annual)"),
                (compare_chart_b, "label", "¿Qué deja una hectárea: sembrarla o alquilarla?", "What does one hectare earn: farmed or rented out?"),
                (compare_chart_c, "label", "Chart C: Desglose de Precio en Chacra (USD/t)", "Chart C: Farm-gate Price Decomposition (USD/t)"),
                (obs_table, "label", "Comparación Regional", "Regional Comparison"),
                (obs_chart, "label", "Evolución de Tasa Interna de Oportunidad", "Capital Opportunity Internal Rate Evolution"),
                (refresh_obs_btn, "value", "🔄 Actualizar Observatorio", "🔄 Refresh Observatory"),
                (start_title_md, "value",
                 "### DORA planifica tu campaña agrícola\nVos le contás tu campo; un motor matemático calcula el plan y cada número se verifica antes de mostrártelo.",
                 "### DORA plans your crop season\nYou describe your farm; a math engine computes the plan, and every number is checked before you see it."),
                (card1_title_md, "value", "#### 🌾 Planificá tu campaña", "#### 🌾 Plan your season"),
                (card1_desc_md, "value",
                 "DORA te pregunta de a una cosa por vez, empezando por la que más cambia el plan.",
                 "DORA asks one thing at a time, starting with what changes the plan the most."),
                (card2_title_md, "value", "#### 📑 Mandale una factura", "#### 📑 Send an invoice"),
                (card2_desc_md, "value",
                 "DORA lee la foto renglón por renglón y recalcula el plan con esos costos.",
                 "DORA reads the photo line by line and recalculates the plan with those costs."),
                (card3_title_md, "value", "#### 🌐 Compará regiones", "#### 🌐 Compare regions"),
                (card3_desc_md, "value",
                 "Balcarce, Pergamino, Iowa y Mato Grosso en un mapa, con su retorno y su flete al puerto.",
                 "Balcarce, Pergamino, Iowa and Mato Grosso on a map, with their return and freight to port."),
                (btn_card3, "value", "Ver regiones", "View regions"),
                (btn_scenario_link, "value",
                 "¿Querés tocar los números vos? Abrí la pestaña Escenario.",
                 "Want to set the numbers yourself? Open the Scenario tab."),
                (start_steps_md, "value",
                 "### ¿Cómo usar DORA?\n1. **Contale tu campo:** hectáreas, región, plata propia, crédito.\n2. **Si falta algo que cambia el plan, DORA te pregunta;** si no sabés, dice qué va a suponer.\n3. **Podés escribir, mandar una nota de voz o una foto de una factura.**\n4. **Cada respuesta dice si está verificada:** todos los números salen del motor.",
                 "### How to use DORA\n1. **Tell it about your farm:** hectares, region, own money, credit.\n2. **If something that changes the plan is missing, DORA asks;** if you don't know, it says what it will assume.\n3. **You can type, send a voice note or a photo of an invoice.**\n4. **Every answer says whether it is verified:** all its numbers come from the engine."),
            ]
            if has_chat:
                if ask_dora_btn is not None:
                    ui_texts.append((ask_dora_btn, "value", "💬 Preguntale a DORA (abrir chat)", "💬 Ask DORA (open chat)"))
                ui_texts.append((chat_files, "label", "Fotos de facturas / remitos / presupuestos (JPG/PNG)", "Photos of invoices / delivery notes / quotes (JPG/PNG)"))
                ui_texts.append((chat_audio, "label", "Nota de voz (grabación o archivo)", "Voice note (recording or file)"))
                ui_texts.append((chat_msg, "label", "Tu mensaje", "Your message"))
                ui_texts.append((chat_attach, "label", "📎 Adjuntar fotos o nota de voz", "📎 Attach photos or a voice note"))
                ui_texts.append((chat_msg, "placeholder", "Consultá sobre tu plan de siembra o enviá facturas/fotos...", "Ask about your planting plan or send invoices/photos..."))
                ui_texts.append((chat_send, "value", "Enviar", "Send"))
                ui_texts.append((btn_card1, "value", "Probar", "Try it"))
                ui_texts.append((btn_card2, "value", "Probar", "Try it"))
                if has_baseten and model_choice is not None and model_subline is not None:
                    ui_texts.append((model_choice, "label", "Modelo", "Model"))
                    ui_texts.append((model_subline, "value", "*Las dos versiones usan el mismo motor y el mismo verificador.*", "*Both use the same engine and the same checker.*"))
            else:
                ui_texts.append((no_chat_msg1, "value", "*El chat necesita la clave del modelo.*", "*The chat needs the model key.*"))
                ui_texts.append((no_chat_msg2, "value", "*El chat necesita la clave del modelo.*", "*The chat needs the model key.*"))

            def on_lang_change(selected_lang: str, last_sc: dict | None = None, current_crops: list | None = None, current_region: str = "southeast_buenos_aires"):
                is_es = selected_lang == "Español"
                curr_lang = "es" if is_es else "en"
                reg_crops = list(REGIONS.get(current_region, REGIONS["southeast_buenos_aires"])["crops"])
                if is_es:
                    crops_choices = [CROP_TRANSLATION_TO_ES.get(c, c) for c in reg_crops]
                else:
                    crops_choices = [CROP_TRANSLATION_TO_EN.get(c, c) for c in reg_crops]

                crop_to_key = {}
                for c in reg_crops:
                    crop_to_key[c] = c
                    crop_to_key[CROP_TRANSLATION_TO_ES.get(c, c)] = c
                    crop_to_key[CROP_TRANSLATION_TO_EN.get(c, c)] = c

                if current_crops:
                    crops_val = []
                    for c in current_crops:
                        key = crop_to_key.get(c, c)
                        trans = CROP_TRANSLATION_TO_ES.get(key, key) if is_es else CROP_TRANSLATION_TO_EN.get(key, key)
                        if trans in crops_choices and trans not in crops_val:
                            crops_val.append(trans)
                    if not crops_val:
                        crops_val = list(crops_choices)
                else:
                    crops_val = list(crops_choices)
                comp_choices = [
                    "Mismo campo, todas las regiones",
                    "Misma plata, todas las regiones",
                    "Comparar corridas guardadas",
                ] if is_es else [
                    "Same farm, every region",
                    "Same budget, every region",
                    "Compare saved runs",
                ]

                # 1. Recompute last scenario in new language
                sc = dict(last_sc or {})
                sc_crops = sc.get("crops") or crops_val
                cred_rate = float(sc.get("credit_rate_annual", 0.10) * 100.0 if "credit_rate_annual" in sc else sc.get("credit_rate_pct", 10.0))
                sup_surcharge = float(sc.get("input_delay_surcharge", 0.0) * 100.0 if "input_delay_surcharge" in sc else sc.get("supplier_surcharge_pct", 0.0))
                res = run_scenario(
                    area_ha=float(sc.get("area_ha", 500.0)),
                    crops=sc_crops,
                    own_capital_usd=float(sc.get("own_capital_usd", 50000.0)),
                    credit_line_usd=float(sc.get("credit_line_usd", 100000.0)),
                    credit_rate_pct=cred_rate,
                    supplier_delay=int(sc.get("input_payment_delay_fortnights", sc.get("supplier_delay", 0))),
                    supplier_surcharge_pct=sup_surcharge,
                    storage_capacity_t=float(sc.get("storage_capacity_t", 1000.0)),
                    price_source=sc.get("price_curve_source", sc.get("price_source", "MAGyP default")),
                    constraints_df=sc.get("constraints"),
                    lang=curr_lang,
                    region=sc.get("region", "southeast_buenos_aires"),
                    owned_ha=sc.get("owned_ha"),
                    max_rent_in_ha=float(sc.get("max_rent_in_ha", 0.0)),
                    allow_rent_out=bool(sc.get("allow_rent_out", False)),
                    max_buy_ha=float(sc.get("max_buy_ha", 0.0)),
                    livestock=sc.get("livestock"),
                    livestock_only_ha=float(sc.get("livestock_only_ha", 0.0)),
                )

                # 2. Recompute observatory in new language
                banner, map_html, new_table, fig_obs = get_observatory_ui_data(force_run=False, lang=curr_lang)

                # 3. Compare tab empty charts & notice in new language
                empty_comp_msg = "Apretá **Comparar** para ver este gráfico" if is_es else "Press **Compare** to see this chart"
                c_status = ""
                comp_a = make_empty_chart(empty_comp_msg)
                comp_b = make_empty_chart(empty_comp_msg)
                comp_c = make_empty_chart(empty_comp_msg)

                # 4. Text updates
                texts = [gr.update(**{attr: es if is_es else en}) for _, attr, es, en in ui_texts]

                return [
                    curr_lang,
                    gr.update(choices=crops_choices, value=crops_val),
                    gr.update(choices=comp_choices, value=comp_choices[0]),
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
                    res.get("run_entry", {}),
                    res.get("scenario_payload", {}),
                    banner,
                    map_html,
                    new_table,
                    fig_obs,
                    c_status,
                    comp_a,
                    comp_b,
                    comp_c,
                    *texts,
                ]

            lang_outputs = [
                lang_state,
                crops_input,
                compare_mode_radio,
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
                current_run_state,
                last_scenario_state,
                obs_banner,
                obs_map,
                obs_table,
                obs_chart,
                compare_status_md,
                compare_chart_a,
                compare_chart_b,
                compare_chart_c,
                *[c for c, *_ in ui_texts],
            ]

            lang_radio.change(
                fn=on_lang_change,
                inputs=[lang_radio, last_scenario_state, crops_input, region_input],
                outputs=lang_outputs,
            )
            app.lang_change_fn = on_lang_change

            if has_chat:
                chat_greeting = {
                    "es": initial_chat_msg,
                    "en": "Tell me about your season: hectares, crops, money and credit. You can type or send a voice note.",
                }

                def greet_in_lang(selected_lang: str, history: list):
                    """Swap the greeting's language while the conversation has not started."""
                    if history and len(history) > 1:
                        return gr.update()
                    lang_key = "es" if selected_lang == "Español" else "en"
                    if history and len(history) == 1:
                        content = history[0].get("content", "")
                        if "Muse Spark Open" in content:
                            msg = "Ahora conversás con Muse Spark Open." if lang_key == "es" else "You are now talking to Muse Spark Open."
                            return [{"role": "assistant", "content": msg}]
                        if "Muse Spark 1.3" in content:
                            msg = "Ahora conversás con Muse Spark 1.3." if lang_key == "es" else "You are now talking to Muse Spark 1.3."
                            return [{"role": "assistant", "content": msg}]
                    return [{"role": "assistant", "content": chat_greeting[lang_key]}]

                lang_radio.change(fn=greet_in_lang, inputs=[lang_radio, chatbot], outputs=[chatbot])
                app.load(fn=greet_in_lang, inputs=[lang_radio, chatbot], outputs=[chatbot])

        app.tab_start = tab_start
        app.start_title_md = start_title_md
        app.card1_title_md = card1_title_md
        app.card2_title_md = card2_title_md
        app.card3_title_md = card3_title_md
        app.card1_btn = btn_card1
        app.card2_btn = btn_card2
        app.card3_btn = btn_card3
        app.scenario_link_btn = btn_scenario_link
        app.btn_download_plan_xlsx = btn_download_plan_xlsx
        app.on_download_plan_xlsx = on_download_plan_xlsx
        app.tabs = tabs
        app.has_chat = has_chat
        app.model_choice = model_choice
        app.model_subline = model_subline
        app.show_pending = show_pending
        if os.environ.get("WHATSAPP_TOKEN"):
            try:
                from dora.whatsapp import mount_whatsapp_webhook
                mount_whatsapp_webhook(app.app)
            except Exception as e:
                print(f"Warning: could not mount WhatsApp webhook: {e}")
    return app


def resolve_server_config() -> tuple[str, int]:
    """Resolve Gradio server host and port from environment or defaults.

    Reads GRADIO_SERVER_NAME and GRADIO_SERVER_PORT from environment,
    defaulting to '0.0.0.0' and 7860 (standard Hugging Face Space configuration).
    """
    host = os.environ.get("GRADIO_SERVER_NAME", "0.0.0.0")
    raw_port = os.environ.get("GRADIO_SERVER_PORT", "7860")
    try:
        port = int(raw_port)
    except (ValueError, TypeError):
        port = 7860
    return host, port


if __name__ == "__main__":
    server_name, server_port = resolve_server_config()
    demo = build_app()
    demo.launch(
        server_name=server_name,
        server_port=server_port,
        head=getattr(demo, "head", None),
        theme=getattr(demo, "theme", None),
    )
