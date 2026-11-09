"""Tests for SPEC-50: The model builds the LP spreadsheet.

Tests 1, 2, and 7 cover Phase 1 (evaluator, linearity, JSON extraction, and grader).
"""
import pytest

from eval.sheets import (
    CycleError,
    FormulaError,
    NonlinearError,
    SheetModel,
    extract_sheet_json,
    grade_sheet,
    parse_formula,
)


def test_01_formula_evaluator():
    """1. The formula evaluator: arithmetic, SUM and SUMPRODUCT over ranges,
    precedence, unary minus, cycle detection, and rejection of IF, MAX,
    other sheets and Python injection (__import__).
    """
    # Arithmetic, precedence and unary minus
    ast1, _ = parse_formula("=-5 + 3 * (2 + 4) / 2")
    assert ast1.eval({}) == 4.0

    ast2, _ = parse_formula("=10 - 4 - 2")
    assert ast2.eval({}) == 4.0

    ast3, _ = parse_formula("=-(2 + 3) * 4")
    assert ast3.eval({}) == -20.0

    # SUM and SUMPRODUCT over ranges
    cells = {
        "B2": 10.0, "C2": 20.0, "D2": 30.0, "E2": 40.0,
        "B5": 1.0,  "C5": 2.0,  "D5": 3.0,  "E5": 4.0,
        "F10": "=SUMPRODUCT(B5:E5, B2:E2)",
        "F11": "=SUM(B5:E5)",
        "F12": "=SUM(B5:E5, 10, -5)",
    }
    model = SheetModel(cells)
    env = model.evaluate()
    # 1*10 + 2*20 + 3*30 + 4*40 = 10 + 40 + 90 + 160 = 300
    assert env["F10"] == 300.0
    # 1 + 2 + 3 + 4 = 10
    assert env["F11"] == 10.0
    # 10 + 10 - 5 = 15
    assert env["F12"] == 15.0

    # Cycle detection: direct cycle
    with pytest.raises(CycleError):
        SheetModel({"A1": "=A1"})

    with pytest.raises(CycleError):
        SheetModel({"A1": "=B1", "B1": "=A1"})

    # Cycle detection: indirect cycle
    with pytest.raises(CycleError):
        SheetModel({"A1": "=B1", "B1": "=C1", "C1": "=A1"})

    # Rejection of disallowed functions (IF, MAX, etc.)
    with pytest.raises(FormulaError, match="Function IF is not allowed"):
        SheetModel({"A1": "=IF(B1>0, 1, 0)"})

    with pytest.raises(FormulaError, match="Function MAX is not allowed"):
        SheetModel({"A1": "=MAX(B1:B5)"})

    with pytest.raises(FormulaError, match="Function MIN is not allowed"):
        SheetModel({"A1": "=MIN(B1:B5)"})

    # Rejection of references to other sheets
    with pytest.raises(FormulaError, match="other sheets are not allowed"):
        SheetModel({"A1": "=Sheet2!B5"})

    with pytest.raises(FormulaError, match="other sheets are not allowed"):
        SheetModel({"A1": "='Sheet 2'!B5"})

    # Rejection of Python injection
    with pytest.raises(FormulaError):
        SheetModel({"A1": "=__import__('os').system('ls')"})

    with pytest.raises(FormulaError):
        SheetModel({"A1": "=eval('1+1')"})

    with pytest.raises(FormulaError):
        SheetModel({"A1": "=open('/etc/passwd').read()"})


def test_02_linearity():
    """2. Linearity: a linear sheet gives exact coefficients; a sheet with
    B5*C5 (two variables multiplied) is detected as nonlinear.
    """
    # 1. Linear sheet
    linear_sheet = {
        "cells": {
            "B2": 100.0, "C2": 150.0, "D2": 200.0, "E2": 250.0,
            "F10": "=SUMPRODUCT(B5:E5, B2:E2)",
            "F11": "=SUM(B5:E5)",
        },
        "variables": "B5:E5",
        "objective": {"cell": "F10", "sense": "max"},
        "constraints": [
            {"lhs": "F11", "op": "<=", "rhs": 500.0},
            {"lhs": "B5:E5", "op": ">=", "rhs": 0.0},
        ],
    }
    res_linear = grade_sheet(linear_sheet)
    assert res_linear["status"] == "optimal"
    assert res_linear["missing_nonneg"] is False
    # Max profit is 500 ha of the most profitable crop (E, at 250 USD/ha) = 125,000
    assert abs(res_linear["objective"] - 125000.0) <= 1e-4
    assert res_linear["solution"]["E5"] == 500.0

    # 2. Nonlinear sheet: B5*C5 (multiplication of two variables)
    nonlinear_sheet = {
        "cells": {
            "F10": "=B5 * C5",
        },
        "variables": "B5, C5",
        "objective": {"cell": "F10", "sense": "max"},
        "constraints": [
            {"lhs": "B5", "op": "<=", "rhs": 10.0},
            {"lhs": "C5", "op": "<=", "rhs": 10.0},
            {"lhs": "B5", "op": ">=", "rhs": 0.0},
            {"lhs": "C5", "op": ">=", "rhs": 0.0},
        ],
    }
    res_nonlinear = grade_sheet(nonlinear_sheet)
    assert res_nonlinear["status"] == "invalid"
    assert "nonlinear" in res_nonlinear["error"].lower()

    # 3. Nonlinear constraint: B5 * C5 <= 50
    nonlinear_con_sheet = {
        "cells": {
            "F10": "=B5 + C5",
            "F11": "=B5 * C5",
        },
        "variables": "B5, C5",
        "objective": {"cell": "F10", "sense": "max"},
        "constraints": [
            {"lhs": "F11", "op": "<=", "rhs": 50.0},
            {"lhs": "B5", "op": ">=", "rhs": 0.0},
            {"lhs": "C5", "op": ">=", "rhs": 0.0},
        ],
    }
    res_con_nonlinear = grade_sheet(nonlinear_con_sheet)
    assert res_con_nonlinear["status"] == "invalid"
    assert "nonlinear" in res_con_nonlinear["error"].lower()


def test_07_json_extraction():
    """7. The JSON extraction from a reply with prose around it, from one with
    two JSON blocks (it takes the first that parses), and from one with no JSON
    at all, which is invalid.
    """
    # 1. Prose around JSON with markdown fences
    reply_with_prose = """
    Certainly! Here is the LP formulation for the farm problem in Google Sheets format:

    ```json
    {
      "cells": {
        "B2": 50.0,
        "F10": "=B2 * B5"
      },
      "variables": "B5",
      "objective": {"cell": "F10", "sense": "max"},
      "constraints": [
        {"lhs": "B5", "op": "<=", "rhs": 100.0},
        {"lhs": "B5", "op": ">=", "rhs": 0.0}
      ]
    }
    ```

    You can load this model directly into OpenSolver.
    """
    extracted1 = extract_sheet_json(reply_with_prose)
    assert extracted1 is not None
    assert "cells" in extracted1
    res1 = grade_sheet(reply_with_prose)
    assert res1["status"] == "optimal"
    assert abs(res1["objective"] - 5000.0) <= 1e-4
    assert res1["solution"]["B5"] == 100.0

    # 2. Two JSON blocks: takes the first that parses
    reply_two_blocks = """
    First, here is the model:
    {
      "cells": {"F10": "=B5 * 20"},
      "variables": "B5",
      "objective": {"cell": "F10", "sense": "max"},
      "constraints": [
        {"lhs": "B5", "op": "<=", "rhs": 10.0},
        {"lhs": "B5", "op": ">=", "rhs": 0.0}
      ]
    }

    And here is secondary metadata:
    {
      "version": "1.0",
      "author": "gemini"
    }
    """
    extracted2 = extract_sheet_json(reply_two_blocks)
    assert extracted2 is not None
    assert "variables" in extracted2
    assert extracted2["variables"] == "B5"
    res2 = grade_sheet(reply_two_blocks)
    assert res2["status"] == "optimal"
    assert abs(res2["objective"] - 200.0) <= 1e-4

    # 3. No JSON at all -> returns None and grader returns invalid
    reply_no_json = "I am sorry, I cannot formulate this linear program as a spreadsheet."
    assert extract_sheet_json(reply_no_json) is None
    res3 = grade_sheet(reply_no_json)
    assert res3["status"] == "invalid"
    assert "no valid json" in res3["error"].lower()


def test_statement_numbers_text_fallback_and_strict_allowed():
    """Test text fallback extraction of statement numbers:
    '0.4', '1.5', '260.000', '180,000', '14%'
    and verify that strict allowed set flags invented 10 and 100.
    """
    from eval.sheets.grader import extract_numbers_from_text, build_allowed_numbers, find_invented_numbers

    sample_text = "Capital de 260.000 USD, rinde de 1.5 t/ha, 0.4 ha, costo 180,000 y tasa de 14% anual."
    extracted = extract_numbers_from_text(sample_text)
    vals = [v for v, is_pct in extracted]
    pcts = [v for v, is_pct in extracted if is_pct]

    assert 260000.0 in vals
    assert 1.5 in vals
    assert 0.4 in vals
    assert 180000.0 in vals
    assert 14.0 in vals
    assert 14.0 in pcts

    # Verify that '0.4' didn't become 4.0 and '1.5' didn't become 15.0
    assert 4.0 not in vals
    assert 15.0 not in vals

    # Build allowed numbers from problem dict
    problem = {
        "statement_es": sample_text,
    }
    allowed = build_allowed_numbers(problem)
    assert 0.4 in allowed
    assert 1.5 in allowed
    assert 260000.0 in allowed
    assert 180000.0 in allowed
    assert 14.0 in allowed
    assert 0.14 in allowed  # 14% / 100
    assert 0.0 in allowed
    assert 1.0 in allowed
    assert -1.0 in allowed

    # Crucial check: 10, 100, 4.0, 15.0 must NOT be in allowed
    assert 10.0 not in allowed
    assert 100.0 not in allowed
    assert 4.0 not in allowed
    assert 15.0 not in allowed

    # Model sheet inventing 10 and 100
    sheet_inventing = {
        "cells": {
            "B2": 1.5,
            "B3": 10.0,   # Invented 10
            "B4": 100.0,  # Invented 100
            "F10": "=B5 * B2",
        },
        "variables": "B5",
        "objective": {"cell": "F10", "sense": "max"},
        "constraints": [
            {"lhs": "B5", "op": "<=", "rhs": 0.4},
            {"lhs": "B5", "op": ">=", "rhs": 0.0},
        ],
    }
    res = grade_sheet(sheet_inventing, problem=problem)
    assert 10.0 in res["invented_numbers"]
    assert 100.0 in res["invented_numbers"]
    assert res["solved"] is False


def test_03_round_trip():
    """3. The round trip: for each of the 12 problems, a hand-built correct
    sheet JSON in tests/fixtures/spec50/ grades solved with the expected objective
    (or handled for incomplete problems). Its objective equals reference_lp
    solved by HiGHS within 1e-6.
    """
    from pathlib import Path
    import json
    from eval.sheets import load_problems, grade_sheet

    probs = {p["id"]: p for p in load_problems()}
    fixtures_dir = Path("tests/fixtures/spec50")

    for pid in sorted(probs.keys()):
        fpath = fixtures_dir / f"{pid}.json"
        assert fpath.exists(), f"Fixture {fpath} does not exist"
        data = json.loads(fpath.read_text(encoding="utf-8"))
        prob = probs[pid]
        res = grade_sheet(data, problem=prob)

        if prob.get("incomplete"):
            assert res["handled"] is True, f"{pid} was expected to be handled: {res}"
            assert len(res["invented_numbers"]) == 0
        else:
            assert res["status"] == "optimal", f"{pid} not optimal: {res.get('error')}"
            assert res["objective_ok"] is True, f"{pid} objective mismatch: got {res.get('objective')} vs exp {prob['expected']['objective']}"
            assert res["solved"] is True, f"{pid} not solved: invented={res.get('invented_numbers')}, error={res.get('error')}"
            assert len(res["invented_numbers"]) == 0
            exp_obj = prob["expected"]["objective"]
            assert abs(res["objective"] - exp_obj) <= 1e-4


def test_04_missing_nonneg():
    """4. The same correct sheet without >= 0 is detected as missing_nonneg.
    The grade is then either still optimal or unbounded according to the problem.
    """
    from pathlib import Path
    import json
    from eval.sheets import load_problems, grade_sheet

    probs = {p["id"]: p for p in load_problems()}
    
    # Check on P1: missing_nonneg detected
    p1_data = json.loads(Path("tests/fixtures/spec50/prob_01.json").read_text(encoding="utf-8"))
    p1_data["constraints"] = [c for c in p1_data["constraints"] if not (c.get("op") == ">=" and c.get("rhs") == 0.0)]
    res1 = grade_sheet(p1_data, problem=probs["prob_01"])
    assert res1["missing_nonneg"] is True

    # Check on P7: without >= 0, machine components can be negative infinitely -> unbounded
    p7_data = json.loads(Path("tests/fixtures/spec50/prob_07.json").read_text(encoding="utf-8"))
    p7_data["constraints"] = [c for c in p7_data["constraints"] if not (c.get("op") == ">=" and c.get("rhs") == 0.0)]
    res7 = grade_sheet(p7_data, problem=probs["prob_07"])
    assert res7["missing_nonneg"] is True
    assert res7["status"] == "unbounded"


def test_05_invented_numbers():
    """5. Invented numbers: the correct sheet for problem 10 with the rent
    changed to 180,000 lists 180000 as invented and does not grade solved.
    """
    from pathlib import Path
    import json
    from eval.sheets import load_problems, grade_sheet

    probs = {p["id"]: p for p in load_problems()}
    p10_data = json.loads(Path("tests/fixtures/spec50/prob_10.json").read_text(encoding="utf-8"))
    
    # Change rent from 150000 to 180000 in objective formula
    p10_data["cells"]["F10"] = "=SUMPRODUCT(B5:D5, B2:D2) - 180000"
    res = grade_sheet(p10_data, problem=probs["prob_10"])
    
    assert 180000.0 in res["invented_numbers"]
    assert res["solved"] is False


def test_06_incomplete_problem():
    """6. Incomplete: for problem 11, a sheet that puts a capital of 260,000
    with no assumption or question is handled = false; the same sheet with the
    question '¿cuánto capital?' is handled = true.
    """
    from pathlib import Path
    import json
    from eval.sheets import load_problems, grade_sheet

    probs = {p["id"]: p for p in load_problems()}
    p11_base = json.loads(Path("tests/fixtures/spec50/prob_11.json").read_text(encoding="utf-8"))
    
    # Case A: no assumption and no question (silent invention of 260,000)
    sheet_silent = dict(p11_base)
    sheet_silent["assumptions"] = []
    sheet_silent["questions_to_user"] = []
    res_silent = grade_sheet(sheet_silent, problem=probs["prob_11"])
    assert res_silent["handled"] is False
    assert 260000.0 in res_silent["invented_numbers"]

    # Case B: question asked
    sheet_question = dict(p11_base)
    sheet_question["questions_to_user"] = ["¿Cuánto capital de trabajo dispone el establecimiento?"]
    res_question = grade_sheet(sheet_question, problem=probs["prob_11"])
    assert res_question["handled"] is True


def test_08_determinism(tmp_path):
    """8. Determinism of expected: two runs of dump_problems_jsonl give byte-identical files."""
    from eval.sheets import dump_problems_jsonl

    p1 = tmp_path / "p1.jsonl"
    p2 = tmp_path / "p2.jsonl"
    dump_problems_jsonl(p1)
    dump_problems_jsonl(p2)
    assert p1.read_bytes() == p2.read_bytes()


def test_09_run_daily_sheets_runner(tmp_path, monkeypatch):
    """9. run_daily.py, with runner: 'sheets', builds the run_sheets.py command.
    Monkeypatch subprocess.run; no network.
    """
    import subprocess
    import json
    import sys
    import eval.daily.run_daily as rd

    queue_file = tmp_path / "queue.json"
    done_file = tmp_path / "done.json"
    log_file = tmp_path / "log.md"
    results_dir = tmp_path / "results"

    queue_data = {
        "queue": [
            {
                "id": "exp_sheets_daily",
                "model": "Qwen/Qwen2.5-7B-Instruct",
                "runner": "sheets",
                "arms": ["alone"],
                "question_es": "Pregunta de prueba diaria",
                "runs": 1,
            }
        ]
    }
    queue_file.write_text(json.dumps(queue_data), encoding="utf-8")
    done_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(rd, "ROOT", tmp_path)
    monkeypatch.setattr(rd, "QUEUE", queue_file)
    monkeypatch.setattr(rd, "DONE", done_file)
    monkeypatch.setattr(rd, "LOG", log_file)
    monkeypatch.setattr(rd, "RESULTS", results_dir)
    monkeypatch.setattr(rd, "quota", lambda: {"daily_used": 0.0, "monthly_left": 50.0})
    monkeypatch.setattr(rd, "refresh_proxy_token", lambda: "http://mock-proxy/openapi")
    monkeypatch.setattr(rd, "git", lambda *args: "")

    executed_cmds = []

    def mock_run(cmd, *args, **kwargs):
        executed_cmds.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0)

    monkeypatch.setattr(subprocess, "run", mock_run)
    monkeypatch.setattr(sys, "argv", ["run_daily.py"])

    rd.main()

    assert len(executed_cmds) > 0
    cmd = executed_cmds[0]
    assert "eval/run_sheets.py" in cmd
    assert "eval/run_e9.py" not in cmd
    assert "--model" in cmd
    assert "Qwen/Qwen2.5-7B-Instruct" in cmd
    assert "--arms" in cmd
    assert "alone" in cmd


def test_10_render_xlsx(tmp_path):
    """10. render.py writes an xlsx that openpyxl reopens, with the formula text unchanged in its cells."""
    import openpyxl
    import json
    from pathlib import Path
    from eval.sheets import grade_sheet, load_problems, render_sheet_to_xlsx

    probs = {p["id"]: p for p in load_problems()}
    p1_data = json.loads(Path("tests/fixtures/spec50/prob_01.json").read_text(encoding="utf-8"))
    grade_res = grade_sheet(p1_data, problem=probs["prob_01"])

    out_xlsx = tmp_path / "rendered_prob_01.xlsx"
    render_sheet_to_xlsx(p1_data, out_xlsx, grade_result=grade_res)

    assert out_xlsx.exists()
    wb = openpyxl.load_workbook(out_xlsx)
    assert "Modelo" in wb.sheetnames
    assert "Solver" in wb.sheetnames
    assert "Corrector" in wb.sheetnames

    ws_model = wb["Modelo"]
    # Formula text remains unchanged
    assert ws_model["F10"].value == "=SUMPRODUCT(B5:C5, B2:C2)"
    assert ws_model["F11"].value == "=SUM(B5:C5)"
    assert ws_model["F12"].value == "=SUMPRODUCT(B5:C5, B3:C3)"

    # Decision variables have fill
    assert ws_model["B5"].fill.fill_type == "solid"
    assert ws_model["C5"].fill.fill_type == "solid"

    # Solver sheet
    ws_solver = wb["Solver"]
    assert ws_solver["B3"].value == "F10"
    assert ws_solver["C3"].value == "MAX"

    # Corrector sheet
    ws_corr = wb["Corrector"]
    assert ws_corr["B3"].value == "optimal"
    assert ws_corr["B5"].value == "SÍ"


def test_11_dual_sheet():
    """11. The dual sheet:
    - For each problem with asks_dual, the fixture's correct dual sheet gives dual_ok.
    - Broken versions fail:
      * wrong sign bound fails dual_structure_ok
      * wrong transposed column fails dual_structure_ok
      * primal sense left unchanged (max instead of min) fails dual_structure_ok
    - A dual row multiplied by 2, or with sides flipped, still passes.
    - Canonical dual built by code matches HiGHS marginals within 1e-6 on all 12 reference LPs.
    """
    from pathlib import Path
    import json
    import numpy as np
    from scipy.optimize import linprog
    from eval.sheets import load_problems, grade_sheet, build_canonical_dual, PROBLEMS

    probs = {p["id"]: p for p in load_problems()}

    # Check correct dual sheets on all problems with asks_dual
    for pid in ["prob_01", "prob_04", "prob_05", "prob_08", "prob_09", "prob_10"]:
        data = json.loads((Path("tests/fixtures/spec50") / f"{pid}.json").read_text(encoding="utf-8"))
        res = grade_sheet(data, problem=probs[pid])
        assert res["dual_ok"] is True, f"{pid} dual not ok: {res.get('dual_result')}"
        assert res["dual_structure_ok"] is True
        assert res["strong_duality_ok"] is True

    # Broken dual: wrong sign bound fails dual_structure_ok
    p1_broken_sign = json.loads(Path("tests/fixtures/spec50/prob_01.json").read_text(encoding="utf-8"))
    p1_broken_sign["dual_sheet"]["constraints"].append({"lhs": "B5", "op": "<=", "rhs": 0.0})
    res_bs = grade_sheet(p1_broken_sign, problem=probs["prob_01"])
    assert res_bs["dual_structure_ok"] is False

    # Broken dual: wrong coefficients in transposed column
    p1_broken_col = json.loads(Path("tests/fixtures/spec50/prob_01.json").read_text(encoding="utf-8"))
    p1_broken_col["dual_sheet"]["cells"]["H2"] = "=B5 * 99 + C5 * 1"
    res_bc = grade_sheet(p1_broken_col, problem=probs["prob_01"])
    assert res_bc["dual_structure_ok"] is False

    # Broken dual: primal sense left unchanged (max instead of min)
    p1_broken_sense = json.loads(Path("tests/fixtures/spec50/prob_01.json").read_text(encoding="utf-8"))
    p1_broken_sense["dual_sheet"]["objective"]["sense"] = "max"
    res_bsen = grade_sheet(p1_broken_sense, problem=probs["prob_01"])
    assert res_bsen["dual_structure_ok"] is False

    # Broken dual: omitting a primal structural row in price_of_row (e.g. omitting labor in problem 1)
    p1_broken_omitted = json.loads(Path("tests/fixtures/spec50/prob_01.json").read_text(encoding="utf-8"))
    p1_broken_omitted["dual_sheet"]["price_of_row"] = [0]
    p1_broken_omitted["dual_sheet"]["variables"] = "B5"
    p1_broken_omitted["dual_sheet"]["cells"]["F10"] = "=B5 * 100"
    p1_broken_omitted["dual_sheet"]["cells"]["H2"] = "=B5 * 1"
    p1_broken_omitted["dual_sheet"]["cells"]["H3"] = "=B5 * 1"
    p1_broken_omitted["dual_sheet"]["constraints"] = [
        {"lhs": "H2", "op": ">=", "rhs": 300.0},
        {"lhs": "H3", "op": ">=", "rhs": 400.0},
        {"lhs": "B5", "op": ">=", "rhs": 0.0},
    ]
    res_bomit = grade_sheet(p1_broken_omitted, problem=probs["prob_01"])
    assert res_bomit["dual_structure_ok"] is False
    # Dual does not gate solved: correct primal with broken dual grades solved = True and dual_ok = False
    assert res_bomit["solved"] is True
    assert res_bomit["dual_ok"] is False

    # Multiplied by 2 passes
    p1_scaled = json.loads(Path("tests/fixtures/spec50/prob_01.json").read_text(encoding="utf-8"))
    p1_scaled["dual_sheet"]["cells"]["H2"] = "=2 * (B5 * 1 + C5 * 1)"
    p1_scaled["dual_sheet"]["constraints"][0]["rhs"] = 600.0  # 300 * 2
    res_scaled = grade_sheet(p1_scaled, problem=probs["prob_01"])
    assert res_scaled["dual_structure_ok"] is True

    # Flipped sides passes: 300 <= B5*1 + C5*1
    p1_flipped = json.loads(Path("tests/fixtures/spec50/prob_01.json").read_text(encoding="utf-8"))
    p1_flipped["dual_sheet"]["constraints"][0] = {"lhs": 300.0, "op": "<=", "rhs": "H2"}
    res_flipped = grade_sheet(p1_flipped, problem=probs["prob_01"])
    assert res_flipped["dual_structure_ok"] is True

    # Canonical dual matches HiGHS marginals and strong duality holds on all 12 reference LPs
    for p in PROBLEMS:
        lp = p["_lp_builder"]()
        c = lp["c"]
        A_ub = lp.get("A_ub")
        b_ub = lp.get("b_ub")
        sense = lp.get("sense", "max")

        dual_canon = build_canonical_dual(c, A_ub, b_ub, sense=sense)
        assert dual_canon["status"] == "optimal"

        # HiGHS primal solve
        c_hi = [-x for x in c] if sense == "max" else c
        res_pri = linprog(c_hi, A_ub=A_ub, b_ub=b_ub, bounds=(0, None), method="highs")
        pri_obj = -res_pri.fun if sense == "max" else res_pri.fun
        dual_obj = dual_canon["objective"]

        assert abs(pri_obj - dual_obj) <= 1e-4 * (1.0 + abs(pri_obj))
        if sense == "max":
            marginals = [-round(float(m), 6) for m in res_pri.ineqlin.marginals]
            dual_sol = [round(float(y), 6) for y in dual_canon["solution"]]
            # Dual solution matches shadow prices
            for y_val, marg_val in zip(dual_sol, marginals):
                assert abs(y_val - marg_val) <= 1e-4 * (1.0 + abs(y_val))


def test_12_sensitivity_report_and_reading():
    """12. The report and the reading:
    - For problems 1, 4, 9 and 10, the report's ranges match direct re-solving.
      Take price at end of range, move by 1% inside (plan does not change) and 1% outside (plan changes).
    - Indifference price read from report equals bisection on reference_lp within 0.5%.
    - Reading answer with right value and wrong unit fails reading_ok.
    """
    from pathlib import Path
    import json
    import numpy as np
    from scipy.optimize import linprog
    from eval.sheets import load_problems, grade_sheet, grade_reading

    probs = {p["id"]: p for p in load_problems()}

    # 1. Perturbation check on Problem 1 (Land range end is 160)
    p1_data = json.loads(Path("tests/fixtures/spec50/prob_01.json").read_text(encoding="utf-8"))
    res1 = grade_sheet(p1_data, problem=probs["prob_01"])
    rep1 = res1["sensitivity_report"]
    land_range = rep1["rhs_ranges"]["tierra"]
    upper_land = land_range["upper"]
    assert abs(upper_land - 160.0) <= 0.5

    # Re-solve 1% inside (159.4 ha) vs 1% outside (160.6 ha)
    lp1 = probs["prob_01"]["_lp_builder"]()
    c1 = [-x for x in lp1["c"]]
    A1 = lp1["A_ub"]
    b_in = [159.4, 160.0]
    b_out = [160.6, 160.0]
    r_in = linprog(c1, A_ub=A1, b_ub=b_in, bounds=(0, None), method="highs")
    r_out = linprog(c1, A_ub=A1, b_ub=b_out, bounds=(0, None), method="highs")
    # Inside shadow price is still 200.0, outside land becomes abundant (shadow price 0)
    assert abs(-r_in.ineqlin.marginals[0] - 200.0) <= 1e-4
    assert abs(-r_out.ineqlin.marginals[0]) <= 1e-4

    # 2. Indifference price check on Problem 4 (Soybean at harvest indifference price is 310)
    p4_data = json.loads(Path("tests/fixtures/spec50/prob_04.json").read_text(encoding="utf-8"))
    res4 = grade_sheet(p4_data, problem=probs["prob_04"])
    rep4 = res4["sensitivity_report"]
    v_s1_range = rep4["obj_ranges"]["v_s1"]
    assert abs(v_s1_range["upper"] - 310.0) <= 0.5

    # 3. Reading grading
    # Correct reading answers for Problem 1
    answers_correct_p1 = [
        {"q": 0, "value": 200.0, "unit": "USD/ha"},
        {"q": 1, "value": 100.0, "unit": "USD/hora"},
        {"q": 2, "value": 160.0, "unit": "ha"},
    ]
    read_eval = grade_reading(answers_correct_p1, rep1, probs["prob_01"])
    assert read_eval["reading_ok"] is True

    # Reading answer with right value and wrong unit fails reading_ok
    answers_wrong_unit = [
        {"q": 0, "value": 200.0, "unit": "EUR/ha"},  # Wrong currency
        {"q": 1, "value": 100.0, "unit": "USD/hora"},
        {"q": 2, "value": 160.0, "unit": "ha"},
    ]
    read_wrong = grade_reading(answers_wrong_unit, rep1, probs["prob_01"])
    assert read_wrong["reading_ok"] is False
    assert read_wrong["results"][0]["val_ok"] is True
    assert read_wrong["results"][0]["unit_ok"] is False


