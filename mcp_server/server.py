"""DORA MCP server: engine optimization and verifiable agronomic planning (SPEC-40)."""
from __future__ import annotations

import copy
import dataclasses
import json
import logging
import os
from pathlib import Path
from typing import Any
import uuid

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse

from dora.engine import optimize
import dora.plan_check as plan_check
from dora.scenario import REGIONS, ScenarioError
import dora.tools as tools
from dora.version import ENGINE_VERSION, engine_fingerprint
import dora.verifier as verifier
from mcp_server.auth import AuthMiddleware
from mcp_server.provenance import (
    build_provenance,
    canonical,
    get_signing_key,
    hmac_sha256,
    sha256_canonical,
    verify_provenance_signature,
)

logger = logging.getLogger("mcp_server")

REPO_ROOT = Path(__file__).resolve().parents[1]

if os.environ.get("DORA_OFFLINE") == "1":
    try:
        import dora.feeds as _feeds

        _feeds.refresh = lambda *args, **kwargs: {"status": "fresh"}
    except Exception:
        pass

mcp = MCPServer(
    "dora",
    instructions=(
        "DORA is an agricultural economic optimization engine for fortnightly crop planning and farm financial decisions. "
        "Call check_text on any answer you write with DORA's numbers before showing it to a person."
    ),
)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Any) -> JSONResponse:
    """Public health check reporting engine version and deterministic fingerprint."""
    return JSONResponse(
        {
            "ok": True,
            "engine_version": ENGINE_VERSION,
            "engine_fingerprint": engine_fingerprint(),
        }
    )


@mcp.resource("dora://modeling-guide")
def resource_modeling_guide() -> str:
    """Read-only guide on DORA assumptions, LP formulation, and agronomic modeling."""
    guide_path = REPO_ROOT / "dora" / "modeling_guide.md"
    if guide_path.exists():
        return guide_path.read_text(encoding="utf-8")
    return "# DORA Modeling Guide\nNot found on disk."


@mcp.resource("dora://regions")
def resource_regions() -> str:
    """Read-only catalogue of supported agricultural regions, names, and available crops."""
    catalog = [
        {
            "id": rid,
            "name": rdata["name"],
            "crops": list(rdata.get("crops", ())),
            "port": rdata.get("port"),
        }
        for rid, rdata in REGIONS.items()
    ]
    return json.dumps(catalog, indent=2, ensure_ascii=False)


def _deep_merge(base: dict, changes: dict) -> dict:
    """Deep merge changes into base (dicts merge recursively, lists and scalars replace)."""
    merged = copy.deepcopy(base)
    for k, v in changes.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k] = _deep_merge(merged[k], v)
        else:
            merged[k] = copy.deepcopy(v)
    return merged


def _validate_scenario_dict(scenario: dict) -> tuple[dict | None, str | None]:
    """Validate scenario dict through tools._validate and return (scenario_as_validated_dict, error_str)."""
    try:
        sc, _ = tools._validate(scenario)
        return dataclasses.asdict(sc), None
    except (ScenarioError, TypeError) as e:
        return None, str(e)


@mcp.tool()
def build_scenario(scenario: dict, lang: str = "es") -> dict:
    """Validate scenario parameters, fill defaults, and return origins. All monetary values in USD of plan start."""
    sc_val, err = _validate_scenario_dict(scenario)
    if err:
        prov = build_provenance("build_scenario", None, {"error": err}, [], is_error=True)
        return {"error": err, "provenance": prov}

    try:
        res = tools.build_scenario(scenario, lang=lang)
        checks = [
            {
                "name": "validated",
                "passed": "error" not in res,
                "detail": res.get("warnings", []),
            }
        ]
        prov = build_provenance("build_scenario", sc_val, res, checks)
        return {"result": res, "provenance": prov}
    except (ScenarioError, TypeError) as e:
        prov = build_provenance("build_scenario", None, {"error": str(e)}, [], is_error=True)
        return {"error": str(e), "provenance": prov}
    except Exception as e:
        err_id = str(uuid.uuid4())
        logger.exception(f"Internal error {err_id} in build_scenario: {e}")
        return {"error": "internal error", "id": err_id}


@mcp.tool()
def update_scenario(scenario: dict, changes: dict, lang: str = "es") -> dict:
    """Deep-merge changes into an existing scenario and validate. All monetary values in USD of plan start."""
    try:
        merged = _deep_merge(scenario, changes)
    except Exception as e:
        prov = build_provenance("update_scenario", None, {"error": str(e)}, [], is_error=True)
        return {"error": str(e), "provenance": prov}

    sc_val, err = _validate_scenario_dict(merged)
    if err:
        prov = build_provenance("update_scenario", None, {"error": err}, [], is_error=True)
        return {"error": err, "provenance": prov}

    try:
        res = tools.build_scenario(merged, lang=lang)
        checks = [
            {
                "name": "validated",
                "passed": "error" not in res,
                "detail": {
                    "warnings": res.get("warnings", []),
                    "changed_keys": sorted(list(changes.keys())),
                },
            }
        ]
        prov = build_provenance("update_scenario", sc_val, res, checks)
        return {"result": res, "provenance": prov}
    except (ScenarioError, TypeError) as e:
        prov = build_provenance("update_scenario", None, {"error": str(e)}, [], is_error=True)
        return {"error": str(e), "provenance": prov}
    except Exception as e:
        err_id = str(uuid.uuid4())
        logger.exception(f"Internal error {err_id} in update_scenario: {e}")
        return {"error": "internal error", "id": err_id}


@mcp.tool()
def solve_plan(
    scenario: dict,
    lang: str = "es",
    farmer_said: list[str] | None = None,
    record: bool = False,
) -> dict:
    """Solve optimal crop allocation and financial plan for the season. All monetary values in USD of plan start."""
    sc_val, err = _validate_scenario_dict(scenario)
    if err:
        prov = build_provenance("solve_plan", None, {"error": err}, [], is_error=True)
        return {"error": err, "provenance": prov}

    try:
        res = tools.evaluate_season(scenario, lang=lang)
        checks = []

        # 3.3 plan_is_optimal
        ha = res.get("hectares", {})
        eval_res = plan_check.evaluate_plan(scenario, ha)
        npv_opt = eval_res.get("npv_optimal_usd") or 0.0
        gap = eval_res.get("gap_usd")
        feasible = bool(eval_res.get("feasible"))
        if gap is not None:
            tol = max(1.0, 1e-4 * abs(npv_opt))
            opt_passed = feasible and (abs(gap) <= tol)
        else:
            opt_passed = False
        checks.append(
            {
                "name": "plan_is_optimal",
                "passed": opt_passed,
                "detail": {
                    "feasible": feasible,
                    "gap_usd": gap,
                    "violations": eval_res.get("violations", []),
                },
            }
        )

        # 3.4 scenario_inputs
        if farmer_said is not None and len(farmer_said) > 0:
            probs = verifier.check_scenario("evaluate_season", {"scenario": scenario}, farmer_said, [])
            checks.append(
                {
                    "name": "scenario_inputs",
                    "passed": len(probs) == 0,
                    "detail": [
                        {"field": p.parameter, "value": p.value, "message": p.reason}
                        for p in probs
                    ],
                }
            )
        else:
            checks.append(
                {
                    "name": "scenario_inputs",
                    "passed": None,
                    "detail": "farmer_said not given: inputs not checked against what the farmer said",
                }
            )

        prov = build_provenance("solve_plan", sc_val, res, checks)
        out = {"result": res, "provenance": prov}
        if record:
            out["record"] = {"status": "not_configured"}
        return out
    except (ScenarioError, TypeError) as e:
        prov = build_provenance("solve_plan", None, {"error": str(e)}, [], is_error=True)
        return {"error": str(e), "provenance": prov}
    except Exception as e:
        err_id = str(uuid.uuid4())
        logger.exception(f"Internal error {err_id} in solve_plan: {e}")
        return {"error": "internal error", "id": err_id}


@mcp.tool()
def shadow_prices(scenario: dict, lang: str = "es") -> dict:
    """Dual values and marginal returns to capital, land, storage, and rotation constraints. All monetary values in USD of plan start."""
    sc_val, err = _validate_scenario_dict(scenario)
    if err:
        prov = build_provenance("shadow_prices", None, {"error": err}, [], is_error=True)
        return {"error": err, "provenance": prov}

    try:
        res = tools.shadow_prices(scenario, lang=lang)

        # 3.3 plan_is_optimal check
        sc, _ = tools._validate(scenario)
        best = optimize(sc)
        eval_res = plan_check.evaluate_plan(scenario, best.hectares)
        npv_opt = eval_res.get("npv_optimal_usd") or 0.0
        gap = eval_res.get("gap_usd")
        feasible = bool(eval_res.get("feasible"))
        if gap is not None:
            tol = max(1.0, 1e-4 * abs(npv_opt))
            opt_passed = feasible and (abs(gap) <= tol)
        else:
            opt_passed = False

        checks = [
            {
                "name": "plan_is_optimal",
                "passed": opt_passed,
                "detail": {
                    "feasible": feasible,
                    "gap_usd": gap,
                    "violations": eval_res.get("violations", []),
                },
            }
        ]
        prov = build_provenance("shadow_prices", sc_val, res, checks)
        return {"result": res, "provenance": prov}
    except (ScenarioError, TypeError) as e:
        prov = build_provenance("shadow_prices", None, {"error": str(e)}, [], is_error=True)
        return {"error": str(e), "provenance": prov}
    except Exception as e:
        err_id = str(uuid.uuid4())
        logger.exception(f"Internal error {err_id} in shadow_prices: {e}")
        return {"error": "internal error", "id": err_id}


@mcp.tool()
def break_even_prices(
    scenario: dict,
    crops: list[str] | None = None,
    verify: bool = True,
    lang: str = "es",
) -> dict:
    """Entry price for crops not in the optimal plan computed from reduced costs. All monetary values in USD of plan start."""
    sc_val, err = _validate_scenario_dict(scenario)
    if err:
        prov = build_provenance("break_even_prices", None, {"error": err}, [], is_error=True)
        return {"error": err, "provenance": prov}

    try:
        res = tools.break_even_prices(scenario, crops=crops, verify=verify, lang=lang)
        checks = []
        for c in res.get("crops", []):
            crop_name = c.get("crop", "")
            verified_val = c.get("verified")
            checks.append(
                {
                    "name": f"break_even_{crop_name}",
                    "passed": verified_val,
                    "detail": {
                        "crop": crop_name,
                        "verified": verified_val,
                        "reduced_cost_usd_ha": c.get("reduced_cost_usd_ha"),
                    },
                }
            )

        prov = build_provenance("break_even_prices", sc_val, res, checks)
        return {"result": res, "provenance": prov}
    except (ScenarioError, TypeError) as e:
        prov = build_provenance("break_even_prices", None, {"error": str(e)}, [], is_error=True)
        return {"error": str(e), "provenance": prov}
    except Exception as e:
        err_id = str(uuid.uuid4())
        logger.exception(f"Internal error {err_id} in break_even_prices: {e}")
        return {"error": "internal error", "id": err_id}


@mcp.tool()
def compare_rent_out(scenario: dict, lang: str = "es") -> dict:
    """Compare farming the land vs renting it out at regional rates. All monetary values in USD of plan start."""
    sc_val, err = _validate_scenario_dict(scenario)
    if err:
        prov = build_provenance("compare_rent_out", None, {"error": err}, [], is_error=True)
        return {"error": err, "provenance": prov}

    try:
        sc, _ = tools._validate(scenario)
        if sc.owned <= 0:
            full_res = tools.evaluate_season(scenario, lang=lang)
            res = {
                k: full_res[k]
                for k in ("land_tenure", "tenure_comparison", "npv_usd", "hectares", "rent_out_ha")
                if k in full_res
            }
            res["note"] = "Rent comparison applies to owned land."
            prov = build_provenance("compare_rent_out", sc_val, res, [])
            return {"result": res, "provenance": prov}

        sc_with_comp = dict(scenario)
        sc_with_comp["tenure_comparison"] = True
        full_res = tools.evaluate_season(sc_with_comp, lang=lang)
        res = {
            k: full_res[k]
            for k in ("land_tenure", "tenure_comparison", "npv_usd", "hectares", "rent_out_ha")
            if k in full_res
        }

        checks = []
        if "tenure_comparison_error" in full_res:
            checks.append(
                {
                    "name": "tenure_consistent",
                    "passed": False,
                    "detail": full_res["tenure_comparison_error"],
                }
            )
        elif "tenure_comparison" in res:
            tc = res["tenure_comparison"]
            farm_only = tc["farm_only_npv_usd"]
            rent_all = tc["rent_all_npv_usd"]
            if not sc.allow_rent_out:
                expected_best = "farm" if farm_only >= rent_all else "rent_out"
                best_ok = tc["best"] == expected_best
            else:
                best_ok = True

            expected_be = round(
                (farm_only - rent_all) / (sc.owned * (1.0 - sc.transaction_tax_rate))
                + sc.regional_rent_usd_ha,
                2,
            )
            be_ok = abs(tc["break_even_rent_usd_ha"] - expected_be) <= 0.01
            passed = best_ok and be_ok
            checks.append(
                {
                    "name": "tenure_consistent",
                    "passed": passed,
                    "detail": {
                        "best_agrees": best_ok,
                        "break_even_matches": be_ok,
                        "break_even_rent_usd_ha": tc["break_even_rent_usd_ha"],
                        "expected_break_even": expected_be,
                    },
                }
            )

        prov = build_provenance("compare_rent_out", sc_val, res, checks)
        return {"result": res, "provenance": prov}
    except (ScenarioError, TypeError) as e:
        prov = build_provenance("compare_rent_out", None, {"error": str(e)}, [], is_error=True)
        return {"error": str(e), "provenance": prov}
    except Exception as e:
        err_id = str(uuid.uuid4())
        logger.exception(f"Internal error {err_id} in compare_rent_out: {e}")
        return {"error": "internal error", "id": err_id}


@mcp.tool()
def evaluate_plan(scenario: dict, hectares: dict) -> dict:
    """Evaluate feasibility and economic value of fixed crop hectares against the optimal plan. All monetary values in USD of plan start."""
    sc_val, err = _validate_scenario_dict(scenario)
    if err:
        prov = build_provenance("evaluate_plan", None, {"error": err}, [], is_error=True)
        return {"error": err, "provenance": prov}

    try:
        res = plan_check.evaluate_plan(scenario, hectares)
        checks = [
            {
                "name": "feasible",
                "passed": bool(res.get("feasible")),
                "detail": res.get("violations", []),
            }
        ]
        prov = build_provenance("evaluate_plan", sc_val, res, checks)
        return {"result": res, "provenance": prov}
    except (ScenarioError, TypeError) as e:
        prov = build_provenance("evaluate_plan", None, {"error": str(e)}, [], is_error=True)
        return {"error": str(e), "provenance": prov}
    except Exception as e:
        err_id = str(uuid.uuid4())
        logger.exception(f"Internal error {err_id} in evaluate_plan: {e}")
        return {"error": "internal error", "id": err_id}


@mcp.tool()
def sensitivity(
    scenario: dict,
    parameter: str,
    values: list,
    lang: str = "es",
) -> dict:
    """Sweep scenario parameter across given values to evaluate NPV sensitivity. All monetary values in USD of plan start."""
    sc_val, err = _validate_scenario_dict(scenario)
    if err:
        prov = build_provenance("sensitivity", None, {"error": err}, [], is_error=True)
        return {"error": err, "provenance": prov}

    try:
        res = tools.sensitivity(scenario, parameter, values, lang=lang)
        prov = build_provenance("sensitivity", sc_val, res, [])
        return {"result": res, "provenance": prov}
    except (ScenarioError, TypeError) as e:
        prov = build_provenance("sensitivity", None, {"error": str(e)}, [], is_error=True)
        return {"error": str(e), "provenance": prov}
    except Exception as e:
        err_id = str(uuid.uuid4())
        logger.exception(f"Internal error {err_id} in sensitivity: {e}")
        return {"error": "internal error", "id": err_id}


@mcp.tool()
def check_text(
    text: str,
    results: list,
    farmer_said: list[str] | None = None,
) -> dict:
    """Verify whether numbers quoted in text are mathematically supported by DORA engine results and what the farmer said."""
    try:
        kept = []
        rejected_results = []
        signing_key, _ = get_signing_key()

        for idx, item in enumerate(results or []):
            if not isinstance(item, dict):
                rejected_results.append({"index": idx, "reason": "item is not a dictionary"})
                continue
            item_result = item.get("result")
            item_prov = item.get("provenance")
            if item_result is None or not isinstance(item_prov, dict):
                rejected_results.append({"index": idx, "reason": "missing result or provenance"})
                continue

            valid, reason = verify_provenance_signature(item_result, item_prov)
            if not valid:
                rejected_results.append({"index": idx, "reason": reason})
                continue

            kept.append(item_result)

        problems = verifier.verify(text, kept, farmer_said or [])
        unsupported = [{"text": p.text, "context": p.context} for p in problems]
        jargon_list = list(verifier.jargon(text))
        unnamed_list = list(verifier.unnamed_series(text))
        styles = jargon_list + unnamed_list
        lang = verifier.farmer_lang(text)
        corr_msg = verifier.correction_message(problems, styles, lang=lang) or None
        supported = len(unsupported) == 0

        payload = {
            "supported": supported,
            "unsupported": unsupported,
            "rejected_results": rejected_results,
            "jargon": jargon_list,
            "unnamed_series": unnamed_list,
            "correction_message": corr_msg,
        }

        prov = build_provenance("check_text", None, payload, [])
        return {
            "result": payload,
            "supported": supported,
            "unsupported": unsupported,
            "rejected_results": rejected_results,
            "jargon": jargon_list,
            "unnamed_series": unnamed_list,
            "correction_message": corr_msg,
            "provenance": prov,
        }
    except Exception as e:
        err_id = str(uuid.uuid4())
        logger.exception(f"Internal error {err_id} in check_text: {e}")
        return {"error": "internal error", "id": err_id}


def create_http_app() -> Any:
    """Create Starlette application with transport security disabled (for reverse proxies/testclient) and Bearer auth."""
    sec = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    inner = mcp.streamable_http_app(
        stateless_http=True,
        json_response=True,
        transport_security=sec,
    )
    return AuthMiddleware(inner)
