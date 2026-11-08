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
    read_plan_xlsx,
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


# -----------------------------------------------------------------------------
# Test 6: Outside-DORA flag (A6)
# -----------------------------------------------------------------------------
def test_6_outside_dora_flag():
    """6. Change one decision cell -> Verification flips to outside DORA. Restore -> flips back. Overwrite formula -> Cambiaste el modelo."""
    sc_dict = SCENARIOS["pampas_core_2000"]
    xlsx_bytes = export_plan_xlsx(sc_dict, lang="es")

    tf = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tf.write(xlsx_bytes)
    tf.close()

    try:
        xl = formulas.ExcelModel().loads(tf.name).finish()
        calc = xl.calculate()
        bname = os.path.basename(tf.name)

        # Baseline: plan verified
        k_b5 = next(k for k in calc.keys() if k.endswith("!B5") and "VERIF" in k.upper())
        val_status = str(calc[k_b5].value)
        assert "Plan de DORA, verificado" in val_status
        val_sum = str(calc[f"'[{bname}]RESUMEN'!A1"].value)
        assert "Este plan era el óptimo" in val_sum
    finally:
        try: os.unlink(tf.name)
        except OSError: pass

    # Case 2: Change one decision cell in Modelo (dora_vars)
    wb2 = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    orig_c3 = float(wb2["Modelo"]["C3"].value or 0.0)
    wb2["Modelo"]["C3"] = orig_c3 + 10.0

    tf2 = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    wb2.save(tf2.name)
    tf2.close()

    try:
        xl2 = formulas.ExcelModel().loads(tf2.name).finish()
        calc2 = xl2.calculate()
        bname2 = os.path.basename(tf2.name)

        k_b5_2 = next(k for k in calc2.keys() if k.endswith("!B5") and "VERIF" in k.upper())
        val_status2 = str(calc2[k_b5_2].value)
        assert "Plan recalculado fuera de DORA" in val_status2
        val_sum2 = str(calc2[f"'[{bname2}]RESUMEN'!A1"].value)
        assert "Plan recalculado fuera de DORA" in val_sum2

        # Case 3: Restore C3 back to orig_c3
        wb2["Modelo"]["C3"] = orig_c3
        wb2.save(tf2.name)
        xl2_restored = formulas.ExcelModel().loads(tf2.name).finish()
        calc2_restored = xl2_restored.calculate()
        k_b5_3 = next(k for k in calc2_restored.keys() if k.endswith("!B5") and "VERIF" in k.upper())
        val_status2_restored = str(calc2_restored[k_b5_3].value)
        assert "Plan de DORA, verificado" in val_status2_restored

        # Case 4: Overwrite a model formula coefficient with a constant
        ws_model = wb2["Modelo"]
        f_coord = None
        for r in range(11, ws_model.max_row + 1):
            for c in range(3, ws_model.max_column - 3):
                cell_v = ws_model.cell(row=r, column=c).value
                if cell_v and str(cell_v).startswith("="):
                    f_coord = (r, c)
                    break
            if f_coord:
                break
        assert f_coord is not None, "Expected formula cells in Modelo"
        ws_model.cell(row=f_coord[0], column=f_coord[1], value=999.0)
        wb2.save(tf2.name)

        xl2_tampered = formulas.ExcelModel().loads(tf2.name).finish()
        calc2_tampered = xl2_tampered.calculate()
        k_b5_4 = next(k for k in calc2_tampered.keys() if k.endswith("!B5") and "VERIF" in k.upper())
        val_status2_tampered = str(calc2_tampered[k_b5_4].value)
        assert "Cambiaste el modelo" in val_status2_tampered
    finally:
        try: os.unlink(tf2.name)
        except OSError: pass


# -----------------------------------------------------------------------------
# Test 7: Read back (A7)
# -----------------------------------------------------------------------------
def test_7_read_back():
    """7. Read back re-solved optimum -> same_plan: True; perturbed to worse -> reason 'worse'; hand-edited coefficient -> reason 'model edited'."""
    base_dict = SCENARIOS["pampas_core_2000"]
    xlsx_bytes = export_plan_xlsx(base_dict, lang="es")

    # 7a: Re-solved optimum with edited soybean price
    wb1 = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    ws_assump1 = wb1["Supuestos"]
    p_row = None
    for r in range(2, ws_assump1.max_row + 1):
        if ws_assump1.cell(row=r, column=1).value == "prices.soybean":
            p_row = r
            break
    assert p_row is not None
    orig_p = float(ws_assump1.cell(row=p_row, column=3).value)
    new_p = orig_p * 1.20
    ws_assump1.cell(row=p_row, column=3, value=new_p)

    sc_edit = dict(base_dict)
    sc_edit["prices"] = {"soybean": new_p}
    dora_edit = optimize(Scenario(**sc_edit), keep_lp=True)

    for j in range(len(dora_edit.lp.c)):
        wb1["Modelo"].cell(row=3, column=3 + j, value=float(dora_edit.lp.x[j]))

    buf1 = io.BytesIO()
    wb1.save(buf1)
    res1 = read_plan_xlsx(buf1.getvalue(), lang="es")
    assert res1.get("same_plan") is True, f"Expected same_plan True, got: {res1.get('reason')}"
    assert "verificado" in res1.get("reason", "").lower()

    # 7b: Decisions perturbed to a feasible worse point
    wb2 = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    sc_base = Scenario(**base_dict)
    base_opt = optimize(sc_base, keep_lp=True)
    s_last_key = f"S[p{len(base_opt.cash) - 1}]"
    s_col = None
    for j, l in enumerate(base_opt.lp.var_labels):
        if l["key"] == s_last_key:
            s_col = 3 + j
            break
    assert s_col is not None
    orig_s = float(wb2["Modelo"].cell(row=3, column=s_col).value or 0.0)
    wb2["Modelo"].cell(row=3, column=s_col, value=max(0.0, orig_s - 50000.0))

    buf2 = io.BytesIO()
    wb2.save(buf2)
    res2 = read_plan_xlsx(buf2.getvalue(), lang="es")
    assert res2.get("same_plan") is False
    assert res2.get("reason") == "worse"

    # 7c: Hand-edited model coefficient
    wb3 = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    cur_val = float(wb3["Modelo"].cell(row=11, column=3).value or 0.0)
    wb3["Modelo"].cell(row=11, column=3, value=cur_val + 5.0)

    buf3 = io.BytesIO()
    wb3.save(buf3)
    res3 = read_plan_xlsx(buf3.getvalue(), lang="es")
    assert res3.get("same_plan") is False
    assert res3.get("reason") == "model edited"


# -----------------------------------------------------------------------------
# Test 8: Sales strategy (A8)
# -----------------------------------------------------------------------------
def test_8_sales_strategy():
    """8. Estrategia de venta has notice, correct tables, decision tonnes, formula incomes matching engine."""
    sc_dict = SCENARIOS["pampas_core_2000"]
    xlsx_bytes = export_plan_xlsx(sc_dict, lang="es")
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))

    assert "Estrategia de venta" in wb.sheetnames
    ws_sales = wb["Estrategia de venta"]

    # Notice
    assert "Esto es cuándo, cuánto y por dónde vender" in str(ws_sales["A2"].value)

    # Table 1: Sales detail
    assert "DETALLE DE VENTAS" in str(ws_sales["A4"].value)
    t2_row = None
    for r in range(5, ws_sales.max_row + 1):
        if "RESUMEN" in str(ws_sales.cell(row=r, column=1).value or ""):
            t2_row = r
            break
    assert t2_row is not None

    # Check Table 1 rows have formula incomes
    for r in range(7, t2_row):
        crop = ws_sales.cell(row=r, column=1).value
        if not crop: continue
        assert str(ws_sales.cell(row=r, column=8).value).startswith("=D")

    # Evaluate with formulas
    tf = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    wb.save(tf.name)
    tf.close()

    try:
        xl = formulas.ExcelModel().loads(tf.name).finish()
        calc = xl.calculate()
        bname = os.path.basename(tf.name)

        sc = Scenario(**sc_dict)
        opt = optimize(sc)

        tot_eval_income = 0.0
        for r in range(7, t2_row):
            crop = ws_sales.cell(row=r, column=1).value
            if not crop: continue
            k_inc = f"'[{bname}]ESTRATEGIA DE VENTA'!H{r}"
            inc_val = float(np.asarray(calc[k_inc].value).flat[0])
            tot_eval_income += inc_val

        engine_tot_sales = sum(sum(p_data.get("sales", {}).values()) for p_data in opt.cash_ledger)
        diff_sales = abs(tot_eval_income - engine_tot_sales)
        assert diff_sales < 0.01, f"Sales income diff: {diff_sales}"
    finally:
        try: os.unlink(tf.name)
        except OSError: pass


# -----------------------------------------------------------------------------
# Test 9: Verification text (A9)
# -----------------------------------------------------------------------------
def test_9_verification_text():
    """9. Verification text shows model name when given, 'armado a mano' otherwise, top sentence, hashes."""
    sc_dict1 = dict(SCENARIOS["pampas_core_2000"])
    sc_dict1["model"] = "claude-3-5-sonnet-20241022"
    wb1 = openpyxl.load_workbook(io.BytesIO(export_plan_xlsx(sc_dict1, lang="es")))
    ws_verif1 = wb1["Verificación"]

    assert "Cada número de este plan lo calculó el motor de DORA" in ws_verif1["A2"].value
    assert ws_verif1["B7"].value == "claude-3-5-sonnet-20241022"

    sc_dict2 = dict(SCENARIOS["pampas_core_2000"])
    wb2 = openpyxl.load_workbook(io.BytesIO(export_plan_xlsx(sc_dict2, lang="es")))
    ws_verif2 = wb2["Verificación"]
    assert ws_verif2["B7"].value == "armado a mano en la pestaña Escenario"

    has_fp = False
    has_sc_hash = False
    has_res_hash = False
    for r in range(10, ws_verif2.max_row + 1):
        lbl = str(ws_verif2.cell(row=r, column=1).value or "")
        val = str(ws_verif2.cell(row=r, column=2).value or "")
        if "Huella digital" in lbl: has_fp = len(val) == 64
        if "Hash del escenario" in lbl: has_sc_hash = len(val) == 64
        if "Hash del resultado" in lbl: has_res_hash = len(val) == 64
    assert has_fp and has_sc_hash and has_res_hash


# -----------------------------------------------------------------------------
# Test 11: Whole workbook reactivity (A11)
# -----------------------------------------------------------------------------
def test_11_whole_workbook_follows_plan():
    """11. Write re-solved x into dora_vars, evaluate with formulas: Cash, Plan por cultivo, Estrategia match DORA <= 0.01."""
    base_dict = SCENARIOS["pampas_core_2000"]
    xlsx_bytes = export_plan_xlsx(base_dict, lang="es")
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    ws_assump = wb["Supuestos"]

    p_row = None
    for r in range(2, ws_assump.max_row + 1):
        if ws_assump.cell(row=r, column=1).value == "prices.soybean":
            p_row = r
            break
    orig_p = float(ws_assump.cell(row=p_row, column=3).value)
    new_p = orig_p * 1.20
    ws_assump.cell(row=p_row, column=3, value=new_p)

    sc_edit = dict(base_dict)
    sc_edit["prices"] = {"soybean": new_p}
    dora_edit = optimize(Scenario(**sc_edit), keep_lp=True)

    ws_model = wb["Modelo"]
    for j in range(len(dora_edit.lp.c)):
        ws_model.cell(row=3, column=3 + j, value=float(dora_edit.lp.x[j]))

    tf = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    wb.save(tf.name)
    tf.close()

    try:
        xl = formulas.ExcelModel().loads(tf.name).finish()
        calc = xl.calculate()
        bname = os.path.basename(tf.name)

        # Plan por cultivo hectares match
        ws_crops = wb["Plan por cultivo"]
        for r in range(2, ws_crops.max_row):
            crop = ws_crops.cell(row=r, column=1).value
            if crop == "TOTAL": continue
            k_ha = f"'[{bname}]PLAN POR CULTIVO'!B{r}"
            ha_eval = float(np.asarray(calc[k_ha].value).flat[0])
            ha_exp = float(dora_edit.hectares.get(crop, 0.0))
            assert abs(ha_eval - ha_exp) < 0.01

        # Caja por quincena matches
        for p in range(len(dora_edit.cash)):
            r = p + 2
            k_close = f"'[{bname}]CAJA POR QUINCENA'!N{r}"
            close_eval = float(np.asarray(calc[k_close].value).flat[0])
            close_exp = float(dora_edit.cash[p])
            assert abs(close_eval - close_exp) < 0.01, f"Cash mismatch at Q{p+1}: eval={close_eval}, exp={close_exp}"

            k_debt = f"'[{bname}]CAJA POR QUINCENA'!O{r}"
            debt_eval = float(np.asarray(calc[k_debt].value).flat[0])
            debt_exp = float(dora_edit.debt[p])
            assert abs(debt_eval - debt_exp) < 0.01, f"Debt mismatch at Q{p+1}: eval={debt_eval}, exp={debt_exp}"

            k_draw = f"'[{bname}]CAJA POR QUINCENA'!L{r}"
            draw_eval = float(np.asarray(calc[k_draw].value).flat[0])
            draw_exp = float(dora_edit.credit_drawn[p])
            assert abs(draw_eval - draw_exp) < 0.01, f"Credit drawn mismatch at Q{p+1}: eval={draw_eval}, exp={draw_exp}"
    finally:
        try: os.unlink(tf.name)
        except OSError: pass


# -----------------------------------------------------------------------------
# Test 12: Visible economic checks (A12)
# -----------------------------------------------------------------------------
def test_12_visible_checks():
    """12. DORA plan: all fortnight checks OK; hand-edited credit beyond line -> ERROR in red and Verification alert."""
    sc_dict = SCENARIOS["pampas_core_2000"]
    xlsx_bytes = export_plan_xlsx(sc_dict, lang="es")

    tf1 = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tf1.write(xlsx_bytes)
    tf1.close()

    try:
        xl1 = formulas.ExcelModel().loads(tf1.name).finish()
        calc1 = xl1.calculate()
        bname1 = os.path.basename(tf1.name)

        # In DORA plan, all checks OK
        for p in range(30):
            r = p + 2
            for col_letter in ("P", "Q", "R", "S"):
                k = f"'[{bname1}]CAJA POR QUINCENA'!{col_letter}{r}"
                val = str(calc1[k].value)
                assert "OK" in val, f"Check {col_letter} failed at Q{p+1}: {val}"

        k_verif = next(k for k in calc1.keys() if k.endswith("!B6") and "VERIF" in k.upper())
        assert "Todas las restricciones por quincena se cumplen" in str(calc1[k_verif].value)
    finally:
        try: os.unlink(tf1.name)
        except OSError: pass

    # Hand-edit debt variable D[p5] beyond credit line
    wb2 = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    ws_model = wb2["Modelo"]
    dp5_col = None
    for c in range(3, ws_model.max_column + 1):
        if ws_model.cell(row=2, column=c).value == "D[p5]":
            dp5_col = c
            break
    assert dp5_col is not None
    # Set debt to 1,000,000 (credit line is 0 for pampas_core_2000)
    ws_model.cell(row=3, column=dp5_col, value=1000000.0)

    tf2 = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    wb2.save(tf2.name)
    tf2.close()

    try:
        xl2 = formulas.ExcelModel().loads(tf2.name).finish()
        calc2 = xl2.calculate()
        bname2 = os.path.basename(tf2.name)

        # Check Col Q at Q6 (p=5, r=7) shows ERROR
        k_q6 = f"'[{bname2}]CAJA POR QUINCENA'!Q7"
        assert "ERROR" in str(calc2[k_q6].value)

        # Verification summary shows failure
        k_verif2 = next(k for k in calc2.keys() if k.endswith("!B6") and "VERIF" in k.upper())
        assert "Restricciones por quincena no cumplidas" in str(calc2[k_verif2].value)
    finally:
        try: os.unlink(tf2.name)
        except OSError: pass


# -----------------------------------------------------------------------------
# Test 13: Shadow prices (A13)
# -----------------------------------------------------------------------------
def test_13_shadow_prices():
    """13. Duals in Modelo match DORA shadow prices, reduced costs present, Resumen block has human-readable duals."""
    sc_dict = SCENARIOS["pampas_core_2000"]
    sc = Scenario(**sc_dict)
    res = optimize(sc, keep_lp=True)

    xlsx_bytes = export_plan_xlsx(sc_dict, lang="es")
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))

    ws_model = wb["Modelo"]
    N = len(res.lp.c)
    col_sp = 2 + N + 4

    M_eq = len(res.lp.b_eq)
    M_ub = len(res.lp.b_ub)

    # Check duals in Modelo column
    for i in range(M_eq):
        r = 11 + i
        val = float(ws_model.cell(row=r, column=col_sp).value or 0.0)
        exp_sp = float(res.lp.duals_eq[i])
        assert abs(val - exp_sp) < 1e-4

    for k in range(M_ub):
        r = 11 + M_eq + k
        val = float(ws_model.cell(row=r, column=col_sp).value or 0.0)
        exp_sp = float(res.lp.duals_ub[k])
        assert abs(val - exp_sp) < 1e-4

    # Check reduced costs in row 7
    assert ws_model.cell(row=7, column=1).value == "Costo reducido (DORA)"
    for j in range(N):
        val_rc = float(ws_model.cell(row=7, column=3 + j).value or 0.0)
        exp_rc = float(res.lp.reduced_costs[j])
        assert abs(val_rc - exp_rc) < 1e-4

    # Check Resumen block
    ws_sum = wb["Resumen"]
    resumen_text = ""
    for r in range(1, ws_sum.max_row + 1):
        for c in range(1, ws_sum.max_column + 1):
            val = ws_sum.cell(row=r, column=c).value
            if val: resumen_text += " " + str(val)

    assert "RECURSOS QUE LIMITAN EL PLAN (PRECIOS SOMBRA)" in resumen_text
    assert "OpenSolver para Google Sheets no entrega informe de sensibilidad" in resumen_text
    assert "Tierra propia" in resumen_text

# -----------------------------------------------------------------------------
# Test 14: Summary shadow-price block (A13 / Review Point 1)
# -----------------------------------------------------------------------------
def test_14_summary_shadow_block():
    """14. Summary sheet shadow-price block: <= 6 rows, mentions 'sin sembrar' (624 +/- 1 ha),
    soybean rotation, no cash line says 'vale 1,5...', and fortnight 1 gain matches capital_shadow_price <= 0.01.
    """
    sc_dict = SCENARIOS["pampas_core_2000"]
    sc = Scenario(**sc_dict)
    res = optimize(sc, keep_lp=True)
    xlsx_bytes = export_plan_xlsx(sc_dict, lang="es")
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    ws_sum = wb["Resumen"]

    start_r = None
    for r in range(1, ws_sum.max_row + 1):
        v = ws_sum.cell(row=r, column=1).value
        if v and "PRECIOS SOMBRA" in str(v).upper():
            start_r = r
            break
    assert start_r is not None, "Shadow prices block title not found in Resumen"

    # Collect rows of the block until an empty row or end of sheet
    block_rows = []
    for r in range(start_r + 1, ws_sum.max_row + 1):
        val_a = ws_sum.cell(row=r, column=1).value
        val_b = ws_sum.cell(row=r, column=2).value
        if val_a is None and val_b is None:
            break
        text = f"{val_a or ''} {val_b or ''}".strip()
        if text:
            block_rows.append(text)

    # 1. At most 6 rows
    assert len(block_rows) <= 6, f"Expected at most 6 rows in shadow block, got {len(block_rows)}: {block_rows}"

    full_text = " ".join(block_rows)

    # 2. Mentions 'sin sembrar' and ~624 ha
    assert "sin sembrar" in full_text.lower(), f"Block must mention 'sin sembrar': {full_text}"
    assert any(str(h) in full_text for h in (623, 624, 625)), f"Must mention ~624 ha unsown: {full_text}"

    # 3. Mentions soybean rotation
    assert "rotación" in full_text.lower() and "soja" in full_text.lower(), f"Must mention soybean rotation: {full_text}"

    # 4. No cash line says 'vale 1,5...'
    assert "vale 1,5" not in full_text, f"No cash line should say 'vale 1,5...': {full_text}"

    # 5. Fortnight 1 gain matches capital_shadow_price within 0.01
    cap_gain = res.capital_shadow_price
    cash_row = next(r for r in block_rows if "quincena 1" in r or "mayo" in r.lower())
    assert f"{cap_gain:.2f}" in cash_row or f"{round(cap_gain, 2)}" in cash_row or f"{cap_gain:.4f}" in cash_row, \
        f"Gain for fortnight 1 ({cap_gain:.2f}) not found in cash row: {cash_row}"

    # English version check
    xlsx_bytes_en = export_plan_xlsx(sc_dict, lang="en")
    wb_en = openpyxl.load_workbook(io.BytesIO(xlsx_bytes_en))
    ws_sum_en = wb_en["Summary"]
    start_r_en = None
    for r in range(1, ws_sum_en.max_row + 1):
        v = ws_sum_en.cell(row=r, column=1).value
        if v and "SHADOW PRICES" in str(v).upper():
            start_r_en = r
            break
    assert start_r_en is not None
    block_rows_en = []
    for r in range(start_r_en + 1, ws_sum_en.max_row + 1):
        va = ws_sum_en.cell(row=r, column=1).value
        vb = ws_sum_en.cell(row=r, column=2).value
        if va is None and vb is None:
            break
        txt = f"{va or ''} {vb or ''}".strip()
        if txt:
            block_rows_en.append(txt)
    assert len(block_rows_en) <= 6
    full_en = " ".join(block_rows_en)
    assert "unsown" in full_en.lower()
    assert "soybean" in full_en.lower()
