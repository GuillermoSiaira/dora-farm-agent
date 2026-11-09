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
