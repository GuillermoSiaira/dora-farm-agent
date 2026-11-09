"""Spreadsheet LP evaluation and grading package (SPEC-50)."""
from .evaluator import (
    CycleError,
    FormulaError,
    NonlinearError,
    SheetModel,
    expand_range_flat,
    parse_formula,
)
from .grader import (
    build_canonical_dual,
    check_dual_sheet,
    extract_sheet_json,
    generate_sensitivity_report,
    grade_reading,
    grade_sheet,
)
from .problems import PROBLEMS, dump_problems_jsonl, load_problems

__all__ = [
    "grade_sheet",
    "extract_sheet_json",
    "build_canonical_dual",
    "check_dual_sheet",
    "generate_sensitivity_report",
    "grade_reading",
    "PROBLEMS",
    "dump_problems_jsonl",
    "load_problems",
    "SheetModel",
    "FormulaError",
    "CycleError",
    "NonlinearError",
    "parse_formula",
    "expand_range_flat",
]
