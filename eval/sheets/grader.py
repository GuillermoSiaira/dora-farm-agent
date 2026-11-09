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


def extract_numbers_from_sheet(sheet_dict: dict, formula_numbers: list[float], var_names: list[str] | None = None) -> list[float]:
    """Extract all numeric constants in cells, formulas, and constraints.
    Decision variable cells are excluded from constant checking since their
    values are solved by the LP and do not define problem parameters.
    """
    numbers: list[float] = []
    var_set = set(v.strip().upper() for v in var_names) if var_names else set()

    # Cells constants
    cells = sheet_dict.get("cells", {})
    if isinstance(cells, dict):
        for k, v in cells.items():
            if str(k).strip().upper() in var_set:
                continue
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


def extract_numbers_from_text(text: str) -> list[tuple[float, bool]]:
    """Extract numbers from text as (value, is_percentage).
    Handles decimals (0.4, 1.5), thousands (260.000, 180,000), and percentages (14%).
    """
    results: list[tuple[float, bool]] = []
    pattern = r"\b\d+(?:[.,]\d+)*(?:%|\b)"
    for token in re.findall(pattern, text):
        is_pct = token.endswith("%")
        s = token[:-1] if is_pct else token
        try:
            if "." in s and "," in s:
                if s.find(".") < s.find(","):
                    # 1.234,56
                    clean = s.replace(".", "").replace(",", ".")
                else:
                    # 1,234.56
                    clean = s.replace(",", "")
                val = float(clean)
            elif "." in s:
                parts = s.split(".")
                # If e.g. 260.000 or 1.000.000
                if len(parts) == 2 and len(parts[1]) == 3 and parts[0] != "0":
                    val = float(parts[0] + parts[1])
                elif len(parts) > 2 and all(len(p) == 3 for p in parts[1:]):
                    val = float("".join(parts))
                else:
                    val = float(s)
            elif "," in s:
                parts = s.split(",")
                if len(parts) == 2 and len(parts[1]) == 3 and parts[0] != "0" and len(parts[0]) >= 2:
                    val = float(parts[0] + parts[1])
                elif len(parts) > 2 and all(len(p) == 3 for p in parts[1:]):
                    val = float("".join(parts))
                else:
                    val = float(parts[0] + "." + parts[1])
            else:
                val = float(s)
            results.append((val, is_pct))
        except ValueError:
            pass
    return results


def build_allowed_numbers(problem: dict | None, assumptions: list[str] | None = None) -> set[float]:
    """Build the strict set of allowed numbers for a problem.
    Universal constants: only {0.0, 1.0, -1.0}.
    Problem statement numbers: x and -x.
    Percentage numbers: x, -x, x/100, -x/100.
    Allowed extra: explicit problem-specific domain conversions.
    Declared assumptions: explicit numbers declared in assumptions.
    """
    allowed: set[float] = {0.0, 1.0, -1.0}
    if not problem:
        return allowed

    # 1. Explicit statement numbers (primary source of truth)
    if "statement_numbers" in problem:
        for n in problem.get("statement_numbers", []):
            try:
                val = float(n)
                allowed.add(val)
                allowed.add(-val)
            except (ValueError, TypeError):
                pass
    else:
        # Fallback to extracting from text
        for text_key in ("statement_es", "statement_en"):
            text = problem.get(text_key, "")
            if text:
                for val, is_pct in extract_numbers_from_text(text):
                    allowed.add(val)
                    allowed.add(-val)
                    if is_pct:
                        allowed.add(round(val / 100.0, 8))
                        allowed.add(round(-val / 100.0, 8))

    # Explicit percentage numbers
    for n in problem.get("percentage_numbers", []):
        try:
            val = float(n)
            allowed.add(val)
            allowed.add(-val)
            allowed.add(round(val / 100.0, 8))
            allowed.add(round(-val / 100.0, 8))
        except (ValueError, TypeError):
            pass

    # 2. Explicit allowed extra (domain specific unit conversions, e.g. /12, /1000)
    for n in problem.get("allowed_extra", []):
        try:
            val = float(n)
            allowed.add(val)
            allowed.add(-val)
        except (ValueError, TypeError):
            pass

    # 3. Explicit numbers declared in assumptions (for incomplete problems)
    if assumptions and isinstance(assumptions, list):
        for ass_text in assumptions:
            if isinstance(ass_text, str):
                for val, is_pct in extract_numbers_from_text(ass_text):
                    allowed.add(val)
                    allowed.add(-val)
                    if is_pct:
                        allowed.add(round(val / 100.0, 8))
                        allowed.add(round(-val / 100.0, 8))

    return allowed

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


def build_canonical_dual(
    c: list[float] | np.ndarray,
    A_ub: list[list[float]] | np.ndarray | None,
    b_ub: list[float] | np.ndarray | None,
    A_eq: list[list[float]] | np.ndarray | None = None,
    b_eq: list[float] | np.ndarray | None = None,
    sense: str = "max",
) -> dict[str, Any]:
    """Build the canonical dual linear program from primal data.
    
    Convention (Tow pp. 48-60):
    - Primal max, A_ub x <= b_ub:
      Dual: min b_ub^T y, subject to A_ub^T y >= c, y >= 0.
    - Primal min, A_ub x <= b_ub (or >= b_ub):
      Dual: max b_ub^T y, subject to A_ub^T y <= c, y <= 0 (or y >= 0).
    """
    c_arr = np.array(c, dtype=float)
    sense = sense.strip().lower()

    if sense == "max":
        b_arr = np.array(b_ub, dtype=float) if b_ub is not None else np.array([])
        A_arr = np.array(A_ub, dtype=float) if A_ub is not None else np.zeros((0, len(c_arr)))
        c_dual = b_arr.copy()
        A_dual_ub = -A_arr.T
        b_dual_ub = -c_arr
        bounds_dual = [(0.0, None)] * len(c_dual)
        res_dual = linprog(
            c_dual,
            A_ub=A_dual_ub,
            b_ub=b_dual_ub,
            bounds=bounds_dual,
            method="highs",
        )
        opt_val = float(res_dual.fun) if res_dual.success else None
        y_opt = [float(v) for v in res_dual.x] if res_dual.success else []
        return {
            "sense": "min",
            "c": c_dual.tolist(),
            "A_ub": A_dual_ub.tolist(),
            "b_ub": b_dual_ub.tolist(),
            "bounds": bounds_dual,
            "status": "optimal" if res_dual.success else "infeasible",
            "objective": round(opt_val, 6) if opt_val is not None else None,
            "solution": y_opt,
            "marginals": [round(float(m), 8) for m in res_dual.ineqlin.marginals] if hasattr(res_dual, "ineqlin") and res_dual.ineqlin is not None else [],
        }
    else:
        b_arr = np.array(b_ub, dtype=float) if b_ub is not None else np.array([])
        A_arr = np.array(A_ub, dtype=float) if A_ub is not None else np.zeros((0, len(c_arr)))
        c_dual = -b_arr.copy()
        A_dual_ub = A_arr.T
        b_dual_ub = c_arr.copy()
        bounds_dual = [(None, 0.0)] * len(b_arr)
        res_dual = linprog(
            c_dual,
            A_ub=A_dual_ub,
            b_ub=b_dual_ub,
            bounds=bounds_dual,
            method="highs",
        )
        opt_val = float(-res_dual.fun) if res_dual.success else None
        y_opt = [float(v) for v in res_dual.x] if res_dual.success else []
        return {
            "sense": "max",
            "c": b_arr.tolist(),
            "A_ub": A_dual_ub.tolist(),
            "b_ub": b_dual_ub.tolist(),
            "bounds": bounds_dual,
            "status": "optimal" if res_dual.success else "infeasible",
            "objective": round(opt_val, 6) if opt_val is not None else None,
            "solution": y_opt,
            "marginals": [round(float(m), 8) for m in res_dual.ineqlin.marginals] if hasattr(res_dual, "ineqlin") and res_dual.ineqlin is not None else [],
        }


def check_dual_sheet(
    primal_info: dict[str, Any],
    dual_sheet_dict: dict[str, Any] | None,
    primal_status: str,
    primal_obj: float | None,
) -> dict[str, Any]:
    """Check a dual sheet against the model's extracted primal."""
    if not dual_sheet_dict or not isinstance(dual_sheet_dict, dict):
        return {
            "dual_structure_ok": False,
            "strong_duality_ok": False,
            "dual_ok": False,
            "dual_objective": None,
            "error": "No dual_sheet provided",
        }

    primal_sense = primal_info.get("sense", "max").strip().lower()
    expected_dual_sense = "min" if primal_sense == "max" else "max"

    dual_obj_info = dual_sheet_dict.get("objective", {})
    actual_dual_sense = dual_obj_info.get("sense", "").strip().lower()
    if actual_dual_sense != expected_dual_sense:
        return {
            "dual_structure_ok": False,
            "strong_duality_ok": False,
            "dual_ok": False,
            "dual_objective": None,
            "error": f"Dual sense must be '{expected_dual_sense}', got '{actual_dual_sense}'",
        }

    price_of_row = dual_sheet_dict.get("price_of_row")
    if price_of_row is None or not isinstance(price_of_row, list):
        return {
            "dual_structure_ok": False,
            "strong_duality_ok": False,
            "dual_ok": False,
            "dual_objective": None,
            "error": "price_of_row must be a list of primal row indices",
        }

    dual_res = grade_sheet(dual_sheet_dict)
    if dual_res["status"] != "optimal":
        return {
            "dual_structure_ok": False,
            "strong_duality_ok": False,
            "dual_ok": False,
            "dual_objective": dual_res.get("objective"),
            "error": f"Dual sheet did not solve to optimal: {dual_res.get('error')}",
        }

    dual_cells = dual_sheet_dict.get("cells", {})
    dual_vars = parse_variables_list(dual_sheet_dict.get("variables"))
    if len(dual_vars) != len(price_of_row):
        return {
            "dual_structure_ok": False,
            "strong_duality_ok": False,
            "dual_ok": False,
            "dual_objective": dual_res.get("objective"),
            "error": "Number of dual variables does not match price_of_row length",
        }

    dual_model = SheetModel(dual_cells, variables=dual_vars)
    dual_obj_cell = str(dual_obj_info["cell"]).strip().upper()
    try:
        _, dual_obj_coeffs = extract_affine_coefficients(dual_model, dual_obj_cell, dual_vars)
    except Exception as e:
        return {
            "dual_structure_ok": False,
            "strong_duality_ok": False,
            "dual_ok": False,
            "dual_objective": dual_res.get("objective"),
            "error": f"Could not extract dual objective coefficients: {e}",
        }

    b_primal = primal_info["b_ub"]
    c_primal = primal_info["c"]
    A_primal = primal_info["A_ub"]
    n_primal_vars = len(c_primal)

    structural_rows = []
    for i in range(len(b_primal)):
        coeffs = A_primal[i]
        nz = [j for j, val in enumerate(coeffs) if abs(val) > 1e-9]
        is_nonneg = (len(nz) == 1 and abs(b_primal[i]) <= 1e-6 and coeffs[nz[0]] < 0)
        if not is_nonneg:
            structural_rows.append(i)

    if sorted(price_of_row) != sorted(structural_rows):
        return {
            "dual_structure_ok": False,
            "strong_duality_ok": False,
            "dual_ok": False,
            "dual_objective": dual_res.get("objective"),
            "error": f"price_of_row must cover all primal structural rows exactly once without non-negativity rows. Expected {sorted(structural_rows)}, got {price_of_row}",
        }

    for k, row_idx in enumerate(price_of_row):
        if row_idx < 0 or row_idx >= len(b_primal):
            return {
                "dual_structure_ok": False,
                "strong_duality_ok": False,
                "dual_ok": False,
                "dual_objective": dual_res.get("objective"),
                "error": f"Invalid row index in price_of_row: {row_idx}",
            }
        expected_coeff = b_primal[row_idx]
        actual_coeff = dual_obj_coeffs[k]
        if abs(actual_coeff - expected_coeff) > 1e-4 * (1.0 + abs(expected_coeff)):
            return {
                "dual_structure_ok": False,
                "strong_duality_ok": False,
                "dual_ok": False,
                "dual_objective": dual_res.get("objective"),
                "error": f"Dual objective coefficient for variable {dual_vars[k]} ({actual_coeff}) does not match primal RHS {expected_coeff}",
            }

    # Structural constraints in dual sheet: matching columns of primal A
    dual_constraints = dual_sheet_dict.get("constraints", [])
    extracted_dual_rows = []

    for c_def in dual_constraints:
        if not isinstance(c_def, dict):
            continue
        op = str(c_def.get("op", "")).strip()
        lhs_items = expand_constraint_side(c_def.get("lhs"))
        rhs_items = expand_constraint_side(c_def.get("rhs"))
        if len(lhs_items) == 1 and len(rhs_items) == 1:
            try:
                l0, l_c = extract_item_affine(lhs_items[0], dual_model, dual_vars)
                r0, r_c = extract_item_affine(rhs_items[0], dual_model, dual_vars)
                coeffs = [l_c[k] - r_c[k] for k in range(len(dual_vars))]
                rhs_val = r0 - l0
                nz = [k for k, val in enumerate(coeffs) if abs(val) > 1e-9]
                if len(nz) == 1:
                    k_var = nz[0]
                    v_coeff = coeffs[k_var]
                    if primal_sense == "max":
                        if op == "<=" and v_coeff > 0 and (rhs_val / v_coeff) <= 1e-6:
                            return {
                                "dual_structure_ok": False,
                                "strong_duality_ok": False,
                                "dual_ok": False,
                                "dual_objective": dual_res.get("objective"),
                                "error": f"Dual price {dual_vars[k_var]} has wrong sign bound",
                            }
                        if op == ">=" and v_coeff < 0 and (rhs_val / v_coeff) <= 1e-6:
                            return {
                                "dual_structure_ok": False,
                                "strong_duality_ok": False,
                                "dual_ok": False,
                                "dual_objective": dual_res.get("objective"),
                                "error": f"Dual price {dual_vars[k_var]} has wrong sign bound",
                            }
                    if abs(rhs_val) <= 1e-6:
                        continue
                extracted_dual_rows.append((coeffs, op, rhs_val))
            except Exception:
                pass
        else:
            for lhs_elem, rhs_elem in zip(lhs_items, rhs_items):
                try:
                    l0, l_c = extract_item_affine(lhs_elem, dual_model, dual_vars)
                    r0, r_c = extract_item_affine(rhs_elem, dual_model, dual_vars)
                    coeffs = [l_c[k] - r_c[k] for k in range(len(dual_vars))]
                    rhs_val = r0 - l0
                    nz = [k for k, val in enumerate(coeffs) if abs(val) > 1e-9]
                    if len(nz) == 1 and abs(rhs_val) <= 1e-6:
                        continue
                    if len(nz) >= 1:
                        extracted_dual_rows.append((coeffs, op, rhs_val))
                except Exception:
                    pass

    # Check each primal variable column
    matched_primal_vars = set()
    for j in range(n_primal_vars):
        target_col = [A_primal[row_idx][j] for row_idx in price_of_row]
        target_rhs = c_primal[j]

        found_match = False
        for coeffs, op, rhs_val in extracted_dual_rows:
            if op == ">=" or (op == "<=" and primal_sense == "min"):
                lambdas = []
                for k in range(len(dual_vars)):
                    if abs(target_col[k]) > 1e-7:
                        lambdas.append(coeffs[k] / target_col[k])
                if abs(target_rhs) > 1e-7:
                    lambdas.append(rhs_val / target_rhs)
                if lambdas and all(l > 0 for l in lambdas):
                    lam = sum(lambdas) / len(lambdas)
                    if all(abs(coeffs[k] - lam * target_col[k]) <= 1e-3 * (1.0 + abs(lam * target_col[k])) for k in range(len(dual_vars))) and abs(rhs_val - lam * target_rhs) <= 1e-3 * (1.0 + abs(lam * target_rhs)):
                        found_match = True
                        break
            elif op == "<=" or (op == ">=" and primal_sense == "min"):
                lambdas = []
                for k in range(len(dual_vars)):
                    if abs(target_col[k]) > 1e-7:
                        lambdas.append(-coeffs[k] / target_col[k])
                if abs(target_rhs) > 1e-7:
                    lambdas.append(-rhs_val / target_rhs)
                if lambdas and all(l > 0 for l in lambdas):
                    lam = sum(lambdas) / len(lambdas)
                    if all(abs(-coeffs[k] - lam * target_col[k]) <= 1e-3 * (1.0 + abs(lam * target_col[k])) for k in range(len(dual_vars))) and abs(-rhs_val - lam * target_rhs) <= 1e-3 * (1.0 + abs(lam * target_rhs)):
                        found_match = True
                        break
        if found_match:
            matched_primal_vars.add(j)

    dual_structure_ok = (len(matched_primal_vars) == n_primal_vars)

    strong_duality_ok = False
    if primal_status == "optimal" and primal_obj is not None and dual_res.get("objective") is not None:
        diff_dual = abs(dual_res["objective"] - primal_obj)
        tol_dual = max(1.0, 0.001 * abs(primal_obj))
        strong_duality_ok = (diff_dual <= tol_dual)

    dual_ok = dual_structure_ok and strong_duality_ok

    return {
        "dual_structure_ok": dual_structure_ok,
        "strong_duality_ok": strong_duality_ok,
        "dual_ok": dual_ok,
        "dual_objective": dual_res.get("objective"),
        "error": None if dual_ok else "Dual structure or strong duality check failed",
    }


def generate_sensitivity_report(
    primal_info: dict[str, Any],
    solver_res: Any,
    opt_val: float,
) -> dict[str, Any]:
    """Generate sensitivity report from primal LP and HiGHS solution."""
    c = np.array(primal_info["c"], dtype=float)
    sense = primal_info.get("sense", "max").strip().lower()
    A_ub = np.array(primal_info["A_ub"], dtype=float) if primal_info.get("A_ub") is not None else None
    b_ub = np.array(primal_info["b_ub"], dtype=float) if primal_info.get("b_ub") is not None else None
    var_names = primal_info.get("var_names", [f"x{j+1}" for j in range(len(c))])
    con_names = primal_info.get("con_names", [f"c{i+1}" for i in range(len(b_ub))] if b_ub is not None else [])

    shadow_prices = {}
    if hasattr(solver_res, "ineqlin") and solver_res.ineqlin is not None:
        margs = solver_res.ineqlin.marginals
        for i, val in enumerate(margs):
            name = con_names[i] if i < len(con_names) else f"con_{i}"
            sp = -float(val) if sense == "max" else float(val)
            shadow_prices[name] = round(sp, 6)
            shadow_prices[f"c_{i}"] = round(sp, 6)

    slacks = {}
    if b_ub is not None and hasattr(solver_res, "x"):
        Ax = A_ub @ solver_res.x
        for i in range(len(b_ub)):
            name = con_names[i] if i < len(con_names) else f"con_{i}"
            sl = round(float(b_ub[i] - Ax[i]), 6)
            slacks[name] = sl
            slacks[f"c_{i}"] = sl

    reduced_costs = {}
    cell_vars = primal_info.get("cell_vars", [])
    if hasattr(solver_res, "lower") and solver_res.lower is not None:
        low_margs = solver_res.lower.marginals
        for j, val in enumerate(low_margs):
            name = var_names[j] if j < len(var_names) else f"var_{j}"
            rc = round(float(val), 6)
            reduced_costs[name] = rc
            if cell_vars and j < len(cell_vars):
                reduced_costs[cell_vars[j]] = rc

    rhs_ranges = {}
    c_hi = -c if sense == "max" else c
    if b_ub is not None:
        for i in range(len(b_ub)):
            con_name = con_names[i] if i < len(con_names) else f"con_{i}"
            b0 = float(b_ub[i])
            sp = shadow_prices.get(con_name, 0.0)

            delta_max = max(1000.0, 10.0 * abs(b0) if abs(b0) > 0 else 1000.0)
            low = 0.0
            high = delta_max
            b_test = b_ub.copy()
            b_test[i] = b0 + high
            r_test = linprog(c_hi, A_ub=A_ub, b_ub=b_test, bounds=[(0, None)]*len(c), method="highs")
            z_test = (-r_test.fun if sense == "max" else r_test.fun) if (r_test.success and r_test.fun is not None) else None
            if z_test is not None and abs(z_test - (opt_val + sp * high)) <= 1e-4 * (1.0 + abs(opt_val)):
                upper = float("inf")
            else:
                for _ in range(25):
                    mid = (low + high) / 2.0
                    b_test[i] = b0 + mid
                    r_test = linprog(c_hi, A_ub=A_ub, b_ub=b_test, bounds=[(0, None)]*len(c), method="highs")
                    z_test = (-r_test.fun if sense == "max" else r_test.fun) if (r_test.success and r_test.fun is not None) else None
                    if z_test is not None and abs(z_test - (opt_val + sp * mid)) <= 1e-4 * (1.0 + abs(opt_val)):
                        low = mid
                    else:
                        high = mid
                upper = b0 + low

            low = 0.0
            high = b0 if b0 > 0 else delta_max
            for _ in range(25):
                mid = (low + high) / 2.0
                b_test[i] = b0 - mid
                r_test = linprog(c_hi, A_ub=A_ub, b_ub=b_test, bounds=[(0, None)]*len(c), method="highs")
                z_test = (-r_test.fun if sense == "max" else r_test.fun) if (r_test.success and r_test.fun is not None) else None
                if z_test is not None and abs(z_test - (opt_val - sp * mid)) <= 1e-4 * (1.0 + abs(opt_val)):
                    low = mid
                else:
                    high = mid
            lower = b0 - low

            r_entry = {
                "base": round(b0, 6),
                "lower": round(lower, 6),
                "upper": round(upper, 6) if upper != float("inf") else float("inf"),
                "allowable_decrease": round(b0 - lower, 6),
                "allowable_increase": round(upper - b0, 6) if upper != float("inf") else float("inf"),
            }
            rhs_ranges[con_name] = r_entry
            rhs_ranges[f"c_{i}"] = r_entry

    obj_ranges = {}
    for j in range(len(c)):
        var_name = var_names[j] if j < len(var_names) else f"var_{j}"
        c0 = float(c[j])
        x0 = float(solver_res.x[j])

        delta_max = max(500.0, 5.0 * abs(c0) if abs(c0) > 0 else 500.0)
        low = 0.0
        high = delta_max
        c_test = c_hi.copy()
        sign = -1.0 if sense == "max" else 1.0
        for _ in range(25):
            mid = (low + high) / 2.0
            c_test[j] = c_hi[j] + sign * mid
            r_test = linprog(c_test, A_ub=A_ub, b_ub=b_ub, bounds=[(0, None)]*len(c), method="highs")
            z_test = (-r_test.fun if sense == "max" else r_test.fun) if (r_test.success and r_test.fun is not None) else None
            is_same = r_test.success and r_test.x is not None and (np.max(np.abs(r_test.x - solver_res.x)) <= 1e-4 or (z_test is not None and abs(z_test - (opt_val + mid * x0)) <= 1e-4))
            if is_same:
                low = mid
            else:
                high = mid
        upper = c0 + low

        low = 0.0
        high = delta_max
        for _ in range(25):
            mid = (low + high) / 2.0
            c_test[j] = c_hi[j] - sign * mid
            r_test = linprog(c_test, A_ub=A_ub, b_ub=b_ub, bounds=[(0, None)]*len(c), method="highs")
            z_test = (-r_test.fun if sense == "max" else r_test.fun) if (r_test.success and r_test.fun is not None) else None
            is_same = r_test.success and r_test.x is not None and (np.max(np.abs(r_test.x - solver_res.x)) <= 1e-4 or (z_test is not None and abs(z_test - (opt_val - mid * x0)) <= 1e-4))
            if is_same:
                low = mid
            else:
                high = mid
        lower = c0 - low

        o_entry = {
            "base": round(c0, 6),
            "lower": round(lower, 6),
            "upper": round(upper, 6),
            "allowable_decrease": round(c0 - lower, 6),
            "allowable_increase": round(upper - c0, 6),
        }
        obj_ranges[var_name] = o_entry
        if cell_vars and j < len(cell_vars):
            obj_ranges[cell_vars[j]] = o_entry

    return {
        "shadow_prices": shadow_prices,
        "slacks": slacks,
        "reduced_costs": reduced_costs,
        "rhs_ranges": rhs_ranges,
        "obj_ranges": obj_ranges,
    }


def grade_reading(
    answers: list[dict[str, Any]] | dict[str, Any],
    report: dict[str, Any],
    problem: dict[str, Any],
) -> dict[str, Any]:
    """Grade reading answers against sensitivity report."""
    if isinstance(answers, dict) and "answers" in answers:
        answers = answers["answers"]
    if not isinstance(answers, list):
        return {"reading_ok": False, "results": [], "error": "answers must be a list"}

    asks_reading = problem.get("asks_reading", [])
    ans_by_q = {a.get("q"): a for a in answers if isinstance(a, dict) and "q" in a}

    results = []
    all_ok = True

    for q_def in asks_reading:
        q_idx = q_def["q"]
        kind = q_def["kind"]
        target = q_def["target"]
        exp_unit = q_def.get("expected_unit", "").strip().lower()

        ans = ans_by_q.get(q_idx)
        if not ans:
            results.append({"q": q_idx, "ok": False, "reason": "Missing answer"})
            all_ok = False
            continue

        val = ans.get("value")
        unit = str(ans.get("unit", "")).strip().lower()

        if kind == "shadow_price":
            exp_val = report.get("shadow_prices", {}).get(target)
        elif kind == "indifference_price":
            var_range = report.get("obj_ranges", {}).get(target, {})
            if var_range:
                base = var_range.get("base", 0.0)
                upper = var_range.get("upper", base)
                lower = var_range.get("lower", base)
                if val is not None and abs(val - upper) <= max(0.5, 0.005 * abs(upper)):
                    exp_val = upper
                elif val is not None and abs(val - lower) <= max(0.5, 0.005 * abs(lower)):
                    exp_val = lower
                else:
                    exp_val = upper if abs(upper - base) > 1e-4 else lower
            else:
                rc = report.get("reduced_costs", {}).get(target, 0.0)
                exp_val = rc
        elif kind == "rhs_range":
            r_def = report.get("rhs_ranges", {}).get(target, {})
            exp_val = r_def.get("upper")
        else:
            exp_val = None

        if exp_val is None or val is None:
            results.append({"q": q_idx, "ok": False, "reason": "Target value not found in report"})
            all_ok = False
            continue

        diff = abs(val - exp_val)
        val_ok = (diff <= max(0.5, 0.005 * abs(exp_val)))
        unit_ok = (unit == exp_unit)

        q_ok = val_ok and unit_ok
        if not q_ok:
            all_ok = False
        results.append({
            "q": q_idx,
            "kind": kind,
            "target": target,
            "expected_val": exp_val,
            "given_val": val,
            "val_ok": val_ok,
            "expected_unit": exp_unit,
            "given_unit": unit,
            "unit_ok": unit_ok,
            "ok": q_ok,
        })

    return {
        "reading_ok": all_ok,
        "results": results,
    }


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
    found_nums = extract_numbers_from_sheet(sheet_dict, model.formula_numbers, var_names=var_names)
    allowed_nums = build_allowed_numbers(problem, assumptions=sheet_dict.get("assumptions"))
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

    # Dual sheet check
    dual_result = None
    dual_structure_ok = None
    strong_duality_ok = None
    dual_ok = None

    asks_dual = bool(problem and problem.get("asks_dual"))
    dual_sheet_data = sheet_dict.get("dual_sheet")

    if asks_dual or dual_sheet_data is not None:
        primal_info = {
            "c": obj_coeffs,
            "sense": sense,
            "A_ub": A_ub,
            "b_ub": b_ub,
            "var_names": var_names,
            "raw_constraints": raw_constraints,
        }
        dual_check = check_dual_sheet(primal_info, dual_sheet_data, status, opt_val)
        dual_result = dual_check
        dual_structure_ok = dual_check["dual_structure_ok"]
        strong_duality_ok = dual_check["strong_duality_ok"]
        dual_ok = dual_check["dual_ok"]

    # Sensitivity report and reading check
    sensitivity_report = None
    reading_result = None
    reading_ok = None

    asks_reading = bool(problem and problem.get("asks_reading"))
    answers = sheet_dict.get("answers")

    if status == "optimal" and opt_val is not None and (asks_reading or answers is not None):
        prob_con_names = problem.get("con_names", []) if problem else []
        con_names = []
        for i in range(len(b_ub)):
            if i < len(prob_con_names):
                con_names.append(prob_con_names[i])
            else:
                con_names.append(f"c_{i}")

        prob_vars = problem.get("var_names") if problem else None
        if not prob_vars or len(prob_vars) != len(var_names):
            prob_vars = var_names

        primal_info = {
            "c": obj_coeffs,
            "sense": sense,
            "A_ub": A_ub,
            "b_ub": b_ub,
            "var_names": prob_vars,
            "cell_vars": var_names,
            "con_names": con_names,
        }
        sensitivity_report = generate_sensitivity_report(primal_info, res, opt_val)
        if problem and problem.get("asks_reading") and answers is not None:
            reading_result = grade_reading(answers, sensitivity_report, problem)
            reading_ok = reading_result["reading_ok"]

    is_incomplete = bool(problem and problem.get("incomplete"))
    
    # Final solved criteria (SPEC-50 section 2)
    solved = (not is_incomplete) and (status == "optimal") and objective_ok and (len(invented) == 0)
    if asks_dual:
        solved = solved and bool(dual_ok)

    handled = is_incomplete and asked_or_declared and (len(invented) == 0)

    out = {
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
    if dual_result is not None:
        out["dual_structure_ok"] = dual_structure_ok
        out["strong_duality_ok"] = strong_duality_ok
        out["dual_ok"] = dual_ok
        out["dual_result"] = dual_result
    if sensitivity_report is not None:
        out["sensitivity_report"] = sensitivity_report
    if reading_result is not None:
        out["reading_ok"] = reading_ok
        out["reading_result"] = reading_result

    return out
