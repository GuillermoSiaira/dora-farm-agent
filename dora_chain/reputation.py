"""Reputation calculation and GraphQL indexing from EAS attestations (SPEC-41 section 6)."""
from __future__ import annotations

import json
import logging
from pathlib import Path
import statistics
from typing import Any

from dora_chain.config import REPO_ROOT

logger = logging.getLogger("dora_chain.reputation")


def calculate_metrics_for_error(values: list[float]) -> dict:
    """Compute count, median of absolute values, and share within +/- 10%."""
    if not values:
        return {"count": 0, "median_abs_error_pct": None, "share_within_10pct": None}
    abs_vals = [abs(v) for v in values]
    med = statistics.median(abs_vals)
    within_10 = sum(1 for v in abs_vals if v <= 10.0) / len(values)
    return {
        "count": len(values),
        "median_abs_error_pct": round(float(med), 2),
        "share_within_10pct": round(float(within_10 * 100.0), 1),
    }


def compute_reputation_summary(plans: list[dict], outcomes: list[dict]) -> dict:
    """Compute public track record and reputation statistics from plan and outcome attestations."""
    plans_count = len(plans)
    outcomes_count = len(outcomes)

    if outcomes_count == 0:
        return {
            "plans_recorded": plans_count,
            "outcomes_recorded": 0,
            "message": "No outcomes recorded yet.",
            "metrics": {},
            "followed_plan": {"yes": 0, "partly": 0, "no": 0, "unknown": 0},
            "outcomes": [],
        }

    yield_errs: list[float] = []
    price_errs: list[float] = []
    margin_errs: list[float] = []
    hectares_matches: list[float] = []
    followed_counts = {"yes": 0, "partly": 0, "no": 0, "unknown": 0}

    outcomes_list = []
    for o in outcomes:
        uid = o.get("id") or o.get("uid") or ""
        ref_uid = o.get("refUID") or o.get("ref_uid") or ""
        errs = o.get("errors", {})
        agg = errs.get("aggregate", {})

        y = agg.get("yield_error_pct")
        if y is None and "yieldErrorBps" in o:
            bps = o["yieldErrorBps"]
            y = bps / 100.0 if bps != -2147483648 else None
        if y is not None:
            yield_errs.append(y)

        p = agg.get("price_error_pct")
        if p is None and "priceErrorBps" in o:
            bps = o["priceErrorBps"]
            p = bps / 100.0 if bps != -2147483648 else None
        if p is not None:
            price_errs.append(p)

        m = agg.get("margin_error_pct")
        if m is None and "marginErrorBps" in o:
            bps = o["marginErrorBps"]
            m = bps / 100.0 if bps != -2147483648 else None
        if m is not None:
            margin_errs.append(m)

        h = agg.get("hectares_match_pct")
        if h is None and "hectaresMatchBps" in o:
            h = o["hectaresMatchBps"] / 100.0
        if h is not None:
            hectares_matches.append(h)

        f_plan = errs.get("followed_plan")
        if not f_plan and "followedPlan" in o:
            from dora_chain.eas import FOLLOWED_PLAN_REV_MAP
            f_plan = FOLLOWED_PLAN_REV_MAP.get(o["followedPlan"], "unknown")
        f_plan = f_plan if f_plan in followed_counts else "unknown"
        followed_counts[f_plan] += 1

        outcomes_list.append({
            "uid": uid,
            "plan_uid": ref_uid,
            "yield_error_pct": y,
            "price_error_pct": p,
            "margin_error_pct": m,
            "hectares_match_pct": h,
            "followed_plan": f_plan,
        })

    # Sort outcomes by absolute error descending (worst first, transparent)
    outcomes_list.sort(
        key=lambda x: max(
            abs(x["yield_error_pct"] or 0),
            abs(x["price_error_pct"] or 0),
            abs(x["margin_error_pct"] or 0),
        ),
        reverse=True,
    )

    summary = {
        "plans_recorded": plans_count,
        "outcomes_recorded": outcomes_count,
        "metrics": {
            "yield_error": calculate_metrics_for_error(yield_errs),
            "price_error": calculate_metrics_for_error(price_errs),
            "margin_error": calculate_metrics_for_error(margin_errs),
            "hectares_match_pct_avg": round(sum(hectares_matches) / len(hectares_matches), 1) if hectares_matches else None,
        },
        "followed_plan": followed_counts,
        "outcomes": outcomes_list,
    }

    # Save to site/reputation.json if site directory exists
    site_dir = REPO_ROOT / "site"
    if site_dir.exists():
        out_file = site_dir / "reputation.json"
        out_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    return summary

