"""Verifiable agronomic plan and outcome records (SPEC-41 section 2). Pure Python, no web3."""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import secrets
from typing import Any
import uuid

from dora.tools import regional_source_label
from dora.version import ENGINE_VERSION, engine_fingerprint


def _round_sig_floats(obj: Any) -> Any:
    """Recursively round every float to 6 significant digits and format objects for canonical JSON."""
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (float,)):
        if math.isnan(obj) or math.isinf(obj) or obj == 0.0:
            return obj
        return float(f"{obj:.6g}")
    if hasattr(obj, "item") and callable(obj.item):
        return _round_sig_floats(obj.item())
    if isinstance(obj, (int,)):
        return int(obj)
    if isinstance(obj, (str,)):
        return obj.replace("\r\n", "\n")
    if obj is None:
        return None
    if isinstance(obj, Path):
        return obj.as_posix()
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return _round_sig_floats(dataclasses.asdict(obj))
    if isinstance(obj, dict):
        return {str(k): _round_sig_floats(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_round_sig_floats(x) for x in obj]
    if isinstance(obj, set):
        rounded_list = [_round_sig_floats(x) for x in obj]
        return sorted(rounded_list, key=lambda x: canonical(x))
    return obj


def canonical(obj: Any) -> str:
    """Canonical JSON string: floats rounded to 6 significant digits, sorted keys, no whitespace."""
    prepared = _round_sig_floats(obj)
    return json.dumps(prepared, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def record_hash(record: dict) -> str:
    """Compute sha256 hex digest of canonical(record)."""
    return hashlib.sha256(canonical(record).encode("utf-8")).hexdigest()


def build_plan_record(
    scenario_validated: dict,
    scenario_sent: dict,
    result: dict,
    provenance: dict,
    planned: dict | None = None,
    record_id: str | None = None,
    created_at: str | None = None,
    salt: str | None = None,
) -> dict:
    """Construct a plan record dictionary conforming to kind 'dora.plan.v1'."""
    if record_id is None:
        record_id = str(uuid.uuid4())
    if created_at is None:
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if salt is None:
        salt = secrets.token_hex(32)

    region = scenario_validated.get("region", "")
    season_start = str(scenario_validated.get("season_start", "2026-05"))
    try:
        season_year = int(season_start[:4])
    except (ValueError, TypeError):
        season_year = 2026

    defaults_used = sorted(list(set(scenario_validated.keys()) - set(scenario_sent.keys())))

    filtered_result = {
        k: result[k]
        for k in (
            "npv_usd",
            "hectares",
            "rent_out_ha",
            "rent_in_ha",
            "buy_ha",
            "sales_t_by_month",
            "max_credit_usd",
            "tenure_comparison",
        )
        if k in result
    }

    return {
        "kind": "dora.plan.v1",
        "record_id": record_id,
        "created_at": created_at,
        "engine_version": ENGINE_VERSION,
        "engine_fingerprint": engine_fingerprint(),
        "scenario": scenario_validated,
        "assumptions": {
            "defaults_used": defaults_used,
            "price_curve_source": scenario_validated.get("price_curve_source"),
            "regional_data": regional_source_label(region),
            "start_date": scenario_validated.get("start_date") or season_start,
            "season": season_year,
        },
        "result": filtered_result,
        "planned": planned or {},
        "provenance": {
            "scenario_hash": provenance.get("scenario_hash"),
            "result_hash": provenance.get("result_hash"),
            "checks": provenance.get("checks", []),
        },
        "salt": salt,
    }


def build_outcome_record(
    plan_record: dict,
    actual: dict,
    record_id: str | None = None,
    created_at: str | None = None,
    salt: str | None = None,
) -> dict:
    """Construct an outcome record dictionary conforming to kind 'dora.outcome.v1'."""
    if record_id is None:
        record_id = str(uuid.uuid4())
    if created_at is None:
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if salt is None:
        salt = secrets.token_hex(32)

    planned = plan_record.get("planned", {})
    planned_yields = planned.get("yield_t_ha", {})
    planned_prices = planned.get("mean_sale_price_usd_t", {})

    plan_result = plan_record.get("result", {})
    planned_hectares = plan_result.get("hectares", {})

    actual_hectares = actual.get("hectares", {})
    actual_yields = actual.get("yield_t_ha", {})
    actual_prices = actual.get("price_received_usd_t", {})

    # Compute errors per crop
    yield_error_pct: dict[str, float | None] = {}
    price_error_pct: dict[str, float | None] = {}

    for crop in set(list(planned_hectares.keys()) + list(actual_hectares.keys())):
        py = planned_yields.get(crop)
        ay = actual_yields.get(crop)
        if py is not None and ay is not None and py > 0:
            yield_error_pct[crop] = round(float((ay - py) / py * 100.0), 2)
        else:
            yield_error_pct[crop] = None

        pp = planned_prices.get(crop)
        ap = actual_prices.get(crop)
        if pp is not None and ap is not None and pp > 0:
            price_error_pct[crop] = round(float((ap - pp) / pp * 100.0), 2)
        else:
            price_error_pct[crop] = None

    # Hectares match pct
    total_planned_ha = sum(float(h) for h in planned_hectares.values() if h > 0)
    if total_planned_ha > 0:
        matched_ha = sum(
            min(float(actual_hectares.get(c, 0.0)), float(planned_hectares[c]))
            for c in planned_hectares
            if planned_hectares[c] > 0
        )
        hectares_match_pct = round(100.0 * matched_ha / total_planned_ha, 2)
    else:
        hectares_match_pct = 100.0

    # Margin error pct
    margin_error_pct: float | None = None
    if "gross_margin_usd" in actual and actual["gross_margin_usd"] is not None:
        act_margin = float(actual["gross_margin_usd"])
        plan_npv = plan_result.get("npv_usd")
        if plan_npv is not None and abs(plan_npv) > 1e-6:
            margin_error_pct = round((act_margin - plan_npv) / abs(plan_npv) * 100.0, 2)

    followed_raw = actual.get("followed_plan")
    if not followed_raw or followed_raw not in ("yes", "partly", "no"):
        followed_plan = "unknown"
    else:
        followed_plan = followed_raw

    # Compute aggregate weighted errors across crops
    weighted_yield_err = None
    weighted_price_err = None
    if total_planned_ha > 0:
        y_sum, y_w = 0.0, 0.0
        p_sum, p_w = 0.0, 0.0
        for c, h in planned_hectares.items():
            if h <= 0:
                continue
            if yield_error_pct.get(c) is not None:
                y_sum += yield_error_pct[c] * h
                y_w += h
            if price_error_pct.get(c) is not None:
                p_sum += price_error_pct[c] * h
                p_w += h
        if y_w > 0:
            weighted_yield_err = round(y_sum / y_w, 2)
        if p_w > 0:
            weighted_price_err = round(p_sum / p_w, 2)

    errors = {
        "yield_error_pct": weighted_yield_err,
        "price_error_pct": weighted_price_err,
        "margin_error_pct": margin_error_pct,
        "hectares_match_pct": hectares_match_pct,
        "followed_plan": followed_plan,
        "yield_error_by_crop": yield_error_pct,
        "price_error_by_crop": price_error_pct,
        "crop_errors": {
            c: {
                "yield_error_pct": yield_error_pct.get(c),
                "price_error_pct": price_error_pct.get(c),
            }
            for c in set(list(planned_hectares.keys()) + list(actual_hectares.keys()))
        },
        "aggregate": {
            "yield_error_pct": weighted_yield_err,
            "price_error_pct": weighted_price_err,
            "margin_error_pct": margin_error_pct,
            "hectares_match_pct": hectares_match_pct,
        },
    }

    return {
        "kind": "dora.outcome.v1",
        "record_id": record_id,
        "created_at": created_at,
        "engine_version": ENGINE_VERSION,
        "engine_fingerprint": engine_fingerprint(),
        "plan_record_id": plan_record.get("record_id"),
        "plan_record_hash": record_hash(plan_record),
        "actual": actual,
        "errors": errors,
        "salt": salt,
    }
