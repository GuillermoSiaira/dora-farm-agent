"""LP spreadsheet extractor, HiGHS solver, and grader (SPEC-50).

Extracts a linear program from a sheet JSON, verifies linearity at 3 random points,
solves with HiGHS, checks non-negativity bounds, checks for invented numbers,
and grades against expected problem objectives.
"""
from __future__ import annotations

import json
import random
import re
from typing import Any

import numpy as np
from scipy.optimize import linprog

from .evaluator import (
    CycleError,
    FormulaError,
    NonlinearError,
    SheetModel,
    expand_range_flat,
    is_valid_cell_name,
    is_valid_range_name,
)


def extract_sheet_json(text: str) -> dict | None:
    """Extract the first balanced JSON object from raw text.
    
    Handles markdown fences (```json ... ```), surrounding prose,
    and multiple JSON blocks (returning the first that parses).
    Returns None if no valid JSON object is found.
    """
    if not isinstance(text, str):
        return text if isinstance(text, dict) else None

    # First check for code blocks
    code_block_re = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
    for m in code_block_re.finditer(text):
        try:
            val = json.loads(m.group(1))
            if isinstance(val, dict):
                return val
        except json.JSONDecodeError:
            pass

    # Scan for first balanced { ... } block
    i = 0
    n = len(text)
    while i < n:
        if text[i] == '{':
            start = i
            depth = 0
            in_string = False
            escape = False
            j = i
            while j < n:
                ch = text[j]
                if in_string:
                    if escape:
                        escape = False
                    elif ch == '\\':
                        escape = True
                    elif ch == '"':
                        in_string = False
                else:
                    if ch == '"':
                        in_string = True
                    elif ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            candidate = text[start:j + 1]
                            try:
                                parsed = json.loads(candidate)
                                if isinstance(parsed, dict):
                                    return parsed
                            except json.JSONDecodeError:
                                break
                j += 1
        i += 1

    return None


def parse_variables_list(variables_field: Any) -> list[str]:
    """Normalize the 'variables' field to an ordered list of cell names."""
    if not variables_field:
        return []
    if isinstance(variables_field, list):
        res = []
        for v in variables_field:
            if is_valid_range_name(str(v)):
                res.extend(expand_range_flat(str(v)))
            elif is_valid_cell_name(str(v)):
                res.append(str(v).strip().upper())
        return res
    if isinstance(variables_field, str):
        s = variables_field.strip().upper()
        if is_valid_range_name(s):
            return expand_range_flat(s)
        if "," in s:
            return [part.strip() for part in s.split(",") if part.strip()]
        if is_valid_cell_name(s):
            return [s]
    return []


def extract_affine_coefficients(
    sheet_model: SheetModel,
    target_cell: str,
    var_names: list[str],
    seed: int = 42,
) -> tuple[float, list[float]]:
    """Extract affine coefficients a_0, a_1..a_n such that cell = a_0 + sum(a_j * x_j).
    
    Verifies linearity at 3 seeded random points.
    Raises NonlinearError if the cell is not affine in the variables.
    """
    target = target_cell.strip().upper()
    n = len(var_names)

    # 1. Base point: all variables at 0
    env_zero = sheet_model.evaluate({v: 0.0 for v in var_names})
    a0 = env_zero.get(target, 0.0)

    # 2. Unit directions: x_j = 1, x_k = 0
    coeffs = []
    for j, vname in enumerate(var_names):
        env_j = sheet_model.evaluate({v: 1.0 if v == vname else 0.0 for v in var_names})
        vj = env_j.get(target, 0.0)
        coeffs.append(vj - a0)

    # 3. Linearity check at 3 random points
    rng = random.Random(seed)
    for _ in range(3):
        x_rand = {v: rng.uniform(1.0, 10.0) for v in var_names}
        env_rand = sheet_model.evaluate(x_rand)
        v_true = env_rand.get(target, 0.0)
        v_pred = a0 + sum(coeffs[j] * x_rand[vname] for j, vname in enumerate(var_names))
        diff = abs(v_true - v_pred)
        tol = 1e-7 * (1.0 + abs(v_true))
        if diff > tol:
            raise NonlinearError(
                f"Cell {target} is nonlinear in variables: true={v_true}, pred={v_pred}, diff={diff}"
            )

    return a0, coeffs


def extract_item_affine(
    item: Any,
    sheet_model: SheetModel,
    var_names: list[str],
) -> tuple[float, list[float]]:
    """Extract affine representation (c0, [c_1..c_n]) for a scalar number or cell."""
    n = len(var_names)
    if isinstance(item, (int, float)) and not isinstance(item, bool):
        return float(item), [0.0] * n
    if isinstance(item, str):
        item_str = item.strip()
        try:
            val = float(item_str)
            return val, [0.0] * n
        except ValueError:
            pass
        if is_valid_cell_name(item_str):
            # Check if it is a decision variable itself
            item_upper = item_str.upper()
            if item_upper in var_names:
                idx = var_names.index(item_upper)
                c_vec = [0.0] * n
                c_vec[idx] = 1.0
                return 0.0, c_vec
            return extract_affine_coefficients(sheet_model, item_upper, var_names)

    raise FormulaError(f"Cannot evaluate constraint item as scalar or cell: {item}")


def expand_constraint_side(side: Any) -> list[Any]:
    """Expand constraint side (range or scalar) into a list of items."""
    if isinstance(side, list):
        res = []
        for x in side:
            res.extend(expand_constraint_side(x))
        return res
    if isinstance(side, str):
        s = side.strip()
        if is_valid_range_name(s):
            return expand_range_flat(s)
    return [side]


def extract_numbers_from_sheet(sheet_dict: dict, formula_numbers: list[float]) -> list[float]:
    """Extract all numeric constants in cells, formulas, and constraints."""
    numbers: list[float] = []

    # Cells constants
    cells = sheet_dict.get("cells", {})
    if isinstance(cells, dict):
        for v in cells.values():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                numbers.append(float(v))
            elif isinstance(v, str) and not v.strip().startswith("="):
                try:
                    numbers.append(float(v.strip()))
                except ValueError:
                    pass

    # Numbers from formula tokenization
    numbers.extend(formula_numbers)

    # Constraints numbers
    for c in sheet_dict.get("constraints", []):
        if isinstance(c, dict):
            for side in ("lhs", "rhs"):
                val = c.get(side)
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    numbers.append(float(val))
                elif isinstance(val, str) and not is_valid_cell_name(val) and not is_valid_range_name(val):
                    try:
                        numbers.append(float(val.strip()))
                    except ValueError:
                        pass

    return numbers


def build_allowed_numbers(problem: dict | None) -> set[float]:
    """Build the set of allowed numbers for a problem, including trivial conversions."""
    allowed: set[float] = {0.0, 1.0}
    if not problem:
        return allowed

    base_nums = set()
    # From problem statement numbers if available
    for key in ("statement_numbers", "numbers", "allowed_extra"):
        for n in problem.get(key, []):
            try:
                base_nums.add(float(n))
            except (ValueError, TypeError):
                pass

    # Also extract numbers mentioned in statement_es / statement_en text
    for text_key in ("statement_es", "statement_en"):
        text = problem.get(text_key, "")
        if text:
            # Match numbers like 500, 260.000, 180,000, 0.4, 14%
            for token in re.findall(r"\b\d+(?:[\.,]\d+)?%?\b", text):
                is_pct = token.endswith("%")
                clean = token.rstrip("%").replace(".", "").replace(",", ".")
                try:
                    val = float(clean)
                    base_nums.add(val)
                    if is_pct:
                        base_nums.add(val / 100.0)
                except ValueError:
                    pass

    # Trivial forms and conversions
    for x in list(base_nums):
        allowed.add(x)
        allowed.add(-x)
        allowed.add(round(x / 100.0, 8))
        allowed.add(round(x * 100.0, 8))
        allowed.add(round(x * 1000.0, 8))
        allowed.add(round(x / 1000.0, 8))
        if abs(x) > 1e-9:
            allowed.add(round(1.0 / x, 8))

    # Add extra allowed standard values
    allowed.update({0.0, 1.0, 0.5, 0.25, 0.75, 2.0, 10.0, 100.0, 1000.0})
    for n in problem.get("allowed_extra", []):
        try:
            allowed.add(float(n))
        except (ValueError, TypeError):
            pass

    return allowed


def find_invented_numbers(found_numbers: list[float], allowed_numbers: set[float]) -> list[float]:
    """Return list of numbers that are not in the allowed set."""
    invented: list[float] = []
    for num in found_numbers:
        # Check against allowed set with relative/absolute tolerance
        matched = False
        for allowed in allowed_numbers:
            if abs(num - allowed) <= 1e-5 * (1.0 + abs(allowed)):
                matched = True
                break
        if not matched and abs(num) > 1e-6:
            invented.append(num)
    return invented


def grade_sheet(sheet_input: str | dict, problem: dict | None = None) -> dict[str, Any]:
    """Grade a model's spreadsheet JSON against problem requirements.
    
    Returns a result dict containing status, objective, solution,
    objective_ok, missing_nonneg, invented_numbers, solved, etc.
    """
    if isinstance(sheet_input, str):
        sheet_dict = extract_sheet_json(sheet_input)
        if sheet_dict is None:
            return {
                "status": "invalid",
                "error": "No valid JSON object found in response",
                "objective": None,
                "solution": None,
                "objective_ok": False,
                "solution_ok": False,
                "missing_nonneg": False,
                "invented_numbers": [],
                "asked_or_declared": False,
                "solved": False,
                "handled": False,
            }
    elif isinstance(sheet_input, dict):
        sheet_dict = sheet_input
    else:
        return {
            "status": "invalid",
            "error": "Input must be a JSON string or dict",
            "objective": None,
            "solution": None,
            "objective_ok": False,
            "solution_ok": False,
            "missing_nonneg": False,
            "invented_numbers": [],
            "asked_or_declared": False,
            "solved": False,
            "handled": False,
        }

    cells = sheet_dict.get("cells", {})
    if not isinstance(cells, dict):
        return {
            "status": "invalid",
            "error": "'cells' must be a dictionary",
            "objective": None,
            "solution": None,
            "objective_ok": False,
            "solution_ok": False,
            "missing_nonneg": False,
            "invented_numbers": [],
            "asked_or_declared": False,
            "solved": False,
            "handled": False,
        }

    var_names = parse_variables_list(sheet_dict.get("variables"))
    if not var_names:
        return {
            "status": "invalid",
            "error": "No decision variables specified",
            "objective": None,
            "solution": None,
            "objective_ok": False,
            "solution_ok": False,
            "missing_nonneg": False,
            "invented_numbers": [],
            "asked_or_declared": False,
            "solved": False,
            "handled": False,
        }

    n_vars = len(var_names)

    # Build SheetModel (parses formulas, checks for cycles & disallowed functions)
    try:
        model = SheetModel(cells, variables=var_names)
    except CycleError as e:
        return {
            "status": "invalid",
            "error": f"Cycle detected: {e}",
            "objective": None,
            "solution": None,
            "objective_ok": False,
            "solution_ok": False,
            "missing_nonneg": False,
            "invented_numbers": [],
            "asked_or_declared": False,
            "solved": False,
            "handled": False,
        }
    except FormulaError as e:
        return {
            "status": "invalid",
            "error": str(e),
            "objective": None,
            "solution": None,
            "objective_ok": False,
            "solution_ok": False,
            "missing_nonneg": False,
            "invented_numbers": [],
            "asked_or_declared": False,
            "solved": False,
            "handled": False,
        }

    # Objective extraction
    obj_info = sheet_dict.get("objective", {})
    if not isinstance(obj_info, dict) or "cell" not in obj_info:
        return {
            "status": "invalid",
            "error": "Objective cell must be specified in 'objective'",
            "objective": None,
            "solution": None,
            "objective_ok": False,
            "solution_ok": False,
            "missing_nonneg": False,
            "invented_numbers": [],
            "asked_or_declared": False,
            "solved": False,
            "handled": False,
        }

    obj_cell = str(obj_info["cell"]).strip().upper()
    sense = str(obj_info.get("sense", "max")).strip().lower()
    if sense not in ("max", "min"):
        return {
            "status": "invalid",
            "error": f"Invalid objective sense: {sense}",
            "objective": None,
            "solution": None,
            "objective_ok": False,
            "solution_ok": False,
            "missing_nonneg": False,
            "invented_numbers": [],
            "asked_or_declared": False,
            "solved": False,
            "handled": False,
        }

    try:
        c0, obj_coeffs = extract_affine_coefficients(model, obj_cell, var_names)
    except NonlinearError as e:
        return {
            "status": "invalid",
            "error": f"Nonlinear objective: {e}",
            "objective": None,
            "solution": None,
            "objective_ok": False,
            "solution_ok": False,
            "missing_nonneg": False,
            "invented_numbers": [],
            "asked_or_declared": False,
            "solved": False,
            "handled": False,
        }

    # Constraints extraction
    raw_constraints = sheet_dict.get("constraints", [])
    if not isinstance(raw_constraints, list):
        return {
            "status": "invalid",
            "error": "'constraints' must be a list",
            "objective": None,
            "solution": None,
            "objective_ok": False,
            "solution_ok": False,
            "missing_nonneg": False,
            "invented_numbers": [],
            "asked_or_declared": False,
            "solved": False,
            "handled": False,
        }

    A_ub: list[list[float]] = []
    b_ub: list[float] = []
    A_eq: list[list[float]] = []
    b_eq: list[float] = []

    bounded_nonneg_vars: set[str] = set()

    for idx_c, c_def in enumerate(raw_constraints):
        if not isinstance(c_def, dict) or "lhs" not in c_def or "op" not in c_def or "rhs" not in c_def:
            continue
        op = str(c_def["op"]).strip()
        if op not in ("<=", ">=", "="):
            return {
                "status": "invalid",
                "error": f"Constraint {idx_c} has invalid operator: {op}",
                "objective": None,
                "solution": None,
                "objective_ok": False,
                "solution_ok": False,
                "missing_nonneg": False,
                "invented_numbers": [],
                "asked_or_declared": False,
                "solved": False,
                "handled": False,
            }

        lhs_items = expand_constraint_side(c_def["lhs"])
        rhs_items = expand_constraint_side(c_def["rhs"])

        if len(lhs_items) == len(rhs_items):
            pairs = list(zip(lhs_items, rhs_items))
        elif len(lhs_items) > 1 and len(rhs_items) == 1:
            pairs = [(item, rhs_items[0]) for item in lhs_items]
        elif len(lhs_items) == 1 and len(rhs_items) > 1:
            pairs = [(lhs_items[0], item) for item in rhs_items]
        else:
            return {
                "status": "invalid",
                "error": f"Constraint {idx_c} LHS and RHS ranges have incompatible shapes: {len(lhs_items)} vs {len(rhs_items)}",
                "objective": None,
                "solution": None,
                "objective_ok": False,
                "solution_ok": False,
                "missing_nonneg": False,
                "invented_numbers": [],
                "asked_or_declared": False,
                "solved": False,
                "handled": False,
            }

        for lhs_elem, rhs_elem in pairs:
            try:
                l0, l_coeffs = extract_item_affine(lhs_elem, model, var_names)
                r0, r_coeffs = extract_item_affine(rhs_elem, model, var_names)
            except NonlinearError as e:
                return {
                    "status": "invalid",
                    "error": f"Nonlinear constraint: {e}",
                    "objective": None,
                    "solution": None,
                    "objective_ok": False,
                    "solution_ok": False,
                    "missing_nonneg": False,
                    "invented_numbers": [],
                    "asked_or_declared": False,
                    "solved": False,
                    "handled": False,
                }
            except FormulaError as e:
                return {
                    "status": "invalid",
                    "error": str(e),
                    "objective": None,
                    "solution": None,
                    "objective_ok": False,
                    "solution_ok": False,
                    "missing_nonneg": False,
                    "invented_numbers": [],
                    "asked_or_declared": False,
                    "solved": False,
                    "handled": False,
                }

            row_coeffs = [l_coeffs[j] - r_coeffs[j] for j in range(n_vars)]
            row_rhs = r0 - l0

            # Check if this row establishes non-negativity for a single variable
            nz_indices = [j for j, val in enumerate(row_coeffs) if abs(val) > 1e-9]
            if len(nz_indices) == 1:
                j = nz_indices[0]
                val = row_coeffs[j]
                vname = var_names[j]
                if op == ">=" and val > 0 and (row_rhs / val) >= -1e-6:
                    bounded_nonneg_vars.add(vname)
                elif op == "<=" and val < 0 and (row_rhs / val) >= -1e-6:
                    bounded_nonneg_vars.add(vname)
                elif op == "=" and (row_rhs / val) >= -1e-6:
                    bounded_nonneg_vars.add(vname)

            if op == "<=":
                A_ub.append(row_coeffs)
                b_ub.append(row_rhs)
            elif op == ">=":
                A_ub.append([-coef for coef in row_coeffs])
                b_ub.append(-row_rhs)
            elif op == "=":
                A_eq.append(row_coeffs)
                b_eq.append(row_rhs)

    # Check missing non-negativity
    missing_nonneg = not all(v in bounded_nonneg_vars for v in var_names)

    # Bounds for HiGHS: variables are free unless bounded by a non-negativity constraint
    bounds = [(0.0, None) if v in bounded_nonneg_vars else (None, None) for v in var_names]

    # HiGHS minimizes c^T x
    c_highs = [-coef for coef in obj_coeffs] if sense == "max" else [coef for coef in obj_coeffs]

    res = linprog(
        c_highs,
        A_ub=np.array(A_ub) if A_ub else None,
        b_ub=np.array(b_ub) if b_ub else None,
        A_eq=np.array(A_eq) if A_eq else None,
        b_eq=np.array(b_eq) if b_eq else None,
        bounds=bounds,
        method="highs",
    )

    if res.status == 0:
        opt_val = (-res.fun if sense == "max" else res.fun) + c0
        solution = {var_names[j]: round(float(res.x[j]), 6) for j in range(n_vars)}
        status = "optimal"
    elif res.status == 2:
        opt_val = None
        solution = None
        status = "infeasible"
    elif res.status == 3:
        opt_val = None
        solution = None
        status = "unbounded"
    else:
        opt_val = None
        solution = None
        status = "invalid"

    # Invented numbers check
    found_nums = extract_numbers_from_sheet(sheet_dict, model.formula_numbers)
    allowed_nums = build_allowed_numbers(problem)
    invented = find_invented_numbers(found_nums, allowed_nums)

    # Check incomplete problems handling
    assumptions = sheet_dict.get("assumptions", [])
    questions = sheet_dict.get("questions_to_user", [])
    asked_or_declared = bool(
        (isinstance(questions, list) and len(questions) > 0)
        or (isinstance(assumptions, list) and len(assumptions) > 0)
    )

    # Compare with expected problem values if provided
    objective_ok = False
    solution_ok = False
    if problem and status == "optimal" and opt_val is not None:
        expected = problem.get("expected", {})
        exp_obj = expected.get("objective")
        if exp_obj is not None:
            diff = abs(opt_val - exp_obj)
            tol = max(1.0, 0.001 * abs(exp_obj))
            objective_ok = (diff <= tol)

        exp_sol = expected.get("solution")
        if exp_sol and isinstance(exp_sol, dict):
            # Check decision values if mapped
            all_sol_ok = True
            for k, exp_v in exp_sol.items():
                if k in solution:
                    diff_s = abs(solution[k] - exp_v)
                    tol_s = max(0.5, 0.005 * abs(exp_v))
                    if diff_s > tol_s:
                        all_sol_ok = False
                        break
            solution_ok = all_sol_ok
        else:
            solution_ok = objective_ok

    is_incomplete = bool(problem and problem.get("incomplete"))
    solved = (not is_incomplete) and (status == "optimal") and objective_ok and (len(invented) == 0)
    handled = is_incomplete and asked_or_declared and (len(invented) == 0)

    return {
        "status": status,
        "error": res.message if res.status not in (0, 2, 3) else None,
        "objective": round(opt_val, 6) if opt_val is not None else None,
        "solution": solution,
        "objective_ok": objective_ok,
        "solution_ok": solution_ok,
        "missing_nonneg": missing_nonneg,
        "invented_numbers": invented,
        "asked_or_declared": asked_or_declared,
        "solved": solved,
        "handled": handled,
        "lp_stats": {
            "n_vars": n_vars,
            "n_ub": len(A_ub),
            "n_eq": len(A_eq),
        },
    }
