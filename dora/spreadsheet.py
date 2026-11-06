"""Spreadsheet export and round-trip import for DORA agricultural plans (SPEC-42).

Exports a 7-sheet workbook (Summary, Plan by crop, Cash by fortnight, Assumptions,
Sensitivity, Verification, and hidden _dora) with live formulas and openpyxl LineChart.
Imports modified .xlsx files with strict range validation and no code execution.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import io
import json
import logging
from pathlib import Path
import re
import tempfile
from typing import Any
import zipfile

import openpyxl
from openpyxl.chart import LineChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from dora.engine import fortnightly_rate, optimize
from dora.scenario import Scenario, normalize_region
from dora.tools import PARAMETERS, break_even_prices, evaluate_season, shadow_prices
from dora.version import ENGINE_VERSION, engine_fingerprint
from mcp_server.provenance import sha256_canonical

logger = logging.getLogger("dora.spreadsheet")

# Styling definitions
FONT_FAMILY = "Segoe UI"
HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
HEADER_FONT = Font(name=FONT_FAMILY, size=11, bold=True, color="FFFFFF")
WARNING_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
WARNING_FONT = Font(name=FONT_FAMILY, size=11, bold=True, color="7F6000")
INPUT_FILL = PatternFill(start_color="FFFFCC", end_color="FFFFCC", fill_type="solid")
DECISION_FILL = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
DECISION_FONT = Font(name=FONT_FAMILY, size=10, italic=True, color="595959")
BOLD_FONT = Font(name=FONT_FAMILY, size=10, bold=True)
REGULAR_FONT = Font(name=FONT_FAMILY, size=10)

THIN_SIDE = Side(border_style="thin", color="D9D9D9")
CELL_BORDER = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)

FMT_CURRENCY = "$#,##0.00"
FMT_INTEGER = "#,##0"
FMT_HECTARES = "#,##0.0"
FMT_YIELD = "0.00"
FMT_PERCENT = "0.0%"


def _get_sheet_names(lang: str) -> dict[str, str]:
    if lang == "en":
        return {
            "summary": "Summary",
            "crops": "Plan by crop",
            "cash": "Cash by fortnight",
            "assumptions": "Assumptions",
            "sensitivity": "Sensitivity",
            "verification": "Verification",
            "dora": "_dora",
        }
    return {
        "summary": "Resumen",
        "crops": "Plan por cultivo",
        "cash": "Caja por quincena",
        "assumptions": "Supuestos",
        "sensitivity": "Sensibilidad",
        "verification": "Verificación",
        "dora": "_dora",
    }


def export_plan_xlsx(
    scenario: dict[str, Any],
    lang: str = "es",
    record: dict | None = None,
) -> bytes:
    """Validate and solve the scenario, generating a 7-sheet .xlsx workbook with live formulas.
    Raises ValueError for stochastic climate scenarios.
    """
    if scenario.get("climate_scenarios"):
        err_msg = (
            "El exportador a planilla no está disponible para escenarios climáticos estocásticos."
            if lang == "es"
            else "Spreadsheet export is not available with stochastic climate scenarios."
        )
        raise ValueError(err_msg)

    sc_clean = {k: v for k, v in scenario.items() if k not in ("costs_origin", "costs_source", "document_date", "invoice_date")}
    sc = Scenario(**sc_clean)
    res = optimize(sc)

    wb = openpyxl.Workbook()
    sheet_names = _get_sheet_names(lang)

    from dora.tools import regional_source_label
    reg_source = regional_source_label(sc.region)
    farmer_lbl = "lo dijo el productor" if lang == "es" else "farmer"
    supp_lbl = "supuesto" if lang == "es" else "assumption"

    # -------------------------------------------------------------
    # Sheet 4: Supuestos / Assumptions (created first for formula refs)
    # -------------------------------------------------------------
    ws_assump = wb.active
    ws_assump.title = sheet_names["assumptions"]

    headers_assump = (
        ["Clave", "Descripción", "Valor", "Unidad", "Origen", "Editado"]
        if lang == "es"
        else ["Key", "Description", "Value", "Unit", "Origin", "Edited"]
    )
    ws_assump.append(headers_assump)
    for col in range(1, 7):
        cell = ws_assump.cell(row=1, column=col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")

    assump_cells: dict[str, int] = {}  # key -> row number in ws_assump

    # Base parameters
    assump_rows = [
        ("area_ha", "Superficie total" if lang == "es" else "Total area", sc.area_ha, "ha", farmer_lbl if "area_ha" in scenario else reg_source),
        ("owned_ha", "Superficie propia" if lang == "es" else "Owned area", sc.owned, "ha", farmer_lbl if "owned_ha" in scenario else reg_source),
        ("own_capital_usd", "Capital propio inicial" if lang == "es" else "Initial own capital", sc.own_capital_usd, "USD", farmer_lbl if "own_capital_usd" in scenario else reg_source),
        ("credit_line_usd", "Límite línea de crédito" if lang == "es" else "Credit line limit", sc.credit_line_usd, "USD", farmer_lbl if "credit_line_usd" in scenario else reg_source),
        ("credit_rate_annual", "Tasa anual crédito" if lang == "es" else "Annual credit rate", sc.credit_rate_annual, "anual", supp_lbl),
        ("deposit_rate_annual", "Tasa anual colocación" if lang == "es" else "Annual deposit rate", sc.deposit_rate_annual, "anual", supp_lbl),
        ("freight_usd_t", "Flete a puerto" if lang == "es" else "Freight to port", sc.freight_usd_t, "USD/t", farmer_lbl if "freight_usd_t" in scenario else reg_source),
        ("regional_rent_usd_ha", "Alquiler regional" if lang == "es" else "Regional rent", sc.regional_rent_usd_ha, "USD/ha", farmer_lbl if "regional_rent_usd_ha" in scenario else reg_source),
        ("land_tax_usd_ha_year", "Impuesto inmobiliario" if lang == "es" else "Land property tax", sc.land_tax_usd_ha_year, "USD/ha/año", farmer_lbl if "land_tax_usd_ha_year" in scenario else reg_source),
        ("ri_fortnightly", "Tasa quincenal colocación" if lang == "es" else "Fortnightly deposit rate", fortnightly_rate(sc.deposit_rate_annual), "quincenal", "cálculo motor"),
        ("rc_fortnightly", "Tasa quincenal crédito" if lang == "es" else "Fortnightly credit rate", fortnightly_rate(sc.credit_rate_annual), "quincenal", "cálculo motor"),
    ]

    # Per-crop parameters: yield, price, and costs
    costs_origin_map = scenario.get("costs_origin") or {}
    for c in sc.crops:
        c_yield = sc.crop_yield(c)
        c_price = sc.price(c)
        y_origin = farmer_lbl if c in (scenario.get("yields") or {}) else reg_source
        if c in (scenario.get("prices") or {}):
            p_origin = farmer_lbl
        elif sc.price_curve_source:
            p_origin = f"{sc.price_curve_metadata.get('source', 'curva de precios')}, as of {sc.price_curve_metadata.get('as_of', '')}"
        else:
            p_origin = reg_source

        assump_rows.append((f"yields.{c}", f"Rendimiento {c}" if lang == "es" else f"Yield {c}", c_yield, "t/ha", y_origin))
        assump_rows.append((f"prices.{c}", f"Precio cosecha {c}" if lang == "es" else f"Harvest price {c}", c_price, "USD/t", p_origin))

        # Cost components
        for item in ("seed", "fertilizer", "crop_protection", "field_operations", "marketing_harvest"):
            val = sc._cost(c, item)
            item_orig = costs_origin_map.get(f"{c}.{item}")
            if not item_orig:
                if c in (scenario.get("costs_override") or {}) and item in scenario["costs_override"][c]:
                    if scenario.get("document_date") or scenario.get("invoice_date"):
                        item_orig = f"factura {scenario.get('document_date') or scenario.get('invoice_date')}"
                    elif scenario.get("costs_source"):
                        item_orig = scenario["costs_source"]
                    else:
                        item_orig = "factura"
                else:
                    item_orig = reg_source
            assump_rows.append((f"costs.{c}.{item}", f"Costo {item} {c}" if lang == "es" else f"Cost {item} {c}", float(val), "USD/ha", item_orig))

    for k, desc, val, unit, origin in assump_rows:
        row_idx = ws_assump.max_row + 1
        assump_cells[k] = row_idx
        ws_assump.append([k, desc, val, unit, origin, ""])
        c_val = ws_assump.cell(row=row_idx, column=3)
        c_val.fill = INPUT_FILL
        c_val.font = BOLD_FONT
        if unit in ("USD", "USD/ha", "USD/t"):
            c_val.number_format = FMT_CURRENCY
        elif unit in ("anual", "quincenal"):
            c_val.number_format = "0.0000%"
        elif unit == "ha":
            c_val.number_format = FMT_HECTARES
        elif unit == "t/ha":
            c_val.number_format = FMT_YIELD

    # -------------------------------------------------------------
    # Sheet 1: Resumen / Summary
    # -------------------------------------------------------------
    ws_sum = wb.create_sheet(title=sheet_names["summary"], index=0)
    # Warning Box
    warning_text = (
        "Este plan era el óptimo con estos supuestos. Si cambiás algo, pedile a DORA que recalcule: mandá esta planilla por el chat."
        if lang == "es"
        else "This plan was the best one under these assumptions. If you change anything, ask DORA to recompute: send this file back in the chat."
    )
    ws_sum.merge_cells("A1:G2")
    w_cell = ws_sum.cell(row=1, column=1, value=warning_text)
    w_cell.fill = WARNING_FILL
    w_cell.font = WARNING_FONT
    w_cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    ws_sum.cell(row=4, column=1, value="PLAN AGRONÓMICO PROPUESTO" if lang == "es" else "PROPOSED AGRONOMIC PLAN").font = Font(name=FONT_FAMILY, size=14, bold=True, color="1F4E78")

    # Table of sowing decisions
    headers_crops_sum = (
        ["Cultivo", "Ventana", "Hectáreas", "Producción (t)", "Margen Total (USD)"]
        if lang == "es"
        else ["Crop", "Window", "Hectares", "Production (t)", "Total Margin (USD)"]
    )
    ws_sum.append([])
    ws_sum.append(headers_crops_sum)
    header_row_sum = ws_sum.max_row
    for col in range(1, 6):
        c_h = ws_sum.cell(row=header_row_sum, column=col)
        c_h.fill = HEADER_FILL
        c_h.font = HEADER_FONT

    active_crops = [c for c in sc.crops if res.hectares.get(c, 0.0) > 0.01]
    crop_rows_in_plan_sheet: dict[str, int] = {}
    plan_sheet_name = sheet_names["crops"]

    for c in active_crops:
        r_idx = ws_sum.max_row + 1
        crop_rows_in_plan_sheet[c] = len(crop_rows_in_plan_sheet) + 2  # Row in Plan by crop sheet
        ha_val = res.hectares[c]
        ws_sum.append([
            c,
            "Óptima" if lang == "es" else "Optimal",
            ha_val,
            f"='{plan_sheet_name}'!D{crop_rows_in_plan_sheet[c]}",
            f"='{plan_sheet_name}'!I{crop_rows_in_plan_sheet[c]}",
        ])
        ws_sum.cell(row=r_idx, column=3).number_format = FMT_HECTARES
        ws_sum.cell(row=r_idx, column=4).number_format = FMT_INTEGER
        ws_sum.cell(row=r_idx, column=5).number_format = FMT_CURRENCY

    # KPIs
    ws_sum.append([])
    kpi_start_row = ws_sum.max_row + 1
    ws_sum.cell(row=kpi_start_row, column=1, value="MÉTRICAS CLAVE DEL PLAN" if lang == "es" else "KEY PLAN METRICS").font = Font(name=FONT_FAMILY, size=12, bold=True)

    cash_sheet_name = sheet_names["cash"]
    T_fortnights = len(res.cash)
    cash_last_row = T_fortnights + 1  # header is row 1, fortnight 0 is row 2, T-1 is T+1
    ri_cell = f"'{sheet_names['assumptions']}'!C{assump_cells['ri_fortnightly']}"

    # VNP formula discounting final wealth
    npv_formula = f"=('{cash_sheet_name}'!N{cash_last_row} - '{cash_sheet_name}'!O{cash_last_row}) / ((1 + {ri_cell})^{T_fortnights - 1})"

    metrics_rows = [
        ("Valor Neto Actual (VNP)" if lang == "es" else "Net Present Value (NPV)", npv_formula, FMT_CURRENCY),
        ("Retorno sobre capital" if lang == "es" else "Return on capital", res.return_on_capital, FMT_PERCENT),
        ("Máximo crédito tomado" if lang == "es" else "Peak credit used", max(res.debt) if res.debt else 0.0, FMT_CURRENCY),
    ]

    for label, val, fmt in metrics_rows:
        r_idx = ws_sum.max_row + 1
        ws_sum.append([label, val])
        ws_sum.cell(row=r_idx, column=1).font = BOLD_FONT
        c_v = ws_sum.cell(row=r_idx, column=2)
        c_v.font = BOLD_FONT
        c_v.number_format = fmt

    # Tenure comparison (if owned)
    if sc.owned > 0:
        ws_sum.append([])
        ws_sum.cell(row=ws_sum.max_row + 1, column=1, value="COMPARACIÓN DE TENENCIA (ALQUILER)" if lang == "es" else "TENURE COMPARISON (RENT OUT)").font = Font(name=FONT_FAMILY, size=11, bold=True)
        rent_all_usd = sc.owned * sc.regional_rent_usd_ha
        farm_npv = res.npv
        ws_sum.append(["Opción" if lang == "es" else "Option", "Resultado (USD)" if lang == "es" else "Result (USD)"])
        ws_sum.append(["Solo sembrar" if lang == "es" else "Farming only", farm_npv])
        ws_sum.append(["Alquilar todo" if lang == "es" else "Rent all out", rent_all_usd])
        ws_sum.cell(row=ws_sum.max_row - 1, column=2).number_format = FMT_CURRENCY
        ws_sum.cell(row=ws_sum.max_row, column=2).number_format = FMT_CURRENCY

    # Binding resources
    ws_sum.append([])
    ws_sum.cell(row=ws_sum.max_row + 1, column=1, value="RECURSOS QUE LIMITAN EL PLAN" if lang == "es" else "RESOURCES LIMITING THE PLAN").font = Font(name=FONT_FAMILY, size=11, bold=True)
    ws_sum.append(["Tierra propia" if lang == "es" else "Owned land", f"{res.land_shadow_price:.2f} USD/ha"])
    if res.capital_shadow_price > 0.001:
        ws_sum.append(["Capital inicial" if lang == "es" else "Initial capital", f"{res.capital_shadow_price:.2f} USD/USD"])

    # -------------------------------------------------------------
    # Sheet 2: Plan por cultivo / Plan by crop
    # -------------------------------------------------------------
    ws_crops = wb.create_sheet(title=sheet_names["crops"], index=1)
    headers_crops = (
        ["Cultivo", "Hectáreas", "Rendimiento (t/ha)", "Producción (t)", "Precio Promedio (USD/t)", "Costo (USD/ha)", "Ingreso Bruto (USD)", "Costo Total (USD)", "Margen Bruto (USD)", "Margen (USD/ha)"]
        if lang == "es"
        else ["Crop", "Hectares", "Yield (t/ha)", "Production (t)", "Avg Price (USD/t)", "Cost (USD/ha)", "Gross Income (USD)", "Total Cost (USD)", "Gross Margin (USD)", "Margin (USD/ha)"]
    )
    ws_crops.append(headers_crops)
    for col in range(1, 11):
        c_h = ws_crops.cell(row=1, column=col)
        c_h.fill = HEADER_FILL
        c_h.font = HEADER_FONT
        c_h.alignment = Alignment(horizontal="center")

    assump_name = sheet_names["assumptions"]
    crop_rows_start = 2
    for c in active_crops:
        r = ws_crops.max_row + 1
        ha_val = res.hectares[c]
        y_ref = f"'{assump_name}'!C{assump_cells[f'yields.{c}']}"
        p_ref = f"'{assump_name}'!C{assump_cells[f'prices.{c}']}"

        cost_cells = [f"'{assump_name}'!C{assump_cells[f'costs.{c}.{item}']}" for item in ("seed", "fertilizer", "crop_protection", "field_operations", "marketing_harvest")]
        cost_sum_formula = f"={'+'.join(cost_cells)}"

        # Tonnes = B * C
        # Cost per ha = formula
        # Gross income = D * E
        # Total cost = B * F
        # Margin = G - H
        # Margin per ha = I / B
        ws_crops.append([
            c,
            ha_val,
            f"={y_ref}",
            f"=B{r}*C{r}",
            f"={p_ref}",
            cost_sum_formula,
            f"=D{r}*E{r}",
            f"=B{r}*F{r}",
            f"=G{r}-H{r}",
            f"=I{r}/B{r}",
        ])
        ws_crops.cell(row=r, column=2).number_format = FMT_HECTARES
        ws_crops.cell(row=r, column=2).fill = DECISION_FILL
        ws_crops.cell(row=r, column=3).number_format = FMT_YIELD
        ws_crops.cell(row=r, column=4).number_format = FMT_INTEGER
        ws_crops.cell(row=r, column=5).number_format = FMT_CURRENCY
        ws_crops.cell(row=r, column=6).number_format = FMT_CURRENCY
        ws_crops.cell(row=r, column=7).number_format = FMT_CURRENCY
        ws_crops.cell(row=r, column=8).number_format = FMT_CURRENCY
        ws_crops.cell(row=r, column=9).number_format = FMT_CURRENCY
        ws_crops.cell(row=r, column=10).number_format = FMT_CURRENCY

    # Total row
    last_crop_row = ws_crops.max_row
    tot_row = last_crop_row + 1
    ws_crops.append([
        "TOTAL",
        f"=SUM(B{crop_rows_start}:B{last_crop_row})",
        "",
        f"=SUM(D{crop_rows_start}:D{last_crop_row})",
        "",
        "",
        f"=SUM(G{crop_rows_start}:G{last_crop_row})",
        f"=SUM(H{crop_rows_start}:H{last_crop_row})",
        f"=SUM(I{crop_rows_start}:I{last_crop_row})",
        f"=I{tot_row}/B{tot_row}",
    ])
    for col in range(1, 11):
        cell = ws_crops.cell(row=tot_row, column=col)
        cell.font = BOLD_FONT
        if col in (2, 4):
            cell.number_format = FMT_HECTARES if col == 2 else FMT_INTEGER
        elif col in (7, 8, 9, 10):
            cell.number_format = FMT_CURRENCY

    # -------------------------------------------------------------
    # Sheet 3: Caja por quincena / Cash by fortnight
    # -------------------------------------------------------------
    ws_cash = wb.create_sheet(title=sheet_names["cash"], index=2)
    headers_cash = (
        ["Quincena", "Saldo Inicial", "Insumos", "Ventas", "Ventas a término", "Silos Entrada", "Silos Mensual", "Alquiler Pagado", "Alquiler Cobrado", "Interés Colocación", "Interés Deuda", "Crédito Tomado", "Crédito Cancelado", "Saldo Final", "Deuda Acumulada"]
        if lang == "es"
        else ["Fortnight", "Opening Cash", "Inputs", "Sales", "Forward Sales", "Storage Fill", "Storage Monthly", "Rent In", "Rent Out", "Deposit Interest", "Credit Interest", "Credit Drawn", "Credit Repaid", "Closing Cash", "Debt"]
    )
    ws_cash.append(headers_cash)
    for col in range(1, 16):
        c_h = ws_cash.cell(row=1, column=col)
        c_h.fill = HEADER_FILL
        c_h.font = HEADER_FONT
        c_h.alignment = Alignment(horizontal="center")

    own_cap_cell = f"'{assump_name}'!C{assump_cells['own_capital_usd']}"
    land_tax_cell = f"'{assump_name}'!C{assump_cells['land_tax_usd_ha_year']}"
    owned_ha_cell = f"'{assump_name}'!C{assump_cells['owned_ha']}"
    ri_cell = f"'{assump_name}'!C{assump_cells['ri_fortnightly']}"
    rc_cell = f"'{assump_name}'!C{assump_cells['rc_fortnightly']}"

    for p in range(T_fortnights):
        r = p + 2  # Row in ws_cash
        lbl = f"Q{p+1}"

        # Opening cash formula
        if p == 0:
            open_formula = f"={own_cap_cell} - {land_tax_cell} * {owned_ha_cell}"
        else:
            open_formula = f"=N{r - 1}"

        # Group flows from cash_ledger
        ledger_p = res.cash_ledger[p] if p < len(res.cash_ledger) else {}
        flow_inputs = sum(ledger_p.get("inputs", {}).values())

        # Sales formula: live formula referencing Supuestos prices
        sales_p = ledger_p.get("sales", {})
        if not sales_p:
            flow_sales = 0.0
        else:
            terms = []
            for c, cash_amt in sales_p.items():
                t_sold = float(res.sales.get(c, {}).get(p, 0.0))
                if t_sold > 1e-6 and f"prices.{c}" in assump_cells:
                    c_price = sc.price(c)
                    net_p = cash_amt / t_sold
                    ded = c_price - net_p
                    p_cell = f"'{assump_name}'!C{assump_cells[f'prices.{c}']}"
                    if abs(ded) < 1e-6:
                        terms.append(f"{t_sold:.6f}*{p_cell}")
                    elif ded > 0:
                        terms.append(f"{t_sold:.6f}*({p_cell}-{ded:.6f})")
                    else:
                        terms.append(f"{t_sold:.6f}*({p_cell}+{-ded:.6f})")
                else:
                    terms.append(f"{cash_amt:.2f}")
            flow_sales = f"={'+'.join(terms)}"

        flow_fwd = sum(ledger_p.get("forward_sales", {}).values())
        flow_silo_fill = sum(ledger_p.get("storage_fill", {}).values())
        flow_silo_m = sum(ledger_p.get("storage_monthly", {}).values())
        flow_rent_in = sum(ledger_p.get("rent_in", {}).values())
        flow_rent_out = sum(ledger_p.get("rent_out", {}).values())

        # Interest formulas
        if p == 0:
            dep_int_formula = 0.0
            cred_int_formula = 0.0
        else:
            dep_int_formula = f"=N{r - 1} * {ri_cell}"
            cred_int_formula = f"=O{r - 1} * {rc_cell}"

        # Decisions: credit drawn and repaid (values)
        cr_drawn = res.credit_drawn[p] if p < len(res.credit_drawn) else 0.0
        cr_repaid = res.credit_repaid[p] if p < len(res.credit_repaid) else 0.0

        # Closing cash formula: Opening + Deposit_Interest - Credit_Interest + Flows + Credit_Drawn - Credit_Repaid
        closing_formula = f"=B{r}+J{r}-K{r}+C{r}+D{r}+E{r}+F{r}+G{r}+H{r}+I{r}+L{r}-M{r}"

        # Debt formula: Prev_Debt + Credit_Drawn - Credit_Repaid
        if p == 0:
            debt_formula = f"=L{r}-M{r}"
        else:
            debt_formula = f"=O{r - 1}+L{r}-M{r}"

        ws_cash.append([
            lbl,
            open_formula,
            flow_inputs,
            flow_sales,
            flow_fwd,
            flow_silo_fill,
            flow_silo_m,
            flow_rent_in,
            flow_rent_out,
            dep_int_formula,
            cred_int_formula,
            cr_drawn,
            cr_repaid,
            closing_formula,
            debt_formula,
        ])

        for col in range(2, 16):
            cell = ws_cash.cell(row=r, column=col)
            cell.number_format = FMT_CURRENCY
            if col in (12, 13):
                cell.fill = DECISION_FILL

    # Add openpyxl LineChart to Sheet 3
    chart = LineChart()
    chart.title = "Evolución de Caja y Deuda" if lang == "es" else "Cash and Debt Evolution"
    chart.style = 13
    chart.y_axis.title = "USD"
    chart.x_axis.title = "Quincena" if lang == "es" else "Fortnight"
    chart.width = 18
    chart.height = 10

    data_ref = Reference(ws_cash, min_col=14, min_row=1, max_col=15, max_row=T_fortnights + 1)
    cats_ref = Reference(ws_cash, min_col=1, min_row=2, max_row=T_fortnights + 1)
    chart.add_data(data_ref, titles_from_data=True)
    chart.set_categories(cats_ref)
    ws_cash.add_chart(chart, "Q2")

    # -------------------------------------------------------------
    # Sheet 5: Sensibilidad / Sensitivity
    # -------------------------------------------------------------
    ws_sens = wb.create_sheet(title=sheet_names["sensitivity"], index=4)
    ws_sens.cell(row=1, column=1, value="ANÁLISIS DE SENSIBILIDAD Y PRECIOS DE INDIFERENCIA" if lang == "es" else "SENSITIVITY & BREAK-EVEN ANALYSIS").font = Font(name=FONT_FAMILY, size=13, bold=True)
    ws_sens.cell(row=2, column=1, value="Valen para un cambio chico, con todo lo demás igual." if lang == "es" else "Valid for a small change, all else equal.").font = DECISION_FONT

    ws_sens.cell(row=4, column=1, value="PRECIOS SOMBRA DE RECURSOS" if lang == "es" else "RESOURCE SHADOW PRICES").font = BOLD_FONT
    sp_headers = ["Recurso", "Precio Sombra", "Unidad"] if lang == "es" else ["Resource", "Shadow Price", "Unit"]
    ws_sens.append([])
    ws_sens.append(sp_headers)
    ws_sens.append(["Tierra propia", res.land_shadow_price, "USD/ha"])
    ws_sens.append(["Capital propio inicial", res.capital_shadow_price, "USD/USD"])
    ws_sens.cell(row=ws_sens.max_row - 1, column=2).number_format = FMT_CURRENCY
    ws_sens.cell(row=ws_sens.max_row, column=2).number_format = "0.0000"

    # Break-even prices for unchosen crops
    ws_sens.append([])
    ws_sens.cell(row=ws_sens.max_row + 1, column=1, value="PRECIOS DE INDIFERENCIA (CULTIVOS FUERA DEL PLAN)" if lang == "es" else "BREAK-EVEN PRICES (CROPS NOT IN PLAN)").font = BOLD_FONT
    be_headers = (
        ["Cultivo", "Mejor Quincena", "Precio Actual", "Precio Necesario", "Suba Requerida %", "Verificado"]
        if lang == "es"
        else ["Crop", "Best Fortnight", "Current Price", "Needed Price", "Required Rise %", "Verified"]
    )
    ws_sens.append(be_headers)
    try:
        be_res = break_even_prices(scenario, lang=lang)
        for be in be_res.get("break_even", []):
            ws_sens.append([
                be.get("crop"),
                be.get("fortnight_label", be.get("fortnight")),
                be.get("current_price"),
                be.get("break_even_price"),
                be.get("required_rise_pct", 0.0) / 100.0,
                "Sí" if be.get("verified") else "No",
            ])
            ws_sens.cell(row=ws_sens.max_row, column=3).number_format = FMT_CURRENCY
            ws_sens.cell(row=ws_sens.max_row, column=4).number_format = FMT_CURRENCY
            ws_sens.cell(row=ws_sens.max_row, column=5).number_format = FMT_PERCENT
    except Exception as e:
        logger.warning("Could not calculate break-even prices for spreadsheet: %s", e)

    # -------------------------------------------------------------
    # Sheet 6: Verificación / Verification
    # -------------------------------------------------------------
    ws_verif = wb.create_sheet(title=sheet_names["verification"], index=5)
    ws_verif.cell(row=1, column=1, value="VERIFICACIÓN Y PROCEDENCIA CRIPTOGRÁFICA" if lang == "es" else "VERIFICATION & CRYPTOGRAPHIC PROVENANCE").font = Font(name=FONT_FAMILY, size=13, bold=True)

    import dataclasses
    from dora.tools import _validate, evaluate_season
    sc_obj, _ = _validate(sc_clean)
    sc_val = dataclasses.asdict(sc_obj)
    res_eval = evaluate_season(sc_clean, lang=lang)
    fp = engine_fingerprint()
    sc_hash = sha256_canonical(sc_val)
    res_hash = sha256_canonical(res_eval)

    verif_rows = [
        ("Versión del motor" if lang == "es" else "Engine version", ENGINE_VERSION),
        ("Huella digital del motor" if lang == "es" else "Engine fingerprint", fp),
        ("Hash del escenario" if lang == "es" else "Scenario hash", sc_hash),
        ("Hash del resultado" if lang == "es" else "Result hash", res_hash),
        ("Fecha de generación" if lang == "es" else "Generation date", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")),
    ]

    for lbl, v in verif_rows:
        ws_verif.append([lbl, v])
        ws_verif.cell(row=ws_verif.max_row, column=1).font = BOLD_FONT

    ws_verif.append([])
    ws_verif.cell(row=ws_verif.max_row + 1, column=1, value="REGISTRO ON-CHAIN (EAS EN BASE)" if lang == "es" else "ON-CHAIN RECORD (EAS ON BASE)").font = BOLD_FONT

    if record:
        status_rec = record.get("status", "unknown")
        if status_rec == "published":
            uid = record.get("attestation_uid", "")
            ws_verif.append(["Estado", "Publicado en Base Sepolia" if lang == "es" else "Published on Base Sepolia"])
            ws_verif.append(["Record Hash", record.get("record_hash", "")])
            ws_verif.append(["UID Atestación", uid])
            ws_verif.append(["EAS Scan", f"https://base-sepolia.easscan.org/attestation/view/{uid}"])
        elif status_rec == "queued":
            ws_verif.append(["Estado", "Registro en cola" if lang == "es" else "Record queued"])
            ws_verif.append(["ID de registro", record.get("record_id", "")])
        else:
            ws_verif.append(["Estado", status_rec])
    else:
        ws_verif.append(["Estado", "sin registro on-chain" if lang == "es" else "no on-chain record"])

    ws_verif.append([])
    ws_verif.cell(row=ws_verif.max_row + 1, column=1, value="Cualquiera puede verificar este plan con dora_chain.verify_record" if lang == "es" else "Anyone can verify this plan using dora_chain.verify_record").font = DECISION_FONT

    # -------------------------------------------------------------
    # Sheet 7: _dora (hidden metadata)
    # -------------------------------------------------------------
    ws_dora = wb.create_sheet(title=sheet_names["dora"], index=6)
    ws_dora.sheet_state = "hidden"
    dora_payload = {
        "scenario": sc_val,
        "scenario_input": sc_clean,
        "scenario_hash": sc_hash,
        "result_hash": res_hash,
        "engine_version": ENGINE_VERSION,
        "export_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    ws_dora["A1"] = json.dumps(dora_payload)

    # Auto-adjust column widths on all sheets
    for ws in (ws_sum, ws_crops, ws_cash, ws_assump, ws_sens, ws_verif):
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 40)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def read_plan_xlsx(data: bytes, lang: str = "es") -> dict[str, Any]:
    """Read a modified .xlsx plan file, validating origin and input constraints.
    Rejects .xlsm, .csv, files > 5MB, or tampered _dora sheets.
    Evaluates season with new scenario and computes delta.
    """
    if len(data) > 5 * 1024 * 1024:
        err = "El archivo supera el límite de 5 MB." if lang == "es" else "File exceeds 5 MB limit."
        return {"error": "file_too_large", "message": err}

    # Verify zip / xlsx header
    if not data.startswith(b"PK"):
        err = (
            "Formato no válido. Solo se admiten archivos Excel .xlsx (no se admiten macros .xlsm ni .csv)."
            if lang == "es"
            else "Invalid format. Only .xlsx files are supported (no macros .xlsm or .csv)."
        )
        return {"error": "invalid_format", "message": err}

    # Check for macro-enabled workbook (.xlsm)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            if any("vbaProject.bin" in name for name in zf.namelist()):
                err = (
                    "No se admiten archivos con macros (.xlsm). Use formato estándar .xlsx."
                    if lang == "es"
                    else "Macro-enabled workbooks (.xlsm) are not supported. Use standard .xlsx format."
                )
                return {"error": "xlsm_not_allowed", "message": err}
    except Exception as e:
        err = f"Error al abrir el archivo ZIP: {e}"
        return {"error": "corrupt_file", "message": err}

    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    except Exception as e:
        err = f"Error al abrir el archivo Excel: {e}" if lang == "es" else f"Error opening Excel file: {e}"
        return {"error": "cannot_read_excel", "message": err}

    if "_dora" not in wb.sheetnames:
        err = "El archivo no contiene la hoja _dora o no fue generado por DORA." if lang == "es" else "File does not contain the _dora sheet or was not generated by DORA."
        return {"error": "not_dora_file", "message": err}

    # Read and verify _dora metadata
    ws_dora = wb["_dora"]
    raw_json = ws_dora["A1"].value
    try:
        meta = json.loads(str(raw_json))
        orig_sc = dict(meta["scenario"])
        orig_hash = meta["scenario_hash"]
        if sha256_canonical(orig_sc) != orig_hash:
            raise ValueError("Scenario hash mismatch")
    except Exception:
        err = "La hoja _dora fue alterada o el hash del escenario no coincide." if lang == "es" else "The _dora sheet was tampered with or scenario hash does not match."
        return {"error": "tampered_dora", "message": err}

    assump_sheet_name = "Supuestos" if "Supuestos" in wb.sheetnames else "Assumptions"
    if assump_sheet_name not in wb.sheetnames:
        err = "No se encontró la hoja de Supuestos." if lang == "es" else "Assumptions sheet not found."
        return {"error": "missing_assumptions_sheet", "message": err}

    ws_assump = wb[assump_sheet_name]
    sc_base = Scenario(**orig_sc)
    if "scenario_input" in meta and isinstance(meta["scenario_input"], dict):
        base_sc = dict(meta["scenario_input"])
    else:
        base_sc = {k: v for k, v in orig_sc.items() if not k.startswith("_") and k in PARAMETERS and v is not None}
        if "crops" in base_sc and isinstance(base_sc["crops"], (list, tuple)):
            base_sc["crops"] = list(base_sc["crops"])

    new_sc = dict(base_sc)
    changes = []
    rejected = []
    ignored = []
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for row in ws_assump.iter_rows(min_row=2, values_only=True):
        if not row or not row[0]:
            continue
        key = str(row[0]).strip()
        val = row[2]

        if key in ("ri_fortnightly", "rc_fortnightly"):
            continue

        if val is None or (isinstance(val, str) and val.startswith("=")):
            ignored.append({"key": key, "reason": "formula without cached value"})
            continue

        # Look up baseline original value
        if key.startswith("prices."):
            c = key.split(".")[1]
            orig_val = sc_base.price(c)
            param_name = "prices"
        elif key.startswith("yields."):
            c = key.split(".")[1]
            orig_val = sc_base.crop_yield(c)
            param_name = "yields"
        elif key.startswith("costs."):
            parts = key.split(".")
            c, item = parts[1], parts[2]
            orig_val = sc_base._cost(c, item)
            param_name = "costs_override"
        else:
            orig_val = getattr(sc_base, key, None)
            param_name = key

        # Skip unchanged
        val_float: float | None = None
        try:
            val_float = float(val)
            if orig_val is not None and abs(val_float - float(orig_val)) < 1e-6:
                continue
        except (ValueError, TypeError):
            if val == orig_val:
                continue

        # Validate with PARAMETERS
        is_valid = True
        reject_reason = ""

        if param_name == "yields":
            if val_float is None or val_float < 0.1:
                is_valid = False
                reject_reason = "Valor menor al mínimo permitido (0.1)" if lang == "es" else "Value below minimum allowed (0.1)"
            elif val_float > 20.0:
                is_valid = False
                reject_reason = "Valor mayor al máximo permitido (20.0)" if lang == "es" else "Value above maximum allowed (20.0)"
        elif param_name == "prices":
            if val_float is None or val_float < 1.0:
                is_valid = False
                reject_reason = "Valor menor al mínimo permitido (1.0)" if lang == "es" else "Value below minimum allowed (1.0)"
            elif val_float > 2000.0:
                is_valid = False
                reject_reason = "Valor mayor al máximo permitido (2000.0)" if lang == "es" else "Value above maximum allowed (2000.0)"
        elif param_name == "costs_override":
            if val_float is None or val_float < 0.0:
                is_valid = False
                reject_reason = "Valor no puede ser negativo" if lang == "es" else "Value cannot be negative"
        else:
            param_def = PARAMETERS.get(param_name)
            if param_def and val_float is not None:
                expected_type, min_v, max_v, _, _ = param_def
                if min_v is not None and val_float < min_v:
                    is_valid = False
                    reject_reason = f"Valor menor al mínimo permitido ({min_v})" if lang == "es" else f"Value below minimum allowed ({min_v})"
                elif max_v is not None and val_float > max_v:
                    is_valid = False
                    reject_reason = f"Valor mayor al máximo permitido ({max_v})" if lang == "es" else f"Value above maximum allowed ({max_v})"

        if not is_valid:
            rejected.append({"key": key, "value": val, "reason": reject_reason})
            continue

        # Apply valid change to new_sc
        applied_val = val_float if val_float is not None else val
        if param_name == "prices":
            c = key.split(".")[1]
            if "prices" not in new_sc or not isinstance(new_sc["prices"], dict):
                new_sc["prices"] = dict(base_sc.get("prices") or {})
            new_sc["prices"][c] = applied_val
        elif param_name == "yields":
            c = key.split(".")[1]
            if "yields" not in new_sc or not isinstance(new_sc["yields"], dict):
                new_sc["yields"] = dict(base_sc.get("yields") or {})
            new_sc["yields"][c] = applied_val
        elif param_name == "costs_override":
            parts = key.split(".")
            c, item = parts[1], parts[2]
            if "costs_override" not in new_sc or not isinstance(new_sc["costs_override"], dict):
                new_sc["costs_override"] = {k: dict(v) for k, v in (base_sc.get("costs_override") or {}).items()}
            new_sc["costs_override"].setdefault(c, {})[item] = applied_val
        else:
            new_sc[key] = applied_val

        changes.append({"key": key, "before": orig_val, "after": applied_val})

    # Evaluate new plan
    plan_before_eval = evaluate_season(base_sc, lang=lang)
    plan_after_eval = evaluate_season(new_sc, lang=lang)

    plan_before = {
        "hectares": plan_before_eval.get("hectares") or plan_before_eval.get("plan", {}).get("hectares", {}),
        "npv": plan_before_eval.get("npv_usd") or plan_before_eval.get("plan", {}).get("npv_usd"),
        "max_credit": plan_before_eval.get("max_credit_usd") or plan_before_eval.get("plan", {}).get("max_credit_usd"),
        "rent_out_ha": plan_before_eval.get("rent_out_ha", 0.0),
    }

    plan_after = {
        "hectares": plan_after_eval.get("hectares") or plan_after_eval.get("plan", {}).get("hectares", {}),
        "npv": plan_after_eval.get("npv_usd") or plan_after_eval.get("plan", {}).get("npv_usd"),
        "max_credit": plan_after_eval.get("max_credit_usd") or plan_after_eval.get("plan", {}).get("max_credit_usd"),
        "rent_out_ha": plan_after_eval.get("rent_out_ha", 0.0),
    }

    # What changed summary
    ha_before = plan_before["hectares"] or {}
    ha_after = plan_after["hectares"] or {}
    all_crops = sorted(set(ha_before.keys()) | set(ha_after.keys()))
    hectares_moved = {}
    crops_in = []
    crops_out = []

    for c in all_crops:
        hb = ha_before.get(c, 0.0)
        ha = ha_after.get(c, 0.0)
        delta = round(ha - hb, 1)
        if abs(delta) > 0.05:
            hectares_moved[c] = delta
        if hb < 0.01 and ha >= 0.01:
            crops_in.append(c)
        elif hb >= 0.01 and ha < 0.01:
            crops_out.append(c)

    npv_diff = round(float(plan_after["npv"] or 0.0) - float(plan_before["npv"] or 0.0), 2)
    what_changed = {
        "crops_in": crops_in,
        "crops_out": crops_out,
        "hectares_moved": hectares_moved,
        "npv_diff_usd": npv_diff,
    }

    # Export new plan file
    from dora.tools import export_plan_spreadsheet
    new_export = export_plan_spreadsheet(new_sc, lang=lang)

    return {
        "changes": changes,
        "rejected": rejected,
        "ignored": ignored,
        "plan_before": plan_before,
        "plan_after": plan_after,
        "what_changed": what_changed,
        "scenario": new_sc,
        "file": new_export.get("file"),
        "file_name": new_export.get("file_name"),
    }
