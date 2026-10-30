"""Evaluate a proposed plan in the engine (E1 of docs/plan-de-pruebas.md).

Shared implementation in dora.plan_check (SPEC-25).
"""
from __future__ import annotations

from dora.plan_check import (
    TOLERANCE_HA,
    UNLIMITED_CREDIT,
    _extra_credit_needed,
    _fixed,
    _plan_violations,
    evaluate_plan,
)

__all__ = [
    "TOLERANCE_HA",
    "UNLIMITED_CREDIT",
    "_extra_credit_needed",
    "_fixed",
    "_plan_violations",
    "evaluate_plan",
]
