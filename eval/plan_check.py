"""Evaluate a proposed plan in the engine (E1 of docs/plan-de-pruebas.md).

A plan is hectares per crop. The engine solves the season with those hectares
fixed (min_area/max_area, give or take half a hectare) and decides the rest:
when to sell, what to store, how much credit to use. So the gap it reports
counts only the error in the hectares; it is a floor of the true gap, and
favors the plan being checked.

Nothing here changes the model: it only calls optimize on the given scenario.
"""
from __future__ import annotations

from dataclasses import replace

from dora.engine import optimize
from dora.scenario import ScenarioError
from dora.tools import _validate

TOLERANCE_HA = 0.5           # plans are read to the hectare: the fixed areas may move this much either way
UNLIMITED_CREDIT = 1e9


def _plan_violations(sc, hectares: dict[str, float]) -> list[str]:
    """Rules a plan breaks before solving: land, rotation and the farmer's area constraints."""
    out = []
    for c, h in hectares.items():
        if c not in sc.crops:
            out.append(f"crop {c} is not available here (options: {', '.join(sc.crops)})")
        if h < 0:
            out.append(f"negative area for {c}")
    if out:
        return out
    max_land = sc.owned + sc.rent_in_cap + sc.max_buy_ha
    total = sum(hectares.values())
    if total > max_land + TOLERANCE_HA:
        out.append(f"land: {total:.1f} ha sown, {max_land:.1f} ha available")
    for c, h in hectares.items():
        if h > sc.max_crop_share * max_land + TOLERANCE_HA:
            out.append(f"rotation: {h:.1f} ha of {c}, at most {sc.max_crop_share:.0%} of {max_land:.1f} ha")
    for k in sc.constraints:
        h = hectares.get(k.get("crop"), 0.0)
        if k["type"] == "min_area" and h < k["ha"] - TOLERANCE_HA:
            out.append(f"farmer's min_area of {k['crop']}: {h:.1f} ha < {k['ha']} ha")
        elif k["type"] == "max_area" and h > k["ha"] + TOLERANCE_HA:
            out.append(f"farmer's max_area of {k['crop']}: {h:.1f} ha > {k['ha']} ha")
        elif k["type"] == "min_share" and h < k["share"] * total - TOLERANCE_HA:
            out.append(f"farmer's min_share of {k['crop']}: {h:.1f} ha < {k['share']:.0%} of {total:.1f} ha")
    sold: dict[str, float] = {}
    for k in sc.constraints:
        if k["type"] == "forward_sale":
            sold[k["crop"]] = sold.get(k["crop"], 0.0) + float(k["tonnes"])
    for c, t in sold.items():
        harvest = sc.crop_yield(c) * hectares.get(c, 0.0)
        if harvest < t - 1e-6:
            out.append(f"forward sales of {c}: {t:.0f} t sold, {harvest:.0f} t harvested")
    return out


def _fixed(sc, hectares: dict[str, float]):
    """The scenario with every crop's area fixed to the plan; the farmer's other constraints stay."""
    kept = [k for k in sc.constraints if k["type"] not in ("min_area", "max_area", "min_share")]
    for c in sc.crops:
        h = float(hectares.get(c, 0.0))
        kept.append({"type": "max_area", "crop": c, "ha": round(h + TOLERANCE_HA, 2)})
        if h > TOLERANCE_HA:
            kept.append({"type": "min_area", "crop": c, "ha": round(h - TOLERANCE_HA, 2)})
    return replace(sc, constraints=kept)


def _extra_credit_needed(sc_fixed) -> float:
    """Smallest addition to the credit line that makes the fixed plan solvable (bisection, to 1 USD)."""
    line = sc_fixed.credit_line_usd
    lo, hi = 0.0, UNLIMITED_CREDIT
    while hi - lo > 1.0:
        mid = (lo + hi) / 2
        try:
            optimize(replace(sc_fixed, credit_line_usd=line + mid))
            hi = mid
        except ScenarioError:
            lo = mid
    return hi


def evaluate_plan(scenario: dict, hectares: dict[str, float]) -> dict:
    """Is the plan feasible, what is it worth, and how far is it from the optimum."""
    sc, _ = _validate(scenario)
    best = optimize(sc)
    hectares = {c: float(h) for c, h in (hectares or {}).items() if h is not None}
    out = {
        "hectares_plan": {c: round(h, 1) for c, h in hectares.items() if h > 0},
        "hectares_optimal": {c: round(float(h), 1) for c, h in best.hectares.items() if h > 1e-6},
        "npv_optimal_usd": round(best.npv, 2),
        "feasible": False,
        "violations": [],
        "extra_credit_needed_usd": None,
        "npv_plan_usd": None,
        "gap_usd": None,
        "gap_pct": None,
    }
    violations = _plan_violations(sc, hectares)
    if violations:
        out["violations"] = violations
        return out

    sc_fixed = _fixed(sc, hectares)
    try:
        plan = optimize(sc_fixed)
    except ScenarioError as e:
        try:
            optimize(replace(sc_fixed, credit_line_usd=UNLIMITED_CREDIT))
        except ScenarioError:
            out["violations"] = [f"engine: {e}"]
            return out
        out["extra_credit_needed_usd"] = round(_extra_credit_needed(sc_fixed), 0)
        out["violations"] = [f"cash: capital and credit fall short by {out['extra_credit_needed_usd']:.0f} USD"]
        return out

    gap = best.npv - plan.npv
    out.update({
        "feasible": True,
        "npv_plan_usd": round(plan.npv, 2),
        "gap_usd": round(gap, 2),
        "gap_pct": round(100.0 * gap / abs(best.npv), 2) if abs(best.npv) > 1e-6 else None,
    })
    return out
