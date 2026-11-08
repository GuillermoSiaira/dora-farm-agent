"""SPEC-45: Phase A acceptance tests (offline, no network, DORA_OFFLINE=1)."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import tempfile
import numpy as np
import openpyxl
from openpyxl.utils import get_column_letter
import pytest
from scipy.optimize import linprog
import formulas

from dora.scenario import Scenario
from dora.engine import optimize, LPModel
from dora.spreadsheet import (
    export_plan_xlsx,
    FORMULA_LINKED_INPUTS,
    VALUE_ONLY_INPUTS,
    is_formula_linked,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = ROOT_DIR / "docs" / "ejemplos" / "planillas"

SCENARIOS = {
    "pampas_core_2000": {
        "region": "pampas_core",
        "area_ha": 2000,
        "owned_ha": 2000,
        "own_capital_usd": 500000,
    },
    "se_ba_500": {
        "region": "southeast_buenos_aires",
        "area_ha": 500,
        "owned_ha": 500,
        "own_capital_usd": 50000,
    },
    "rented_300": {
        "region": "pampas_core",
        "area_ha": 300,
        "owned_ha": 0,
        "own_capital_usd": 30000,
        "credit_line_usd": 200000,
    },
    "se_ba_rent_out": {
        "region": "southeast_buenos_aires",
        "area_ha": 500,
        "owned_ha": 500,
        "own_capital_usd": 50000,
        "allow_rent_out": True,
    },
    "livestock_500": {
        "region": "southeast_buenos_aires",
        "area_ha": 500,
        "owned_ha": 500,
        "own_capital_usd": 100000,
        "crops": [],
        "livestock": ["cow_calf"],
    },
}


def _solve_highs_from_workbook_eval(wb: openpyxl.Workbook, calc: dict, bname: str, lp: LPModel) -> tuple[float, np.ndarray]:
    """Read evaluated model matrix from formulas calculation and solve with HiGHS."""
    N = len(lp.c)
    M_eq = len(lp.b_eq)
    M_ub = len(lp.b_ub)

    # 1. Objective: row 6 has -c_j (or c_j for maximization)
    c_eval = np.zeros(N)
    for j in range(N):
        col_letter = get_column_letter(3 + j)
        k = f"'[{bname}]MODELO'!{col_letter}6"
        c_eval[j] = -float(np.asarray(calc[k].value).flat[0])

    # 2. Bounds from rows 4 and 5
    bounds_eval = []
    for j in range(N):
        col_letter = get_column_letter(3 + j)
        k_lb = f"'[{bname}]MODELO'!{col_letter}4"
        k_ub = f"'[{bname}]MODELO'!{col_letter}5"
        lb_val = calc[k_lb].value
        lb = float(np.asarray(lb_val).flat[0]) if lb_val is not None and str(lb_val) != "" else 0.0
        ub_val = wb["Modelo"].cell(row=5, column=3 + j).value
        ub = float(ub_val) if ub_val is not None and ub_val != "" else None
        bounds_eval.append((lb, ub))

    # 3. Equalities: rows 11 to 11 + M_eq - 1
    A_eq_eval = np.zeros((M_eq, N))
    b_eq_eval = np.zeros(M_eq)
    col_rhs_letter = get_column_letter(2 + N + 3)

    for i in range(M_eq):
        r = 11 + i
        k_rhs = f"'[{bname}]MODELO'!{col_rhs_letter}{r}"
        b_eq_eval[i] = float(np.asarray(calc[k_rhs].value).flat[0])
        for j in range(N):
            col_letter = get_column_letter(3 + j)
            cell_val = wb["Modelo"].cell(row=r, column=3 + j).value
            if cell_val is not None and cell_val != "":
                if str(cell_val).startswith("="):
                    k_cell = f"'[{bname}]MODELO'!{col_letter}{r}"
                    A_eq_eval[i, j] = float(np.asarray(calc[k_cell].value).flat[0])
                else:
                    A_eq_eval[i, j] = float(cell_val)

    # 4. Inequalities: rows 11 + M_eq to 11 + M_eq + M_ub - 1
    A_ub_eval = np.zeros((M_ub, N))
    b_ub_eval = np.zeros(M_ub)
    for k_idx in range(M_ub):
        r = 11 + M_eq + k_idx
        k_rhs = f"'[{bname}]MODELO'!{col_rhs_letter}{r}"
        b_ub_eval[k_idx] = float(np.asarray(calc[k_rhs].value).flat[0])
        for j in range(N):
            col_letter = get_column_letter(3 + j)
            cell_val = wb["Modelo"].cell(row=r, column=3 + j).value
            if cell_val is not None and cell_val != "":
                if str(cell_val).startswith("="):
                    k_cell = f"'[{bname}]MODELO'!{col_letter}{r}"
                    A_ub_eval[k_idx, j] = float(np.asarray(calc[k_cell].value).flat[0])
                else:
                    A_ub_eval[k_idx, j] = float(cell_val)

    res = linprog(
        c=c_eval,
        A_ub=A_ub_eval,
        b_ub=b_ub_eval,
        A_eq=A_eq_eval,
        b_eq=b_eq_eval,
        bounds=bounds_eval,
        method="highs",
    )
    assert res.success, f"HiGHS solver failed: {res.message}"
    npv = -res.fun - lp.obj_constant
    return npv, res.x


# -----------------------------------------------------------------------------
# Test 1: Labels and engine LP model identity
# -----------------------------------------------------------------------------
def test_1_labels():
    """1. Every variable and row has a label; keep_lp=True changes no numbers; linprog on LPModel reproduces x and NPV."""
    sc = Scenario(**SCENARIOS["pampas_core_2000"])
    base_res = optimize(sc, keep_lp=False)
    lp_res = optimize(sc, keep_lp=True)

    # Output identity
    assert lp_res.npv == base_res.npv
    assert lp_res.hectares == base_res.hectares
    assert lp_res.cash == base_res.cash

    lp = lp_res.lp
    assert lp is not None

    # Variable labels
    assert len(lp.var_labels) == len(lp.c)
    for lbl in lp.var_labels:
        assert lbl.get("key"), "Variable label must have machine key"
        assert lbl.get("desc_es"), "Variable label must have Spanish description"
        assert lbl.get("desc_en"), "Variable label must have English description"

    # Row labels
    total_rows = len(lp.b_eq) + len(lp.b_ub)
    assert len(lp.row_labels) == total_rows
    for rlbl in lp.row_labels:
        assert rlbl.get("group"), "Row label must have group"
        assert rlbl.get("key"), "Row label must have key"
        assert rlbl.get("desc_es"), "Row label must have Spanish description"
        assert rlbl.get("desc_en"), "Row label must have English description"
        assert rlbl.get("sense") in ("=", "<="), f"Invalid sense {rlbl.get('sense')}"

    # Independent linprog on LPModel
    highs = linprog(
        c=lp.c,
        A_ub=lp.A_ub,
        b_ub=lp.b_ub,
        A_eq=lp.A_eq,
        b_eq=lp.b_eq,
        bounds=lp.bounds,
        method="highs",
    )
    assert highs.success
    npv_highs = -highs.fun - lp.obj_constant
    assert abs(npv_highs - lp_res.npv) < 1e-5
    np.testing.assert_allclose(highs.x, lp.x, atol=1e-5)


# -----------------------------------------------------------------------------
# Test 2: Model sheet layout and named ranges
# -----------------------------------------------------------------------------
def test_2_model_sheet_layout():
    """2. Named ranges exist; equalities before <= rows; zero matrix cells are blank."""
    xlsx_bytes = export_plan_xlsx(SCENARIOS["pampas_core_2000"], lang="es")
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))

    # Sheet order
    assert "Modelo" in wb.sheetnames
    assert "__OpenSolver__" in wb.sheetnames
    assert wb["__OpenSolver__"].sheet_state == "hidden"

    # Required named ranges
    for nr in ("dora_vars", "dora_objective", "dora_eq_lhs", "dora_eq_rhs", "dora_le_lhs", "dora_le_rhs"):
        assert nr in wb.defined_names, f"Missing named range: {nr}"

    ws = wb["Modelo"]

    # Row 1-2: var descriptions & keys
    assert ws.cell(row=1, column=1).value == "Descripción"
    assert ws.cell(row=2, column=1).value in ("Clave", "Key", "Variable")

    # Row 3: Decision cells (dora_vars)
    assert ws.cell(row=3, column=1).value in ("Valor del plan", "Plan values", "Variables de decisión (óptimo DORA)")

    # Row 8: Objective cell (dora_objective)
    assert "=SUMPRODUCT" in str(ws.cell(row=8, column=2).value)

    # Check constraint rows
    sc = Scenario(**SCENARIOS["pampas_core_2000"])
    res = optimize(sc, keep_lp=True)
    M_eq = len(res.lp.b_eq)
    M_ub = len(res.lp.b_ub)
    N = len(res.lp.c)
    col_sense = 2 + N + 2

    # Equalities come first
    for i in range(M_eq):
        r = 11 + i
        assert ws.cell(row=r, column=col_sense).value == "="

    # Inequalities come second
    for k in range(M_ub):
        r = 11 + M_eq + k
        assert ws.cell(row=r, column=col_sense).value == "<="

    # Check that zeros in coefficient matrix are blank (None or "")
    blank_zeros_count = 0
    non_zeros_count = 0
    for r in range(11, 11 + M_eq + M_ub):
        for c_idx in range(3, 3 + N):
            val = ws.cell(row=r, column=c_idx).value
            if val is None or val == "":
                blank_zeros_count += 1
            else:
                non_zeros_count += 1
    assert non_zeros_count > 100
    assert blank_zeros_count > 500, f"Expected sparse blank cells, got {blank_zeros_count}"


# -----------------------------------------------------------------------------
# Test 3: Solver defined names and lp-minimo.xlsx
# -----------------------------------------------------------------------------
def test_3_solver_names():
    """3. Excel defined names present with right codes; lp-minimo.xlsx gives known optimum."""
    xlsx_bytes = export_plan_xlsx(SCENARIOS["pampas_core_2000"], lang="es")
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))

    for sn in ("solver_opt", "solver_typ", "solver_adj", "solver_neg", "solver_lin", "solver_eng", "solver_num"):
        assert sn in wb.defined_names, f"Missing solver defined name: {sn}"

    # Check lp-minimo.xlsx
    min_path = EXAMPLES_DIR / "lp-minimo.xlsx"
    assert min_path.exists(), "lp-minimo.xlsx must exist in docs/ejemplos/planillas/"

    wb_min = openpyxl.load_workbook(min_path)
    ws_min = wb_min["Modelo"]
    assert ws_min["B8"].value == "=SUMPRODUCT(B6:D6, B3:D3)"

    # Solve lp-minimo independently with HiGHS
    c_min = [-float(ws_min["B6"].value), -float(ws_min["C6"].value), -float(ws_min["D6"].value)]
    A_ub_min = [
        [float(ws_min["B11"].value), float(ws_min["C11"].value), float(ws_min["D11"].value)],
        [float(ws_min["B12"].value), float(ws_min["C12"].value), float(ws_min["D12"].value)],
    ]
    b_ub_min = [float(ws_min["G11"].value), float(ws_min["G12"].value)]
    bounds_min = [(0, None), (0, None), (0, None)]

    sol = linprog(c=c_min, A_ub=A_ub_min, b_ub=b_ub_min, bounds=bounds_min, method="highs")
    assert sol.success
    np.testing.assert_allclose(sol.x, [2.5, 1.5, 0.0], atol=1e-5)
    assert abs(-sol.fun - 10.5) < 1e-5


# -----------------------------------------------------------------------------
# Test 4: Independent re-solve on unedited scenarios (A5)
# -----------------------------------------------------------------------------
def test_4_independent_resolve_unedited():
    """4. HiGHS solves the workbook's evaluated model independently: NPV matches DORA <= 0.01 USD."""
    for name, sc_dict in SCENARIOS.items():
        sc = Scenario(**sc_dict)
        dora_res = optimize(sc, keep_lp=True)
        xlsx_bytes = export_plan_xlsx(sc_dict, lang="es")

        tf = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        tf.write(xlsx_bytes)
        tf.close()

        try:
            wb = openpyxl.load_workbook(tf.name)
            xl = formulas.ExcelModel().loads(tf.name).finish()
            calc = xl.calculate()
            bname = os.path.basename(tf.name)

            npv_highs, x_highs = _solve_highs_from_workbook_eval(wb, calc, bname, dora_res.lp)
            diff_npv = abs(npv_highs - dora_res.npv)
            assert diff_npv < 0.01, f"NPV mismatch on {name}: HiGHS={npv_highs:.2f}, DORA={dora_res.npv:.2f}, diff={diff_npv:.4f}"

            # Check decision variables match
            diff_x = np.max(np.abs(x_highs - dora_res.lp.x))
            assert diff_x < 0.01, f"Decisions mismatch on {name}: max diff={diff_x}"
        finally:
            try:
                os.unlink(tf.name)
            except OSError:
                pass


# -----------------------------------------------------------------------------
# Test 5: Independent re-solve after edits (A5)
# -----------------------------------------------------------------------------
def test_5_independent_resolve_after_edits():
    """5. Edit inputs in Supuestos, evaluate with formulas, solve with HiGHS, compare to DORA on edited scenario."""
    base_dict = SCENARIOS["pampas_core_2000"]
    base_sc = Scenario(**base_dict)

    # Edit 1: Soybean price +20%
    xlsx_bytes = export_plan_xlsx(base_dict, lang="es")
    wb1 = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    ws_assump = wb1["Supuestos"]

    p_row = None
    for r in range(2, ws_assump.max_row + 1):
        if ws_assump.cell(row=r, column=1).value == "prices.soybean":
            p_row = r
            break
    assert p_row is not None
    orig_p = float(ws_assump.cell(row=p_row, column=3).value)
    new_p = orig_p * 1.20
    ws_assump.cell(row=p_row, column=3, value=new_p)

    tf1 = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    wb1.save(tf1.name)
    tf1.close()

    try:
        xl1 = formulas.ExcelModel().loads(tf1.name).finish()
        calc1 = xl1.calculate()
        bname1 = os.path.basename(tf1.name)

        sc_edit1 = dict(base_dict)
        sc_edit1["prices"] = {"soybean": new_p}
        dora_edit1 = optimize(Scenario(**sc_edit1), keep_lp=True)

        npv1, _ = _solve_highs_from_workbook_eval(wb1, calc1, bname1, dora_edit1.lp)
        diff1 = abs(npv1 - dora_edit1.npv)
        assert diff1 < 0.01, f"Edit 1 (Soybean +20%) mismatch: HiGHS={npv1:.2f}, DORA={dora_edit1.npv:.2f}, diff={diff1:.4f}"
    finally:
        try: os.unlink(tf1.name)
        except OSError: pass

    # Edit 2: Own capital * 2
    wb2 = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    ws_assump2 = wb2["Supuestos"]
    cap_row = None
    for r in range(2, ws_assump2.max_row + 1):
        if ws_assump2.cell(row=r, column=1).value == "own_capital_usd":
            cap_row = r
            break
    assert cap_row is not None
    orig_cap = float(ws_assump2.cell(row=cap_row, column=3).value)
    new_cap = orig_cap * 2.0
    ws_assump2.cell(row=cap_row, column=3, value=new_cap)

    tf2 = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    wb2.save(tf2.name)
    tf2.close()

    try:
        xl2 = formulas.ExcelModel().loads(tf2.name).finish()
        calc2 = xl2.calculate()
        bname2 = os.path.basename(tf2.name)

        sc_edit2 = dict(base_dict)
        sc_edit2["own_capital_usd"] = new_cap
        dora_edit2 = optimize(Scenario(**sc_edit2), keep_lp=True)

        npv2, _ = _solve_highs_from_workbook_eval(wb2, calc2, bname2, dora_edit2.lp)
        diff2 = abs(npv2 - dora_edit2.npv)
        assert diff2 < 0.01, f"Edit 2 (Own capital x2) mismatch: HiGHS={npv2:.2f}, DORA={dora_edit2.npv:.2f}, diff={diff2:.4f}"
    finally:
        try: os.unlink(tf2.name)
        except OSError: pass

    # Edit 3: Corn yield -15%
    wb3 = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    ws_assump3 = wb3["Supuestos"]
    y_row = None
    for r in range(2, ws_assump3.max_row + 1):
        if ws_assump3.cell(row=r, column=1).value == "yields.corn":
            y_row = r
            break
    assert y_row is not None
    orig_y = float(ws_assump3.cell(row=y_row, column=3).value)
    new_y = orig_y * 0.85
    ws_assump3.cell(row=y_row, column=3, value=new_y)

    tf3 = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    wb3.save(tf3.name)
    tf3.close()

    try:
        xl3 = formulas.ExcelModel().loads(tf3.name).finish()
        calc3 = xl3.calculate()
        bname3 = os.path.basename(tf3.name)

        sc_edit3 = dict(base_dict)
        sc_edit3["yields"] = {"corn": new_y}
        dora_edit3 = optimize(Scenario(**sc_edit3), keep_lp=True)

        npv3, _ = _solve_highs_from_workbook_eval(wb3, calc3, bname3, dora_edit3.lp)
        diff3 = abs(npv3 - dora_edit3.npv)
        assert diff3 < 0.01, f"Edit 3 (Corn yield -15%) mismatch: HiGHS={npv3:.2f}, DORA={dora_edit3.npv:.2f}, diff={diff3:.4f}"
    finally:
        try: os.unlink(tf3.name)
        except OSError: pass

    # Value-only inputs verification
    assert not is_formula_linked("credit_rate_annual")
    assert not is_formula_linked("discount_rate_annual")
    assert not is_formula_linked("monthly_price_rise")
    assert not is_formula_linked("routes")
    assert is_formula_linked("prices.soybean")
    assert is_formula_linked("own_capital_usd")
    assert is_formula_linked("yields.corn")


# -----------------------------------------------------------------------------
# Test 10: Example spreadsheets (A10)
# -----------------------------------------------------------------------------
def test_10_examples():
    """10. All 6 example files exist, open cleanly, are < 1 MB, and README.md exists."""
    assert EXAMPLES_DIR.exists(), "docs/ejemplos/planillas must exist"

    expected_files = [
        "pampas-core-2000ha.xlsx",
        "se-ba-500ha.xlsx",
        "rented-300ha.xlsx",
        "se-ba-rent-out.xlsx",
        "livestock-500ha.xlsx",
        "iowa-400ha.xlsx",
    ]

    for fname in expected_files:
        fpath = EXAMPLES_DIR / fname
        assert fpath.exists(), f"Example file missing: {fname}"
        size_bytes = fpath.stat().st_size
        assert size_bytes < 1024 * 1024, f"File {fname} is {size_bytes} bytes (>= 1 MB)"

        # Verify it opens with openpyxl
        wb = openpyxl.load_workbook(fpath)
        assert "Modelo" in wb.sheetnames, f"'Modelo' sheet missing in {fname}"
        assert "__OpenSolver__" in wb.sheetnames, f"'__OpenSolver__' sheet missing in {fname}"

    readme_path = EXAMPLES_DIR / "README.md"
    assert readme_path.exists(), "README.md missing in docs/ejemplos/planillas"
    readme_text = readme_path.read_text(encoding="utf-8")
    assert "OpenSolver" in readme_text
    assert "Google Sheets" in readme_text
    assert "lp-minimo.xlsx" in readme_text
