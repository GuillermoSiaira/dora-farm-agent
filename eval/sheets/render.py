"""Render a model sheet JSON into an Excel (.xlsx) file using openpyxl.

The rendered workbook contains:
- 'Modelo': grid of cells with formulas and values, highlighting decision variables.
- 'Solver': objective cell, sense, and constraints.
- 'Corrector': grading verdict, solved variable values, and any flagged invented numbers.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from eval.sheets.grader import parse_variables_list


VAR_FILL = PatternFill(start_color="D9EAD3", end_color="D9EAD3", fill_type="solid")  # soft green
HEADER_FILL = PatternFill(start_color="F3F3F3", end_color="F3F3F3", fill_type="solid")
HEADER_FONT = Font(name="Calibri", size=11, bold=True)
REGULAR_FONT = Font(name="Calibri", size=11)
THIN_BORDER = Border(
    left=Side(style="thin", color="CCCCCC"),
    right=Side(style="thin", color="CCCCCC"),
    top=Side(style="thin", color="CCCCCC"),
    bottom=Side(style="thin", color="CCCCCC"),
)


def render_sheet_to_xlsx(
    sheet_dict: dict[str, Any],
    output_path: str | Path,
    grade_result: dict[str, Any] | None = None,
) -> Path:
    """Render a model sheet JSON dictionary to a formatted .xlsx workbook."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.Workbook()

    # 1. Sheet 'Modelo'
    ws_model = wb.active
    ws_model.title = "Modelo"
    ws_model.views.sheetView[0].showGridLines = True

    cells_data = sheet_dict.get("cells", {})
    var_cells = set(parse_variables_list(sheet_dict.get("variables", "")))

    for ref, val in cells_data.items():
        ref_clean = str(ref).strip().upper()
        if not re.match(r"^[A-Z]+[0-9]+$", ref_clean):
            continue
        cell = ws_model[ref_clean]
        if isinstance(val, str) and val.startswith("="):
            cell.value = val
        else:
            try:
                cell.value = float(val)
            except (ValueError, TypeError):
                cell.value = val
        cell.font = REGULAR_FONT
        cell.border = THIN_BORDER
        cell.alignment = Alignment(horizontal="right" if isinstance(cell.value, (int, float)) or str(cell.value).startswith("=") else "left")

    for v_ref in var_cells:
        if re.match(r"^[A-Z]+[0-9]+$", v_ref):
            cell = ws_model[v_ref]
            cell.fill = VAR_FILL

    # 2. Sheet 'Solver'
    ws_solver = wb.create_sheet(title="Solver")
    ws_solver.views.sheetView[0].showGridLines = True

    ws_solver["A1"] = "Configuración del Modelo de Optimización (Solver)"
    ws_solver["A1"].font = Font(name="Calibri", size=13, bold=True)

    obj_info = sheet_dict.get("objective", {})
    obj_cell = obj_info.get("cell", "")
    obj_sense = obj_info.get("sense", "max")

    ws_solver["A3"] = "Función Objetivo:"
    ws_solver["A3"].font = HEADER_FONT
    ws_solver["B3"] = str(obj_cell)
    ws_solver["C3"] = str(obj_sense).upper()

    ws_solver["A5"] = "Variables de Decisión:"
    ws_solver["A5"].font = HEADER_FONT
    ws_solver["B5"] = str(sheet_dict.get("variables", ""))

    ws_solver["A7"] = "Restricciones:"
    ws_solver["A7"].font = HEADER_FONT

    ws_solver["A8"] = "Lado Izquierdo (LHS)"
    ws_solver["B8"] = "Operador"
    ws_solver["C8"] = "Lado Derecho (RHS)"
    for col in ("A8", "B8", "C8"):
        ws_solver[col].font = HEADER_FONT
        ws_solver[col].fill = HEADER_FILL
        ws_solver[col].border = THIN_BORDER

    row = 9
    for c in sheet_dict.get("constraints", []):
        if not isinstance(c, dict):
            continue
        ws_solver.cell(row=row, column=1, value=str(c.get("lhs", ""))).border = THIN_BORDER
        ws_solver.cell(row=row, column=2, value=str(c.get("op", "<="))).border = THIN_BORDER
        ws_solver.cell(row=row, column=3, value=str(c.get("rhs", ""))).border = THIN_BORDER
        row += 1

    # 3. Sheet 'Corrector'
    ws_corr = wb.create_sheet(title="Corrector")
    ws_corr.views.sheetView[0].showGridLines = True

    ws_corr["A1"] = "Dictamen de Auditoría Automática (Grader)"
    ws_corr["A1"].font = Font(name="Calibri", size=13, bold=True)

    if grade_result is not None:
        ws_corr["A3"] = "Estado:"
        ws_corr["B3"] = grade_result.get("status", "unknown")
        ws_corr["A4"] = "Valor Objetivo:"
        ws_corr["B4"] = grade_result.get("objective")
        ws_corr["A5"] = "Resuelto (solved):"
        ws_corr["B5"] = "SÍ" if grade_result.get("solved") else "NO"
        ws_corr["A6"] = "Falta no negatividad:"
        ws_corr["B6"] = "SÍ" if grade_result.get("missing_nonneg") else "NO"
        ws_corr["A7"] = "Números inventados:"
        ws_corr["B7"] = ", ".join(map(str, grade_result.get("invented_numbers", []))) or "Ninguno"

        if grade_result.get("error"):
            ws_corr["A8"] = "Error:"
            ws_corr["B8"] = grade_result.get("error")

        for r_idx in range(3, 9):
            ws_corr[f"A{r_idx}"].font = HEADER_FONT

        sol = grade_result.get("solution") or {}
        if sol:
            ws_corr["A10"] = "Valores de Variables:"
            ws_corr["A10"].font = HEADER_FONT
            ws_corr["A11"] = "Variable"
            ws_corr["B11"] = "Valor Óptimo"
            ws_corr["A11"].font = HEADER_FONT
            ws_corr["B11"].font = HEADER_FONT
            ws_corr["A11"].fill = HEADER_FILL
            ws_corr["B11"].fill = HEADER_FILL
            ws_corr["A11"].border = THIN_BORDER
            ws_corr["B11"].border = THIN_BORDER

            s_row = 12
            for v_name, v_val in sol.items():
                ws_corr.cell(row=s_row, column=1, value=v_name).border = THIN_BORDER
                ws_corr.cell(row=s_row, column=2, value=v_val).border = THIN_BORDER
                s_row += 1
    else:
        ws_corr["A3"] = "No se proveyó dictamen del corrector."

    # Adjust column widths automatically
    for ws in (ws_model, ws_solver, ws_corr):
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    wb.save(p)
    return p
