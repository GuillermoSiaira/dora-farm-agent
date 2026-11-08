"""Spreadsheet export and round-trip import for DORA agricultural plans (SPEC-42 & SPEC-45).

Exports a 9-sheet workbook (Summary, Plan by crop, Sales strategy, Cash by fortnight, Assumptions,
Model, Sensitivity, Verification, and hidden _dora and __OpenSolver__) with live formulas,
re-optimization via OpenSolver/Excel Solver, economic checks, and cryptographic provenance.
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
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName

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

OK_FILL = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
OK_FONT = Font(name=FONT_FAMILY, size=10, bold=True, color="385723")
ERROR_FILL = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
ERROR_FONT = Font(name=FONT_FAMILY, size=10, bold=True, color="C00000")

THIN_SIDE = Side(border_style="thin", color="D9D9D9")
CELL_BORDER = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)

FMT_CURRENCY = "$#,##0.00"
FMT_INTEGER = "#,##0"
FMT_HECTARES = "#,##0.0"
FMT_YIELD = "0.00"
FMT_PERCENT = "0.0%"


FORMULA_LINKED_INPUTS = [
    "prices",
    "yields",
    "own_capital_usd",
    "owned_ha",
    "credit_line_usd",
    "costs",
    "freight_usd_t",
    "land_tax_usd_ha_year",
    "regional_rent_usd_ha",
]

VALUE_ONLY_INPUTS = [
    "credit_rate_annual",
    "deposit_rate_annual",
    "area_ha",
    "sowing_windows",
    "storage_options",
    "routes",
    "livestock",
    "payment_options",
    "constraints",
]

def is_formula_linked(key: str) -> bool:
    base = key.split(".")[0]
    return base in FORMULA_LINKED_INPUTS

def is_value_only(key: str) -> bool:
    base = key.split(".")[0]
    return base in VALUE_ONLY_INPUTS

def _get_sheet_names(lang: str) -> dict[str, str]:
    if lang == "en":
        return {
            "summary": "Summary",
            "crops": "Plan by crop",
            "sales": "Sales strategy",
            "cash": "Cash by fortnight",
            "assumptions": "Assumptions",
            "model": "Model",
            "sensitivity": "Sensitivity",
            "verification": "Verification",
            "dora": "_dora",
        }
    return {
        "summary": "Resumen",
        "crops": "Plan por cultivo",
        "sales": "Estrategia de venta",
        "cash": "Caja por quincena",
        "assumptions": "Supuestos",
        "model": "Modelo",
        "sensitivity": "Sensibilidad",
        "verification": "Verificación",
        "dora": "_dora",
    }


def _build_model_sheet(
    wb: openpyxl.Workbook,
    ws_assump: Any,
    lp: Any,
    sc: Scenario,
    res: Any,
    sheet_names: dict[str, str],
    assump_cells: dict[str, int],
    lang: str = "es",
) -> list[str]:
    model_title = sheet_names["model"]
    assump_title = sheet_names["assumptions"]
    ws_model = wb.create_sheet(title=model_title, index=5)

    N = len(lp.c)
    col_end = 2 + N
    col_end_letter = get_column_letter(col_end)
    col_lhs = col_end + 1
    col_lhs_letter = get_column_letter(col_lhs)
    col_sense = col_end + 2
    col_sense_letter = get_column_letter(col_sense)
    col_rhs = col_end + 3
    col_rhs_letter = get_column_letter(col_rhs)
    col_sp = col_end + 4
    col_sp_letter = get_column_letter(col_sp)

    desc_col_a = "Descripción" if lang == "es" else "Description"
    desc_col_b = "Variable" if lang == "es" else "Variable"
    key_col_a = "Clave" if lang == "es" else "Key"
    key_col_b = "Identificador" if lang == "es" else "Identifier"

    # Row 1: Descriptions
    var_descs = [lp.var_labels[j]["desc_es" if lang == "es" else "desc_en"] for j in range(N)]
    ws_model.append([desc_col_a, desc_col_b] + var_descs)
    for col in range(1, col_end + 1):
        c_h = ws_model.cell(row=1, column=col)
        c_h.fill = HEADER_FILL
        c_h.font = HEADER_FONT

    # Row 2: Keys
    var_keys = [lp.var_labels[j]["key"] for j in range(N)]
    ws_model.append([key_col_a, key_col_b] + var_keys)
    for col in range(1, col_end + 1):
        c_h = ws_model.cell(row=2, column=col)
        c_h.fill = HEADER_FILL
        c_h.font = HEADER_FONT

    # Row 3: Decision cells (dora_vars)
    plan_lbl_a = "Valor del plan" if lang == "es" else "Plan value"
    plan_lbl_b = "Decisión" if lang == "es" else "Decision"
    ws_model.append([plan_lbl_a, plan_lbl_b] + [float(lp.x[j]) for j in range(N)])
    ws_model.cell(row=3, column=1).font = BOLD_FONT
    ws_model.cell(row=3, column=2).font = BOLD_FONT
    for col in range(3, col_end + 1):
        c_d = ws_model.cell(row=3, column=col)
        c_d.fill = INPUT_FILL
        c_d.font = BOLD_FONT

    # Row 4: Lower bounds
    lb_lbl_a = "Cota inferior" if lang == "es" else "Lower bound"
    lb_lbl_b = "Límite mín." if lang == "es" else "Min limit"
    ws_model.append([lb_lbl_a, lb_lbl_b] + [lp.bounds[j][0] if lp.bounds[j][0] is not None else "" for j in range(N)])

    # Row 5: Upper bounds
    ub_lbl_a = "Cota superior" if lang == "es" else "Upper bound"
    ub_lbl_b = "Límite máx." if lang == "es" else "Max limit"
    ws_model.append([ub_lbl_a, ub_lbl_b] + [lp.bounds[j][1] if lp.bounds[j][1] is not None else "" for j in range(N)])

    # Row 6: Objective coefficients (Maximization: -lp.c)
    obj_lbl_a = "Coeficiente objetivo" if lang == "es" else "Objective coefficient"
    obj_lbl_b = "Maximizando VNP" if lang == "es" else "Maximizing NPV"
    ws_model.append([obj_lbl_a, obj_lbl_b] + [-float(lp.c[j]) for j in range(N)])
    for col in range(3, col_end + 1):
        ws_model.cell(row=6, column=col).font = BOLD_FONT

    # Row 7: Reduced costs (A13)
    rc_lbl_a = "Costo reducido (DORA)" if lang == "es" else "Reduced cost (DORA)"
    rc_lbl_b = "USD/ha"
    rc_vals = [float(lp.reduced_costs[j]) if getattr(lp, "reduced_costs", None) is not None and j < len(lp.reduced_costs) else 0.0 for j in range(N)]
    ws_model.append([rc_lbl_a, rc_lbl_b] + rc_vals)
    ws_model.cell(row=7, column=1).font = BOLD_FONT
    ws_model.cell(row=7, column=2).font = BOLD_FONT
    for col in range(3, col_end + 1):
        c_rc = ws_model.cell(row=7, column=col)
        c_rc.font = BOLD_FONT
        c_rc.number_format = "#,##0.0000"

    # Row 8: Objective cell (dora_objective)
    obj_title = "Valor presente del plan (lo que se maximiza)" if lang == "es" else "Present value of plan (to maximize)"
    obj_formula = f"=SUMPRODUCT(C6:{col_end_letter}6, dora_vars)"
    if abs(lp.obj_constant) > 1e-6:
        obj_formula += f"-{lp.obj_constant:.6f}"
    ws_model.append([obj_title, obj_formula])
    ws_model.cell(row=8, column=1).font = Font(name=FONT_FAMILY, size=11, bold=True, color="1F4E78")
    cell_obj = ws_model.cell(row=8, column=2)
    cell_obj.font = Font(name=FONT_FAMILY, size=12, bold=True)
    cell_obj.number_format = FMT_CURRENCY
    cell_obj.fill = WARNING_FILL

    # OpenSolver guide box at top right
    guide_text = (
        "Para volver a optimizar: Extensiones → OpenSolver → Solve. El modelo ya está cargado.\n"
        "Parámetros OpenSolver: Objetivo = dora_objective (Maximizar) | Variables = dora_vars\n"
        "Restricciones: dora_eq_lhs = dora_eq_rhs | dora_le_lhs <= dora_le_rhs"
        if lang == "es"
        else "To re-optimize: Extensions → OpenSolver → Solve. The model is already loaded.\n"
        "OpenSolver parameters: Objective = dora_objective (Maximise) | Variables = dora_vars\n"
        "Constraints: dora_eq_lhs = dora_eq_rhs | dora_le_lhs <= dora_le_rhs"
    )
    ws_model.cell(row=8, column=4, value=guide_text).font = DECISION_FONT

    # Row 9: Blank
    ws_model.append([])

    # Row 10: Constraint headers
    constr_header = (
        ["Restricción", "Clave"] + [lp.var_labels[j]["key"] for j in range(N)] + ["LHS", "Sentido", "RHS", "Precio sombra (DORA)"]
        if lang == "es"
        else ["Constraint", "Key"] + [lp.var_labels[j]["key"] for j in range(N)] + ["LHS", "Sense", "RHS", "Shadow price (DORA)"]
    )
    ws_model.append(constr_header)
    for col in (1, 2, col_lhs, col_sense, col_rhs, col_sp):
        c_h = ws_model.cell(row=10, column=col)
        c_h.fill = HEADER_FILL
        c_h.font = HEADER_FONT

    M_eq = len(lp.b_eq)
    M_ub = len(lp.b_ub)
    model_formula_cells: list[str] = []

    # Equalities
    for i in range(M_eq):
        r = ws_model.max_row + 1
        rl = lp.row_labels[i]
        grp = rl["group"]
        desc_text = rl["desc_es" if lang == "es" else "desc_en"]
        row_cells = [desc_text, rl["key"]]

        for j in range(N):
            val = lp.A_eq[i, j]
            if abs(val) < 1e-12:
                row_cells.append("")
            else:
                vk = lp.var_labels[j]["key"]
                if grp.startswith("cash[") and vk.startswith("sell["):
                    p_num = int(grp.split("p")[1].rstrip("]"))
                    c_name = vk.split("[")[1].split(",")[0]
                    hp_key = f"net_price.{c_name}.p{p_num}"
                    if hp_key in assump_cells:
                        row_cells.append(f"=-'{assump_title}'!C{assump_cells[hp_key]}")
                        col_letter = get_column_letter(3 + j)
                        model_formula_cells.append(f"'{model_title}'!{col_letter}{r}")
                    else:
                        row_cells.append(float(val))
                elif grp.startswith("harvest_balance[") and (vk.startswith("ha[") or vk.startswith("ha_w[")) and val < 0:
                    c_name = grp.split("[")[1].split(",")[0]
                    row_cells.append(f"=-'{assump_title}'!C{assump_cells[f'yields.{c_name}']}")
                    col_letter = get_column_letter(3 + j)
                    model_formula_cells.append(f"'{model_title}'!{col_letter}{r}")
                else:
                    row_cells.append(float(val))

        # LHS
        row_cells.append(f"=SUMPRODUCT(C{r}:{col_end_letter}{r}, dora_vars)")
        # Sense
        row_cells.append("=")
        # RHS
        if grp == "cash[p0]":
            row_cells.append(f"='{assump_title}'!C{assump_cells['own_capital_usd']} - '{assump_title}'!C{assump_cells['land_tax_usd_ha_year']} * '{assump_title}'!C{assump_cells['owned_ha']}")
        else:
            row_cells.append(float(lp.b_eq[i]))

        # Shadow price (DORA)
        sp_eq = float(lp.duals_eq[i]) if getattr(lp, "duals_eq", None) is not None and i < len(lp.duals_eq) else 0.0
        row_cells.append(sp_eq)

        ws_model.append(row_cells)
        ws_model.cell(row=r, column=col_sp).number_format = "#,##0.0000"

        for j in range(N):
            cell_v = ws_model.cell(row=r, column=3 + j)
            if cell_v.value != "" and not str(cell_v.value).startswith("="):
                cell_v.font = DECISION_FONT

    # Inequalities
    for k in range(M_ub):
        r = ws_model.max_row + 1
        rl = lp.row_labels[M_eq + k]
        grp = rl["group"]
        desc_text = rl["desc_es" if lang == "es" else "desc_en"]
        row_cells = [desc_text, rl["key"]]

        for j in range(N):
            val = lp.A_ub[k, j]
            if abs(val) < 1e-12:
                row_cells.append("")
            else:
                row_cells.append(float(val))

        # LHS
        row_cells.append(f"=SUMPRODUCT(C{r}:{col_end_letter}{r}, dora_vars)")
        # Sense
        row_cells.append("<=")
        # RHS
        if grp == "land":
            row_cells.append(f"='{assump_title}'!C{assump_cells['owned_ha']}")
        elif grp.startswith("rotation["):
            sh = float(sc.max_crop_share)
            row_cells.append(f"='{assump_title}'!C{assump_cells['owned_ha']} * {sh:.4f}")
        elif grp.startswith("credit_line["):
            row_cells.append(f"='{assump_title}'!C{assump_cells['credit_line_usd']}")
        else:
            row_cells.append(float(lp.b_ub[k]))

        # Shadow price (DORA)
        sp_ub = float(lp.duals_ub[k]) if getattr(lp, "duals_ub", None) is not None and k < len(lp.duals_ub) else 0.0
        row_cells.append(sp_ub)

        ws_model.append(row_cells)
        ws_model.cell(row=r, column=col_sp).number_format = "#,##0.0000"

        for j in range(N):
            cell_v = ws_model.cell(row=r, column=3 + j)
            if cell_v.value != "":
                cell_v.font = DECISION_FONT

    # Named ranges
    row_eq_start = 11
    row_eq_end = 10 + M_eq
    row_le_start = 11 + M_eq
    row_le_end = 10 + M_eq + M_ub

    wb.defined_names.add(DefinedName("dora_vars", attr_text=f"'{model_title}'!$C$3:${col_end_letter}$3"))
    wb.defined_names.add(DefinedName("dora_objective", attr_text=f"'{model_title}'!$B$8"))
    wb.defined_names.add(DefinedName("dora_eq_lhs", attr_text=f"'{model_title}'!${col_lhs_letter}${row_eq_start}:${col_lhs_letter}${row_eq_end}"))
    wb.defined_names.add(DefinedName("dora_eq_rhs", attr_text=f"'{model_title}'!${col_rhs_letter}${row_eq_start}:${col_rhs_letter}${row_eq_end}"))
    wb.defined_names.add(DefinedName("dora_le_lhs", attr_text=f"'{model_title}'!${col_lhs_letter}${row_le_start}:${col_lhs_letter}${row_le_end}"))
    wb.defined_names.add(DefinedName("dora_le_rhs", attr_text=f"'{model_title}'!${col_rhs_letter}${row_le_start}:${col_rhs_letter}${row_le_end}"))

    # Excel Solver defined names (A4)
    wb.defined_names.add(DefinedName("solver_opt", attr_text=f"'{model_title}'!$B$8"))
    wb.defined_names.add(DefinedName("solver_adj", attr_text=f"'{model_title}'!$C$3:${col_end_letter}$3"))
    wb.defined_names.add(DefinedName("solver_typ", attr_text="1"))
    wb.defined_names.add(DefinedName("solver_neg", attr_text="1"))
    wb.defined_names.add(DefinedName("solver_lin", attr_text="1"))
    wb.defined_names.add(DefinedName("solver_eng", attr_text="2"))
    wb.defined_names.add(DefinedName("solver_num", attr_text="2"))
    wb.defined_names.add(DefinedName("solver_lhs1", attr_text=f"'{model_title}'!${col_lhs_letter}${row_eq_start}:${col_lhs_letter}${row_eq_end}"))
    wb.defined_names.add(DefinedName("solver_rel1", attr_text="2"))
    wb.defined_names.add(DefinedName("solver_rhs1", attr_text=f"'{model_title}'!${col_rhs_letter}${row_eq_start}:${col_rhs_letter}${row_eq_end}"))
    wb.defined_names.add(DefinedName("solver_lhs2", attr_text=f"'{model_title}'!${col_lhs_letter}${row_le_start}:${col_lhs_letter}${row_le_end}"))
    wb.defined_names.add(DefinedName("solver_rel2", attr_text="1"))
    wb.defined_names.add(DefinedName("solver_rhs2", attr_text=f"'{model_title}'!${col_rhs_letter}${row_le_start}:${col_rhs_letter}${row_le_end}"))

    # OpenSolver for Google Sheets hidden sheet __OpenSolver__
    ws_os = wb.create_sheet(title="__OpenSolver__")
    ws_os.sheet_state = "hidden"
    os_rows = [
        f'="ModelSheet={model_title}!A:Z"',
        f'="solver_opt={model_title}!$B$8"',
        '="solver_typ=1"',
        '="solver_neg=1"',
        '="solver_sho=1"',
        '="solver_val=0"',
        '="solver_num=2"',
        f'="solver_adj={model_title}!$C$3:${col_end_letter}$3"',
        f'="solver_lhs1={model_title}!${col_lhs_letter}${row_eq_start}:${col_lhs_letter}${row_eq_end}"',
        '="solver_rel1=2"',
        f'="solver_rhs1={model_title}!${col_rhs_letter}${row_eq_start}:${col_rhs_letter}${row_eq_end}"',
        f'="solver_lhs2={model_title}!${col_lhs_letter}${row_le_start}:${col_lhs_letter}${row_le_end}"',
        '="solver_rel2=1"',
        f'="solver_rhs2={model_title}!${col_rhs_letter}${row_le_start}:${col_rhs_letter}${row_le_end}"',
        '="OpenSolver_AdjNum=1"',
        '="OpenSolver_LinearityCheck=1"',
        '="OpenSolver_FastBuild=0"',
        '="OpenSolver_ChosenSolver=Google"',
    ]
    for r_os in os_rows:
        ws_os.append([r_os])
    return model_formula_cells


def _build_sales_strategy_sheet(
    wb: openpyxl.Workbook,
    ws_assump: Any,
    lp: Any,
    sc: Scenario,
    res: Any,
    sheet_names: dict[str, str],
    assump_cells: dict[str, int],
    var_col_map: dict[str, str],
    lang: str = "es",
) -> None:
    model_title = sheet_names["model"]
    assump_title = sheet_names["assumptions"]
    sales_title = sheet_names["sales"]
    ws_sales = wb.create_sheet(title=sales_title, index=2)

    # Title
    t_title = "ESTRATEGIA DE VENTA Y COMERCIALIZACIÓN" if lang == "es" else "SALES & COMMERCIAL STRATEGY"
    ws_sales.cell(row=1, column=1, value=t_title).font = Font(name=FONT_FAMILY, size=13, bold=True, color="1F4E78")

    # Short notice line on top (A8)
    notice_text = (
        "Esto es cuándo, cuánto y por dónde vender, según el plan. Si cambian los precios, pedile a DORA que recalcule."
        if lang == "es"
        else "This is when, how much and through where to sell, according to the plan. If prices change, ask DORA to recompute."
    )
    ws_sales.cell(row=2, column=1, value=notice_text).font = DECISION_FONT

    # Table 1: Detalle de ventas planificadas
    ws_sales.cell(row=4, column=1, value="DETALLE DE VENTAS PLANIFICADAS" if lang == "es" else "PLANNED SALES DETAIL").font = BOLD_FONT
    headers_t1 = (
        ["Cultivo", "Quincena", "Fecha", "Toneladas vendidas", "Canal", "Precio bruto (USD/t)", "Precio neto (USD/t)", "Ingreso (USD)"]
        if lang == "es"
        else ["Crop", "Fortnight", "Date", "Tonnes sold", "Channel", "Gross price (USD/t)", "Net price (USD/t)", "Income (USD)"]
    )
    ws_sales.append([])
    ws_sales.append(headers_t1)
    for col in range(1, 9):
        c_h = ws_sales.cell(row=5, column=col)
        c_h.fill = HEADER_FILL
        c_h.font = HEADER_FONT
        c_h.alignment = Alignment(horizontal="center")

    from dora.scenario import CALENDAR as DORA_CALENDAR, fortnight_name
    cal_scenario = sc.calendar if hasattr(sc, "calendar") else DORA_CALENDAR
    routes_list = sc.routes if hasattr(sc, "routes") and sc.routes else [{"id": "default"}]

    crop_labels_es = {"soybean": "Soja", "corn": "Maíz", "wheat": "Trigo", "sunflower": "Girasol", "sorghum": "Sorgo", "barley": "Cebada"}
    crop_labels_en = {"soybean": "Soybean", "corn": "Corn", "wheat": "Wheat", "sunflower": "Sunflower", "sorghum": "Sorghum", "barley": "Barley"}
    labels_map = crop_labels_es if lang == "es" else crop_labels_en

    t1_rows_by_crop: dict[str, list[int]] = {}
    active_crops = [c for c in sc.crops if res.hectares.get(c, 0.0) > 0.01]

    for c in active_crops:
        c_lbl = labels_map.get(c, c)
        harvest_p = cal_scenario[c]["harvest"] if c in cal_scenario else 16
        c_sales = res.sales.get(c, {})
        active_p_list = sorted([p for p, t in c_sales.items() if t > 1e-4])
        if not active_p_list:
            active_p_list = [harvest_p]

        for p in active_p_list:
            for r_route in routes_list:
                r_id = r_route["id"]
                vk = f"sell[{c},p{p},{r_id}]"
                r_num = ws_sales.max_row + 1
                t1_rows_by_crop.setdefault(c, []).append(r_num)

                fn_str = f"Q{p+1} ({fortnight_name(p, lang=lang)})"
                date_str = fortnight_name(p, lang=lang)

                if vk in var_col_map:
                    tonnes_f = f"='{model_title}'!{var_col_map[vk]}3"
                else:
                    tonnes_f = float(c_sales.get(p, 0.0))

                if p <= harvest_p:
                    channel_str = "Contado a cosecha" if lang == "es" else "Spot at harvest"
                else:
                    channel_str = "Desde acopio" if lang == "es" else "From storage"

                gross_ref = f"='{assump_title}'!C{assump_cells[f'prices.{c}']}"
                hp_key = f"net_price.{c}.p{p}"
                if hp_key in assump_cells:
                    net_ref = f"='{assump_title}'!C{assump_cells[hp_key]}"
                else:
                    net_ref = gross_ref

                income_f = f"=D{r_num}*G{r_num}"

                ws_sales.append([
                    c_lbl,
                    fn_str,
                    date_str,
                    tonnes_f,
                    channel_str,
                    gross_ref,
                    net_ref,
                    income_f,
                ])
                ws_sales.cell(row=r_num, column=4).number_format = FMT_INTEGER
                ws_sales.cell(row=r_num, column=4).fill = DECISION_FILL
                ws_sales.cell(row=r_num, column=6).number_format = FMT_CURRENCY
                ws_sales.cell(row=r_num, column=7).number_format = FMT_CURRENCY
                ws_sales.cell(row=r_num, column=8).number_format = FMT_CURRENCY

    # Forward sales if any
    for i, constr in enumerate(sc.constraints):
        if constr.get("type") == "forward_sale":
            c_fwd = constr["crop"]
            c_lbl = labels_map.get(c_fwd, c_fwd)
            m_fwd = constr.get("month", "cosecha")
            t_fwd = constr.get("tonnes", 0.0)
            fwd_vk = f"forward[{c_fwd},{m_fwd},{i}]"
            r_num = ws_sales.max_row + 1
            t1_rows_by_crop.setdefault(c_fwd, []).append(r_num)

            tonnes_f = f"='{model_title}'!{var_col_map[fwd_vk]}3" if fwd_vk in var_col_map else float(t_fwd)
            channel_str = "Venta a futuro" if lang == "es" else "Forward sale"
            gross_ref = f"='{assump_title}'!C{assump_cells[f'prices.{c_fwd}']}"
            net_ref = gross_ref
            income_f = f"=D{r_num}*G{r_num}"

            ws_sales.append([
                c_lbl,
                f"Futuro ({m_fwd})",
                str(m_fwd),
                tonnes_f,
                channel_str,
                gross_ref,
                net_ref,
                income_f,
            ])
            ws_sales.cell(row=r_num, column=4).number_format = FMT_INTEGER
            ws_sales.cell(row=r_num, column=4).fill = DECISION_FILL
            ws_sales.cell(row=r_num, column=6).number_format = FMT_CURRENCY
            ws_sales.cell(row=r_num, column=7).number_format = FMT_CURRENCY
            ws_sales.cell(row=r_num, column=8).number_format = FMT_CURRENCY

    # Table 2: Per-crop summary
    ws_sales.append([])
    start_t2 = ws_sales.max_row + 1
    ws_sales.cell(row=start_t2, column=1, value="RESUMEN DE COMERCIALIZACIÓN POR CULTIVO" if lang == "es" else "COMMERCIAL SUMMARY BY CROP").font = BOLD_FONT
    headers_t2 = (
        ["Cultivo", "A cosecha (t)", "Desde acopio (t)", "A futuro (t)", "Total vendido (t)", "Ingreso total (USD)", "Precio neto prom. (USD/t)"]
        if lang == "es"
        else ["Crop", "Harvest sales (t)", "Storage sales (t)", "Forward sales (t)", "Total sales (t)", "Total income (USD)", "Avg net price (USD/t)"]
    )
    ws_sales.append(headers_t2)
    header_row_t2 = ws_sales.max_row
    for col in range(1, 8):
        c_h = ws_sales.cell(row=header_row_t2, column=col)
        c_h.fill = HEADER_FILL
        c_h.font = HEADER_FONT
        c_h.alignment = Alignment(horizontal="center")

    for c in active_crops:
        r_num = ws_sales.max_row + 1
        c_lbl = labels_map.get(c, c)
        rows_c = t1_rows_by_crop.get(c, [])

        harvest_rows = [r for r in rows_c if ws_sales.cell(row=r, column=5).value in ("Contado a cosecha", "Spot at harvest")]
        storage_rows = [r for r in rows_c if ws_sales.cell(row=r, column=5).value in ("Desde acopio", "From storage")]
        forward_rows = [r for r in rows_c if ws_sales.cell(row=r, column=5).value in ("Venta a futuro", "Forward sale")]

        h_expr = f"=SUM({','.join(f'D{r}' for r in harvest_rows)})" if harvest_rows else "0"
        s_expr = f"=SUM({','.join(f'D{r}' for r in storage_rows)})" if storage_rows else "0"
        f_expr = f"=SUM({','.join(f'D{r}' for r in forward_rows)})" if forward_rows else "0"
        tot_expr = f"=SUM(B{r_num}:D{r_num})"
        inc_expr = f"=SUM({','.join(f'H{r}' for r in rows_c)})" if rows_c else "0"
        avg_p_expr = f"=IF(E{r_num}>0, F{r_num}/E{r_num}, 0)"

        ws_sales.append([
            c_lbl,
            h_expr,
            s_expr,
            f_expr,
            tot_expr,
            inc_expr,
            avg_p_expr,
        ])
        ws_sales.cell(row=r_num, column=2).number_format = FMT_INTEGER
        ws_sales.cell(row=r_num, column=3).number_format = FMT_INTEGER
        ws_sales.cell(row=r_num, column=4).number_format = FMT_INTEGER
        ws_sales.cell(row=r_num, column=5).number_format = FMT_INTEGER
        ws_sales.cell(row=r_num, column=6).number_format = FMT_CURRENCY
        ws_sales.cell(row=r_num, column=7).number_format = FMT_CURRENCY
    return ws_sales


def export_plan_xlsx(
    scenario: dict[str, Any],
    lang: str = "es",
    record: dict | None = None,
) -> bytes:
    """Validate and solve the scenario, generating a 9-sheet .xlsx workbook with live formulas.
    Raises ValueError for stochastic climate scenarios.
    """
    if scenario.get("climate_scenarios"):
        err_msg = (
            "El exportador a planilla no está disponible para escenarios climáticos estocásticos."
            if lang == "es"
            else "Spreadsheet export is not available with stochastic climate scenarios."
        )
        raise ValueError(err_msg)

    sc_clean = {k: v for k, v in scenario.items() if k not in ("costs_origin", "costs_source", "document_date", "invoice_date", "model")}
    sc = Scenario(**sc_clean)
    res = optimize(sc, keep_lp=True)

    wb = openpyxl.Workbook()
    sheet_names = _get_sheet_names(lang)

    from dora.tools import regional_source_label
    reg_source = regional_source_label(sc.region)
    farmer_lbl = "lo dijo el productor" if lang == "es" else "farmer"
    supp_lbl = "supuesto" if lang == "es" else "assumption"

    # Pre-calculate variable column map if lp is available
    var_col_map: dict[str, str] = {}
    if res.lp is not None:
        for j, v_lbl in enumerate(res.lp.var_labels):
            var_col_map[v_lbl["key"]] = get_column_letter(3 + j)

    # -------------------------------------------------------------
    # Sheet 5: Supuestos / Assumptions (created first for formula refs)
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

    # Helper net prices per crop per fortnight
    T_fortnights = len(res.cash)
    routes_list = sc.routes if hasattr(sc, "routes") and sc.routes else [{"id": "default"}]
    default_route = routes_list[0]
    from dora.scenario import CALENDAR as DORA_CALENDAR, fortnight_name
    cal_scenario = sc.calendar if hasattr(sc, "calendar") else DORA_CALENDAR
    for c in sc.crops:
        harvest_p = cal_scenario[c]["harvest"] if c in cal_scenario else 16
        for p in range(T_fortnights):
            months = (p - harvest_p) / 2
            factor = ((1 + sc.monthly_price_rise) ** months) * (1.0 - sc.gross_receipts_rate - sc.transaction_tax_rate)
            ded = sc.route_cost(default_route, p) + sc.marketing_per_t(c)
            p_row = assump_cells.get(f"prices.{c}")
            if p_row:
                r_idx = ws_assump.max_row + 1
                assump_cells[f"net_price.{c}.p{p}"] = r_idx
                if abs(ded) < 1e-6:
                    hp_formula = f"={factor:.10f}*C{p_row}"
                elif ded > 0:
                    hp_formula = f"={factor:.10f}*C{p_row}-{ded:.6f}"
                else:
                    hp_formula = f"={factor:.10f}*C{p_row}+{-ded:.6f}"
                ws_assump.append([f"helper.net_price.{c}.p{p}", f"Precio neto {c} q{p}" if lang == "es" else f"Net price {c} p{p}", hp_formula, "USD/t", "cálculo fórmula"])

    # -------------------------------------------------------------
    # Sheet 1: Resumen / Summary
    # -------------------------------------------------------------
    ws_sum = wb.create_sheet(title=sheet_names["summary"], index=0)
    # Warning Box (A6)
    warning_formula = (
        '=IF(SUMPRODUCT(ABS(dora_vars - _dora_vars)) > 0.01, "Plan recalculado fuera de DORA: sin verificar. Mandale la planilla a DORA para verificarlo.", "Este plan era el óptimo con estos supuestos. Si cambiás algo, pedile a DORA que recalcule: mandá esta planilla por el chat.")'
        if lang == "es"
        else '=IF(SUMPRODUCT(ABS(dora_vars - _dora_vars)) > 0.01, "Plan recomputed outside DORA: unverified. Send this file to DORA to verify it.", "This plan was the best one under these assumptions. If you change anything, ask DORA to recompute: send this file back in the chat.")'
    )
    ws_sum.merge_cells("A1:G2")
    w_cell = ws_sum.cell(row=1, column=1, value=warning_formula)
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
        ws_sum.append([
            c,
            "Óptima" if lang == "es" else "Optimal",
            f"='{plan_sheet_name}'!B{crop_rows_in_plan_sheet[c]}",
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
    cash_last_row = T_fortnights + 1
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

    # Binding resources / Shadow prices block (A13)
    ws_sum.append([])
    sp_box_title = "RECURSOS QUE LIMITAN EL PLAN (PRECIOS SOMBRA)" if lang == "es" else "RESOURCES LIMITING THE PLAN (SHADOW PRICES)"
    ws_sum.cell(row=ws_sum.max_row + 1, column=1, value=sp_box_title).font = Font(name=FONT_FAMILY, size=11, bold=True, color="1F4E78")
    sp_note_formula = (
        '=IF(SUMPRODUCT(ABS(dora_vars - _dora_vars)) > 0.01, "Estos precios sombra son del plan de DORA; para los del plan nuevo, pedíselos a DORA.", "Precios sombra de la solución de DORA.")'
        if lang == "es"
        else '=IF(SUMPRODUCT(ABS(dora_vars - _dora_vars)) > 0.01, "These shadow prices belong to the DORA plan; for the new plan prices, ask DORA.", "Shadow prices of DORA optimal plan.")'
    )
    ws_sum.append([sp_note_formula])
    ws_sum.cell(row=ws_sum.max_row, column=1).font = DECISION_FONT

    ws_sum.append(["Tierra propia" if lang == "es" else "Owned land", f"Una hectárea más de tierra propia vale {res.land_shadow_price:.2f} USD/ha" if lang == "es" else f"One more hectare of owned land is worth {res.land_shadow_price:.2f} USD/ha"])
    if res.capital_shadow_price > 0.0001:
        ws_sum.append(["Capital propio inicial" if lang == "es" else "Initial own capital", f"Un dólar más de capital inicial vale {res.capital_shadow_price:.4f} USD" if lang == "es" else f"One more dollar of initial capital is worth {res.capital_shadow_price:.4f} USD"])
    if sum(res.credit_shadow_price) > 0.0001:
        ws_sum.append(["Línea de crédito" if lang == "es" else "Credit line", f"Un dólar más de línea de crédito vale {sum(res.credit_shadow_price):.4f} USD" if lang == "es" else f"One more dollar of credit line is worth {sum(res.credit_shadow_price):.4f} USD"])
    if sum(res.storage_shadow_price) > 0.0001:
        ws_sum.append(["Capacidad de silo" if lang == "es" else "Storage capacity", f"Una tonelada más de silo vale {sum(res.storage_shadow_price):.2f} USD" if lang == "es" else f"One more tonne of storage is worth {sum(res.storage_shadow_price):.2f} USD"])
    for p in range(len(res.cash_value) - 1):
        if res.credit_shadow_price[p] > 0.0001 or res.cash_value[p] > 1.0001:
            fn_nm = fortnight_name(p, lang=lang)
            ws_sum.append([f"Capital Q{p+1}" if lang == "es" else f"Capital P{p+1}", f"Un dólar más en la quincena {p+1} ({fn_nm}) vale {res.cash_value[p]:.4f} USD" if lang == "es" else f"One more dollar in fortnight {p+1} ({fn_nm}) is worth {res.cash_value[p]:.4f} USD"])
    os_disclaimer = (
        "Nota: OpenSolver para Google Sheets no entrega informe de sensibilidad; los duales calculados corresponden a la solución de DORA."
        if lang == "es"
        else "Note: OpenSolver for Google Sheets does not output a sensitivity report; the reported duals correspond to DORA's solution."
    )
    ws_sum.append([os_disclaimer])
    ws_sum.cell(row=ws_sum.max_row, column=1).font = DECISION_FONT

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
    crop_row_map = {}
    for c in active_crops:
        r = ws_crops.max_row + 1
        crop_row_map[c] = r
        ha_vk = f"ha[{c}]"
        if ha_vk in var_col_map:
            ha_expr = f"='{sheet_names['model']}'!{var_col_map[ha_vk]}3"
        else:
            ha_expr = float(res.hectares[c])

        y_ref = f"'{assump_name}'!C{assump_cells[f'yields.{c}']}"
        p_ref = f"'{assump_name}'!C{assump_cells[f'prices.{c}']}"

        cost_cells = [f"'{assump_name}'!C{assump_cells[f'costs.{c}.{item}']}" for item in ("seed", "fertilizer", "crop_protection", "field_operations", "marketing_harvest")]
        cost_sum_formula = f"={'+'.join(cost_cells)}"

        ws_crops.append([
            c,
            ha_expr,
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
    # Sheet 3: Estrategia de venta / Sales strategy (A8)
    # -------------------------------------------------------------
    ws_sales = _build_sales_strategy_sheet(wb, ws_assump, res.lp, sc, res, sheet_names, assump_cells, var_col_map, lang=lang)

    # -------------------------------------------------------------
    # Sheet 4: Caja por quincena / Cash by fortnight (A11, A12)
    # -------------------------------------------------------------
    ws_cash = wb.create_sheet(title=sheet_names["cash"], index=3)
    headers_cash = (
        ["Quincena", "Saldo Inicial", "Insumos", "Ventas", "Ventas a término", "Silos Entrada", "Silos Mensual", "Alquiler Pagado", "Alquiler Cobrado", "Interés Colocación", "Interés Deuda", "Crédito Tomado", "Crédito Cancelado", "Saldo Final", "Deuda Acumulada", "Saldo ≥ 0", "Deuda ≤ Línea", "Silo en rango", "Ventas ≤ Cosecha"]
        if lang == "es"
        else ["Fortnight", "Opening Cash", "Inputs", "Sales", "Forward Sales", "Storage Fill", "Storage Monthly", "Rent In", "Rent Out", "Deposit Interest", "Credit Interest", "Credit Drawn", "Credit Repaid", "Closing Cash", "Debt", "Cash ≥ 0", "Debt ≤ Line", "Storage in range", "Sales ≤ Harvest"]
    )
    ws_cash.append(headers_cash)
    for col in range(1, 20):
        c_h = ws_cash.cell(row=1, column=col)
        c_h.fill = HEADER_FILL
        c_h.font = HEADER_FONT
        c_h.alignment = Alignment(horizontal="center")

    own_cap_cell = f"'{assump_name}'!C{assump_cells['own_capital_usd']}"
    land_tax_cell = f"'{assump_name}'!C{assump_cells['land_tax_usd_ha_year']}"
    owned_ha_cell = f"'{assump_name}'!C{assump_cells['owned_ha']}"
    ri_cell = f"'{assump_name}'!C{assump_cells['ri_fortnightly']}"
    rc_cell = f"'{assump_name}'!C{assump_cells['rc_fortnightly']}"

    storage_opts = sc.effective_storage_options() if hasattr(sc, "effective_storage_options") else (sc.storage_options or [])
    h_c0_map = {c: (cal_scenario[c]["harvest"] if c in cal_scenario else 16) for c in sc.crops}

    for p in range(T_fortnights):
        r = p + 2
        lbl = f"Q{p+1}"

        # Opening cash formula
        if p == 0:
            open_formula = f"={own_cap_cell} - {land_tax_cell} * {owned_ha_cell}"
        else:
            open_formula = f"=N{r - 1}"

        # Group flows from cash_ledger
        ledger_p = res.cash_ledger[p] if p < len(res.cash_ledger) else {}
        inputs_p = ledger_p.get("inputs", {})
        if not inputs_p:
            flow_inputs = 0.0
        else:
            terms = []
            for c, cash_amt in inputs_p.items():
                ha_c = float(res.hectares.get(c, 0.0))
                base_c = sum(sc._cost(c, item) for item in ("seed", "fertilizer", "crop_protection", "field_operations", "marketing_harvest"))
                if ha_c > 1e-6 and base_c > 1e-6 and c in crop_row_map:
                    r_crop = crop_row_map[c]
                    ha_ref = f"'{sheet_names['crops']}'!B{r_crop}"
                    cost_ref = f"'{sheet_names['crops']}'!F{r_crop}"
                    share_p = abs(cash_amt) / (ha_c * base_c)
                    terms.append(f"({ha_ref}*{cost_ref}*{share_p:.10f})")
                else:
                    terms.append(f"{abs(cash_amt):.2f}")
            flow_inputs = f"=-({'+'.join(terms)})"

        # Sales formula: reactive on dora_vars sell cells
        sales_terms = []
        for c in sc.crops:
            for r_route in routes_list:
                vk = f"sell[{c},p{p},{r_route['id']}]"
                hp_key = f"net_price.{c}.p{p}"
                if vk in var_col_map and hp_key in assump_cells:
                    sales_terms.append(f"'{sheet_names['model']}'!{var_col_map[vk]}3 * '{assump_name}'!C{assump_cells[hp_key]}")
        if sales_terms:
            flow_sales = f"={'+'.join(sales_terms)}"
        else:
            flow_sales = 0.0

        flow_fwd = sum(ledger_p.get("forward_sales", {}).values())

        # Silos Entrada
        terms_in = []
        for c in sc.crops:
            for opt in storage_opts:
                vk = f"put_in[{c},p{p},{opt['id']}]"
                fill_rate = float(opt.get("fill_cost_usd_t", 0.0))
                if vk in var_col_map and fill_rate > 1e-6:
                    terms_in.append(f"{fill_rate:.4f} * '{sheet_names['model']}'!{var_col_map[vk]}3")
        flow_silo_fill = f"=-({'+'.join(terms_in)})" if terms_in else sum(ledger_p.get("storage_fill", {}).values())

        # Silos Mensual
        terms_m = []
        for c in sc.crops:
            for opt in storage_opts:
                vk = f"stock[{c},p{p},{opt['id']}]"
                half_m = float(opt.get("monthly_cost_usd_t", 0.0)) / 2.0
                if vk in var_col_map and half_m > 1e-6:
                    terms_m.append(f"{half_m:.4f} * '{sheet_names['model']}'!{var_col_map[vk]}3")
        flow_silo_m = f"=-({'+'.join(terms_m)})" if terms_m else sum(ledger_p.get("storage_monthly", {}).values())

        # Alquileres
        flow_rent_in = sum(ledger_p.get("rent_in", {}).values())
        if "rent_in" in var_col_map and abs(flow_rent_in) > 1e-6 and float(res.rent_in_ha) > 1e-6 and sc.regional_rent_usd_ha > 1e-6:
            share_rent = abs(flow_rent_in) / (float(res.rent_in_ha) * sc.regional_rent_usd_ha)
            flow_rent_in = f"=-({share_rent:.6f} * '{assump_name}'!C{assump_cells['regional_rent_usd_ha']} * '{sheet_names['model']}'!{var_col_map['rent_in']}3)"

        flow_rent_out = sum(ledger_p.get("rent_out", {}).values())
        if "rent_out" in var_col_map and abs(flow_rent_out) > 1e-6 and float(res.rent_out_ha) > 1e-6 and sc.regional_rent_usd_ha > 1e-6:
            share_rent = abs(flow_rent_out) / (float(res.rent_out_ha) * sc.regional_rent_usd_ha)
            flow_rent_out = f"=({share_rent:.6f} * '{assump_name}'!C{assump_cells['regional_rent_usd_ha']} * '{sheet_names['model']}'!{var_col_map['rent_out']}3)"

        # Interest formulas
        if p == 0:
            dep_int_formula = 0.0
            cred_int_formula = 0.0
        else:
            dep_int_formula = f"=N{r - 1} * {ri_cell}"
            cred_int_formula = f"=O{r - 1} * {rc_cell}"

        # Decisions: credit drawn and repaid reactive on dora_vars (A11)
        if "D[p0]" in var_col_map:
            if p == 0:
                cr_drawn = f"='{sheet_names['model']}'!{var_col_map['D[p0]']}3"
                cr_repaid = 0.0
            else:
                col_dp = var_col_map[f"D[p{p}]"]
                col_dprev = var_col_map[f"D[p{p-1}]"]
                cr_drawn = f"=MAX(0, '{sheet_names['model']}'!{col_dp}3 - '{sheet_names['model']}'!{col_dprev}3)"
                cr_repaid = f"=MAX(0, '{sheet_names['model']}'!{col_dprev}3 - '{sheet_names['model']}'!{col_dp}3)"
            debt_formula = f"='{sheet_names['model']}'!{var_col_map[f'D[p{p}]']}3"
        else:
            cr_drawn = res.credit_drawn[p] if p < len(res.credit_drawn) else 0.0
            cr_repaid = res.credit_repaid[p] if p < len(res.credit_repaid) else 0.0
            debt_formula = f"=L{r}-M{r}" if p == 0 else f"=O{r - 1}+L{r}-M{r}"

        # Closing cash formula (A11)
        closing_formula = f"=B{r}+J{r}-K{r}+C{r}+D{r}+E{r}+F{r}+G{r}+H{r}+I{r}+L{r}-M{r}"

        # Checks per fortnight (A12)
        chk_cash = f'=IF(N{r} >= -0.01, "OK", "ERROR")'
        cred_cell_ref = f"'{assump_name}'!C{assump_cells['credit_line_usd']}"
        chk_debt = f'=IF(O{r} <= {cred_cell_ref} + 0.01, "OK", "ERROR")'

        # Check Silo
        stock_terms = []
        for c in sc.crops:
            for opt in storage_opts:
                vk = f"stock[{c},p{p},{opt['id']}]"
                if vk in var_col_map:
                    stock_terms.append(f"'{sheet_names['model']}'!{var_col_map[vk]}3")
        tot_cap = sum(float(opt.get("capacity_t", 0.0) or 0.0) for opt in storage_opts if opt.get("capacity_t"))
        if stock_terms and tot_cap > 0:
            chk_silo = f'=IF(AND(({"+".join(stock_terms)}) >= -0.01, ({"+".join(stock_terms)}) <= {tot_cap:.2f} + 0.01), "OK", "ERROR")'
        elif stock_terms:
            chk_silo = f'=IF(({"+".join(stock_terms)}) >= -0.01, "OK", "ERROR")'
        else:
            chk_silo = '="OK"'

        # Check Sales <= Harvest
        crop_conds = []
        for c in active_crops:
            h_c = cal_scenario[c]["harvest"] if c in cal_scenario else 16
            h0_c = h_c0_map[c]
            sales_terms_c = [f"'{sheet_names['model']}'!{var_col_map[f'sell[{c},p{t},{r_route["id"]}]']}3" for t in range(h0_c, p + 1) for r_route in routes_list if f"sell[{c},p{t},{r_route["id"]}]" in var_col_map]
            s_expr = f"({'+'.join(sales_terms_c)})" if sales_terms_c else "0"
            if p < h_c:
                crop_conds.append(f"{s_expr} <= 0.01")
            else:
                r_crop = crop_row_map[c]
                crop_conds.append(f"{s_expr} <= '{sheet_names['crops']}'!D{r_crop} + 0.01")
        if crop_conds:
            chk_sales = f'=IF(AND({", ".join(crop_conds)}), "OK", "ERROR")' if len(crop_conds) > 1 else f'=IF({crop_conds[0]}, "OK", "ERROR")'
        else:
            chk_sales = '="OK"'

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
            chk_cash,
            chk_debt,
            chk_silo,
            chk_sales,
        ])

        for col in range(2, 16):
            cell = ws_cash.cell(row=r, column=col)
            cell.number_format = FMT_CURRENCY
            if col in (6, 7):
                cell.fill = DECISION_FILL
            elif col in (12, 13):
                cell.fill = DECISION_FILL

        for col in range(16, 20):
            cell = ws_cash.cell(row=r, column=col)
            cell.alignment = Alignment(horizontal="center")
            cell.font = BOLD_FONT

    # Add openpyxl LineChart to Sheet 4
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
    ws_cash.add_chart(chart, "U2")

    # -------------------------------------------------------------
    # Sheet 5: Modelo / Model (SPEC-45)
    # -------------------------------------------------------------
    model_formula_cells: list[str] = []
    if res.lp is not None:
        model_formula_cells = _build_model_sheet(wb, ws_assump, res.lp, sc, res, sheet_names, assump_cells, lang=lang)
        if model_formula_cells:
            cond_formula = "AND(" + ", ".join(f"ISFORMULA({c})" for c in model_formula_cells[:15]) + ")"
            ws_sum["A1"] = (
                f'=IF(NOT({cond_formula}), "Cambiaste el modelo: el resultado ya no es comparable con el de DORA.", IF(SUMPRODUCT(ABS(dora_vars - _dora_vars)) > 0.01, "Plan recalculado fuera de DORA: sin verificar. Mandale la planilla a DORA para verificarlo.", "Este plan era el óptimo con estos supuestos. Si cambiás algo, pedile a DORA que recalcule: mandá esta planilla por el chat."))'
                if lang == "es"
                else f'=IF(NOT({cond_formula}), "Model edited: result is no longer comparable with DORA.", IF(SUMPRODUCT(ABS(dora_vars - _dora_vars)) > 0.01, "Plan recomputed outside DORA: unverified. Send this file to DORA to verify it.", "This plan was the best one under these assumptions. If you change anything, ask DORA to recompute: send this file back in the chat."))'
            )

    # -------------------------------------------------------------
    # Sheet 6: Sensibilidad / Sensitivity
    # -------------------------------------------------------------
    ws_sens = wb.create_sheet(title=sheet_names["sensitivity"], index=6)
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
    # Sheet 7: Verificación / Verification (A6, A9, A12)
    # -------------------------------------------------------------
    ws_verif = wb.create_sheet(title=sheet_names["verification"], index=7)
    ws_verif.cell(row=1, column=1, value="VERIFICACIÓN Y PROCEDENCIA CRIPTOGRÁFICA" if lang == "es" else "VERIFICATION & CRYPTOGRAPHIC PROVENANCE").font = Font(name=FONT_FAMILY, size=13, bold=True)
    ws_verif.cell(row=2, column=1, value="Cada número de este plan lo calculó el motor de DORA; el modelo de lenguaje solo armó el escenario y lo explicó." if lang == "es" else "Every number in this plan was computed by DORA's engine; the language model only assembled the scenario and explained it.").font = DECISION_FONT

    import dataclasses
    from dora.tools import _validate, evaluate_season
    sc_obj, _ = _validate(sc_clean)
    sc_val = dataclasses.asdict(sc_obj)
    res_eval = evaluate_season(sc_clean, lang=lang)

    fp = engine_fingerprint()
    sc_hash = sha256_canonical(sc_val)
    res_hash = sha256_canonical(res_eval)

    ws_verif.append([])
    ws_verif.append(["ESTADO Y CHEQUEOS DEL PLAN" if lang == "es" else "PLAN STATUS & CHECKS"])
    ws_verif.cell(row=4, column=1).font = BOLD_FONT

    # A6: Outside-DORA flag formula
    if model_formula_cells:
        cond_formula = "AND(" + ", ".join(f"ISFORMULA({c})" for c in model_formula_cells[:15]) + ")"
        status_formula = (
            f'=IF(NOT({cond_formula}), "Cambiaste el modelo: el resultado ya no es comparable con el de DORA.", IF(SUMPRODUCT(ABS(dora_vars - _dora_vars)) > 0.01, "Plan recalculado fuera de DORA: sin verificar. Mandale la planilla a DORA para verificarlo.", "Plan de DORA, verificado"))'
            if lang == "es"
            else f'=IF(NOT({cond_formula}), "Model edited: result is no longer comparable with DORA.", IF(SUMPRODUCT(ABS(dora_vars - _dora_vars)) > 0.01, "Plan recomputed outside DORA: unverified. Send this file to DORA to verify it.", "DORA plan, verified"))'
        )
    else:
        status_formula = (
            '=IF(SUMPRODUCT(ABS(dora_vars - _dora_vars)) > 0.01, "Plan recalculado fuera de DORA: sin verificar. Mandale la planilla a DORA para verificarlo.", "Plan de DORA, verificado")'
            if lang == "es"
            else '=IF(SUMPRODUCT(ABS(dora_vars - _dora_vars)) > 0.01, "Plan recomputed outside DORA: unverified. Send this file to DORA to verify it.", "DORA plan, verified")'
        )
    ws_verif.append(["Estado del plan" if lang == "es" else "Plan status", status_formula])
    ws_verif.cell(row=5, column=1).font = BOLD_FONT
    ws_verif.cell(row=5, column=2).font = BOLD_FONT

    # A12: Check summary formula
    cash_range_ref = f"'{sheet_names['cash']}'!P2:S{T_fortnights + 1}"
    checks_formula = (
        f'=IF(COUNTIF({cash_range_ref}, "ERROR") = 0, "Todas las restricciones por quincena se cumplen", "Restricciones por quincena no cumplidas: revisar Caja")'
        if lang == "es"
        else f'=IF(COUNTIF({cash_range_ref}, "ERROR") = 0, "All fortnightly constraints are satisfied", "Fortnightly constraints violated: check Cash")'
    )
    ws_verif.append(["Chequeos por quincena" if lang == "es" else "Fortnightly checks", checks_formula])
    ws_verif.cell(row=6, column=1).font = BOLD_FONT
    ws_verif.cell(row=6, column=2).font = BOLD_FONT

    # A9: Model name
    model_name_val = scenario.get("model") or ("armado a mano en la pestaña Escenario" if lang == "es" else "assembled by hand in Scenario tab")
    ws_verif.append(["Modelo de lenguaje" if lang == "es" else "Language model", model_name_val])
    ws_verif.cell(row=7, column=1).font = BOLD_FONT

    ws_verif.append([])
    ws_verif.append(["PARÁMETROS DEL MOTOR Y PROCEDENCIA" if lang == "es" else "ENGINE PARAMETERS & PROVENANCE"])
    ws_verif.cell(row=9, column=1).font = BOLD_FONT

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
    # Sheet 8: _dora (hidden metadata)
    # -------------------------------------------------------------
    ws_dora = wb.create_sheet(title=sheet_names["dora"], index=8)
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

    # Row 2: _dora_vars
    ws_dora.cell(row=2, column=1, value="Decisiones DORA")
    ws_dora.cell(row=2, column=2, value="_dora_vars")
    if res.lp is not None:
        for j in range(len(res.lp.c)):
            ws_dora.cell(row=2, column=3 + j, value=float(res.lp.x[j]))
        col_end_letter = get_column_letter(2 + len(res.lp.c))
        wb.defined_names.add(DefinedName("_dora_vars", attr_text=f"'{sheet_names['dora']}'!$C$2:${col_end_letter}$2"))

    # Rows 3+: original Supuestos snapshot
    ws_dora.append([])
    ws_dora.append(["Clave", "Valor Original", "VinculadoPorFormula"])
    for k_item, _, v_item, _, _ in assump_rows:
        ws_dora.append([k_item, v_item, 1 if is_formula_linked(k_item) else 0])

    # Auto-adjust column widths on all sheets
    for ws in (ws_sum, ws_crops, ws_sales, ws_cash, ws_assump, ws_sens, ws_verif):
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
    Evaluates season with new scenario, checks model re-solve, and computes delta.
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

        if key in ("ri_fortnightly", "rc_fortnightly") or key.startswith("helper."):
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

    # Evaluate new plan with DORA
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

    # Model sheet decision comparison & re-resolve verification (A7)
    model_sheet_name = "Modelo" if "Modelo" in wb.sheetnames else ("Model" if "Model" in wb.sheetnames else None)
    same_plan = True
    reason = "dora_plan"
    sheet_plan = dict(plan_after)
    dora_plan = dict(plan_after)

    if model_sheet_name and "_dora" in wb.sheetnames:
        ws_model = wb[model_sheet_name]
        dora_vars_row = [cell.value for cell in ws_dora[2] if cell.column >= 3 and cell.value is not None]
        N_vars = len(dora_vars_row)
        sheet_vars_row = [ws_model.cell(row=3, column=3 + j).value for j in range(N_vars)]

        def _to_f(v):
            try:
                return float(v)
            except (ValueError, TypeError):
                return 0.0

        d_vars = [_to_f(v) for v in dora_vars_row]
        s_vars = [_to_f(v) for v in sheet_vars_row]

        decisions_changed = any(abs(s - d) > 0.01 for s, d in zip(s_vars, d_vars))

        # Solve new scenario with DORA to obtain expected optimum
        dora_opt_res = optimize(Scenario(**new_sc), keep_lp=True)
        dora_x = [float(v) for v in dora_opt_res.lp.x] if dora_opt_res.lp else []
        dora_npv = float(dora_opt_res.npv)

        dora_plan = {
            "hectares": dora_opt_res.hectares,
            "npv": round(dora_npv, 2),
            "max_credit": max(dora_opt_res.debt) if dora_opt_res.debt else 0.0,
        }

        # Check model coefficient tampering
        model_tampered = False
        wb_raw = openpyxl.load_workbook(io.BytesIO(data), data_only=False)
        ws_model_raw = wb_raw[model_sheet_name]
        if dora_opt_res.lp is not None:
            M_eq = len(dora_opt_res.lp.b_eq)
            for i in range(M_eq):
                r_idx = 11 + i
                grp = dora_opt_res.lp.row_labels[i]["group"]
                for j in range(len(dora_x)):
                    vk = dora_opt_res.lp.var_labels[j]["key"]
                    is_formula = (grp.startswith("harvest_balance[") and (vk.startswith("ha[") or vk.startswith("ha_w["))) or (grp.startswith("cash[") and vk.startswith("sell["))
                    cell_val = ws_model_raw.cell(row=r_idx, column=3 + j).value
                    exp_val = dora_opt_res.lp.A_eq[i, j]
                    if is_formula and abs(exp_val) > 1e-12:
                        if cell_val is None or not str(cell_val).startswith("="):
                            model_tampered = True
                            break
                    else:
                        c_num = _to_f(cell_val)
                        if abs(c_num - exp_val) > 0.01:
                            model_tampered = True
                            break
                if model_tampered:
                    break
            if not model_tampered:
                M_ub = len(dora_opt_res.lp.b_ub)
                for k in range(M_ub):
                    r_idx = 11 + M_eq + k
                    for j in range(len(dora_x)):
                        cell_val = ws_model_raw.cell(row=r_idx, column=3 + j).value
                        exp_val = dora_opt_res.lp.A_ub[k, j]
                        c_num = _to_f(cell_val)
                        if abs(c_num - exp_val) > 0.01:
                            model_tampered = True
                            break
                    if model_tampered:
                        break

        # Calculate sheet objective
        b8_val = ws_model.cell(row=8, column=2).value
        try:
            sheet_npv = float(b8_val)
        except (ValueError, TypeError):
            if dora_opt_res.lp:
                sheet_npv = sum(-float(dora_opt_res.lp.c[j]) * s_vars[j] for j in range(min(len(s_vars), len(dora_opt_res.lp.c)))) - dora_opt_res.lp.obj_constant
            else:
                sheet_npv = dora_npv

        # Extract sheet hectares
        sheet_ha = {}
        if dora_opt_res.lp:
            for j, lbl in enumerate(dora_opt_res.lp.var_labels):
                vk = lbl["key"]
                if vk.startswith("ha[") and "," not in vk:
                    c_name = vk.split("[")[1].rstrip("]")
                    if j < len(s_vars):
                        sheet_ha[c_name] = round(s_vars[j], 1)
        else:
            sheet_ha = dict(plan_after["hectares"] or {})

        sheet_plan = {
            "hectares": sheet_ha,
            "npv": round(sheet_npv, 2),
            "max_credit": plan_after.get("max_credit", 0.0),
        }

        max_var_diff = max((abs(s - d) for s, d in zip(s_vars, dora_x)), default=0.0)

        if model_tampered:
            same_plan = False
            reason = "model edited"
        elif decisions_changed or len(changes) > 0:
            if max_var_diff < 0.05:
                same_plan = True
                reason = (
                    "OpenSolver (o el solver que usaste) llegó al mismo plan que DORA: verificado."
                    if lang == "es"
                    else "OpenSolver (or the solver you used) found the same plan as DORA: verified."
                )
            else:
                same_plan = False
                if any(is_value_only(ch["key"]) for ch in changes):
                    reason = "value_only_input"
                elif sheet_npv < dora_npv - 1.0:
                    reason = "worse"
                else:
                    reason = "different_solution"
        else:
            same_plan = True
            reason = "dora_plan"

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
        "sheet_plan": sheet_plan,
        "dora_plan": dora_plan,
        "same_plan": same_plan,
        "reason": reason,
    }
