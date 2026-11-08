"""DORA MCP server: engine optimization and verifiable agronomic planning (SPEC-40)."""
from __future__ import annotations

import base64
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
from mcp_server.auth import AuthMiddleware, is_anonymous
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

    if record and is_anonymous():
        err_msg = "recording on-chain needs an API key"
        prov = build_provenance("solve_plan", None, {"error": err_msg}, [], is_error=True)
        return {"error": err_msg, "provenance": prov}

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
            from dora_chain.config import is_chain_configured

            if not is_chain_configured():
                out["record"] = {"status": "not_configured"}
            else:
                failed_checks = [c["name"] for c in checks if c.get("passed") is False]
                if failed_checks:
                    out["record"] = {
                        "status": "not_recorded",
                        "reason": f"checks failed: {', '.join(failed_checks)}",
                    }
                else:
                    sc, _ = tools._validate(scenario)
                    r_extra = optimize(sc)
                    npv_plan = res.get("npv_usd", 0.0)
                    if abs(r_extra.npv - npv_plan) > 1.0:
                        out["record"] = {
                            "status": "not_recorded",
                            "reason": "engine not deterministic",
                        }
                    else:
                        win_map = sc.resolved_sowing_windows()
                        planned_yields = {}
                        planned_prices = {}
                        for c, ha in r_extra.hectares.items():
                            if ha > 0:
                                win_ha = r_extra.hectares_by_window.get(c, {})
                                tot_ha = sum(win_ha.values())
                                y = (
                                    sum(win_ha.get(w["id"], 0.0) * float(w["yield_t_ha"]) for w in win_map.get(c, [])) / tot_ha
                                    if tot_ha > 0
                                    else float(sc.crop_yield(c))
                                )
                                sales_c = r_extra.sales.get(c, {})
                                tot_t = sum(sales_c.values())
                                p_mean = (
                                    sum(tools._crop_price_at_p(sc, c, p) * t for p, t in sales_c.items()) / tot_t
                                    if tot_t > 0
                                    else float(sc.price(c))
                                )
                                planned_yields[c] = round(float(y), 4)
                                planned_prices[c] = round(float(p_mean), 2)

                        planned = {
                            "yield_t_ha": planned_yields,
                            "mean_sale_price_usd_t": planned_prices,
                        }
                        from dora.record import build_plan_record, record_hash
                        from dora_chain.queue import enqueue_record

                        plan_rec = build_plan_record(
                            scenario_validated=sc_val,
                            scenario_sent=scenario,
                            result=res,
                            provenance=prov,
                            planned=planned,
                        )
                        init_status = enqueue_record(plan_rec)
                        out["record"] = {
                            "status": "queued",
                            "record_id": plan_rec["record_id"],
                            "record_hash": record_hash(plan_rec),
                            "record": plan_rec,
                        }
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


@mcp.tool()
def record_status(record_id: str) -> dict:
    """Check publication status of an on-chain plan or outcome attestation by record_id."""
    try:
        from dora_chain.queue import get_record_status

        return get_record_status(record_id)
    except Exception as e:
        err_id = str(uuid.uuid4())
        logger.exception(f"Internal error {err_id} in record_status: {e}")
        return {"error": "internal error", "id": err_id}


@mcp.tool()
def record_outcome(plan_record: dict, actual: dict) -> dict:
    """Record real-world end-of-season outcome and calculate performance errors against the original plan."""
    if is_anonymous():
        err_msg = "recording on-chain needs an API key"
        prov = build_provenance("record_outcome", None, {"error": err_msg}, [], is_error=True)
        return {"error": err_msg, "status": "refused", "provenance": prov}

    try:
        from dora.record import build_outcome_record, record_hash
        from dora_chain.queue import enqueue_record, get_record_status

        rec_id = plan_record.get("record_id")
        local_status = get_record_status(rec_id) if rec_id else None
        h = record_hash(plan_record)

        if local_status and local_status.get("status") != "not_found":
            if local_status.get("record_hash") != h:
                return {"error": "hash does not match", "status": "refused"}

        # Check provenance hashes if present
        prov = plan_record.get("provenance", {})
        if prov.get("scenario_hash") and sha256_canonical(plan_record.get("scenario", {})) != prov["scenario_hash"]:
            return {"error": "hash does not match", "status": "refused"}
        if prov.get("result_hash") and sha256_canonical(plan_record.get("result", {})) != prov["result_hash"]:
            return {"error": "hash does not match", "status": "refused"}

        ref_uid = local_status.get("attestation_uid") if local_status else None
        outcome_rec = build_outcome_record(plan_record, actual)
        init_status = enqueue_record(outcome_rec, ref_uid=ref_uid)
        return {
            "record": outcome_rec,
            "outcome_record": outcome_rec,
            "errors": outcome_rec.get("errors", {}),
            "status": init_status.get("status", "queued"),
            "record_id": outcome_rec.get("record_id"),
            "record_hash": record_hash(outcome_rec),
        }
    except Exception as e:
        err_id = str(uuid.uuid4())
        logger.exception(f"Internal error {err_id} in record_outcome: {e}")
        return {"error": "internal error", "id": err_id}


@mcp.tool()
def verify_record(record: dict) -> dict:
    """Verify record on chain: checks hash matches, attester is DORA, and returns EAS scan link."""
    try:
        from dora_chain.eas import verify_record_attestation

        return verify_record_attestation(record)
    except Exception as e:
        err_id = str(uuid.uuid4())
        logger.exception(f"Internal error {err_id} in verify_record: {e}")
        return {"error": "internal error", "id": err_id}


@mcp.tool()
def export_plan_xlsx(scenario: dict, lang: str = "es", record: dict | None = None) -> dict:
    """Export optimal agronomic and financial plan as an Excel spreadsheet (.xlsx). All monetary values in USD of plan start."""
    sc_val, err = _validate_scenario_dict(scenario)
    if err:
        prov = build_provenance("export_plan_xlsx", None, {"error": err}, [], is_error=True)
        return {"error": err, "provenance": prov}

    try:
        from dora.spreadsheet import export_plan_xlsx as _export_xlsx
        from dora.scenario import Scenario, normalize_region
        raw_bytes = _export_xlsx(scenario, lang=lang, record=record)
        b64_content = base64.b64encode(raw_bytes).decode("ascii")

        sc_obj = Scenario(**sc_val)
        reg_norm = normalize_region(sc_obj.region)
        date_str = getattr(sc_obj, "start_date", None) or getattr(sc_obj, "season_start", None) or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        file_name = f"dora-plan-{reg_norm}-{date_str}.xlsx"

        result = {
            "resource": {
                "blob": b64_content,
                "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "fileName": file_name,
            },
            "file_name": file_name,
            "sheets": (
                ["Resumen", "Plan por cultivo", "Caja por quincena", "Supuestos", "Sensibilidad", "Verificación", "_dora"]
                if lang == "es"
                else ["Summary", "Plan by crop", "Cash by fortnight", "Assumptions", "Sensitivity", "Verification", "_dora"]
            ),
        }
        prov = build_provenance("export_plan_xlsx", sc_val, result, [])
        return {"result": result, "provenance": prov}
    except ValueError as e:
        prov = build_provenance("export_plan_xlsx", sc_val, {"error": str(e)}, [], is_error=True)
        return {"error": str(e), "provenance": prov}
    except Exception as e:
        err_id = str(uuid.uuid4())
        logger.exception(f"Internal error {err_id} in export_plan_xlsx: {e}")
        return {"error": "internal error", "id": err_id}


@mcp.tool()
def import_plan_xlsx(file_base64: str, lang: str = "es") -> dict:
    """Import and validate a modified DORA plan spreadsheet (.xlsx), re-solve and report deltas."""
    if len(file_base64) > 7 * 1024 * 1024:
        err_msg = "El archivo supera el límite de 5 MB." if lang == "es" else "File exceeds 5 MB limit."
        prov = build_provenance("import_plan_xlsx", None, {"error": err_msg}, [], is_error=True)
        return {"error": err_msg, "provenance": prov}

    try:
        raw_bytes = base64.b64decode(file_base64)
    except Exception as e:
        err_msg = f"Invalid base64 encoding: {e}"
        prov = build_provenance("import_plan_xlsx", None, {"error": err_msg}, [], is_error=True)
        return {"error": err_msg, "provenance": prov}

    if len(raw_bytes) > 5 * 1024 * 1024:
        err_msg = "El archivo supera el límite de 5 MB." if lang == "es" else "File exceeds 5 MB limit."
        prov = build_provenance("import_plan_xlsx", None, {"error": err_msg}, [], is_error=True)
        return {"error": err_msg, "provenance": prov}

    try:
        from dora.spreadsheet import read_plan_xlsx
        res = read_plan_xlsx(raw_bytes, lang=lang)
        if "error" in res:
            prov = build_provenance("import_plan_xlsx", None, res, [], is_error=True)
            return {"error": res.get("message", res["error"]), "detail": res, "provenance": prov}

        if res.get("file") and Path(res["file"]).exists():
            out_bytes = Path(res["file"]).read_bytes()
            res["resource"] = {
                "blob": base64.b64encode(out_bytes).decode("ascii"),
                "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "fileName": res.get("file_name", "dora-plan.xlsx"),
            }

        sc_val = res.get("scenario")
        prov = build_provenance("import_plan_xlsx", sc_val, res, [])
        return {"result": res, "provenance": prov}
    except Exception as e:
        err_id = str(uuid.uuid4())
        logger.exception(f"Internal error {err_id} in import_plan_xlsx: {e}")
        return {"error": "internal error", "id": err_id}


@mcp.tool()
def field_ndvi(
    field: dict | list | None = None,
    scenario: dict | None = None,
    crop: str | None = None,
    date: str | None = None,
    same_crop_years: list[int] | None = None,
    replan: bool = False,
    yield_t_ha: float | None = None,
    lang: str = "es",
) -> dict:
    """Measure crop vigour and NDVI from Sentinel-2 satellite imagery over the field, compare with normal, and propose yield adjustment (SPEC-46)."""
    sc_val = None
    if scenario is not None:
        sc_val, err = _validate_scenario_dict(scenario)
        if err:
            prov = build_provenance("field_ndvi", None, {"error": err}, [], is_error=True)
            return {"error": err, "provenance": prov}

    input_args = {
        "field": field,
        "scenario": sc_val,
        "crop": crop,
        "date": date,
        "same_crop_years": same_crop_years,
        "replan": replan,
        "yield_t_ha": yield_t_ha,
        "lang": lang,
    }
    try:
        from dora.tools import field_ndvi as _tool_field_ndvi
        res = _tool_field_ndvi(
            field=field,
            scenario=sc_val,
            crop=crop,
            date=date,
            same_crop_years=same_crop_years,
            replan=replan,
            yield_t_ha=yield_t_ha,
            lang=lang,
        )
        overlay_path = res.get("overlay_path")
        if overlay_path and os.path.isfile(overlay_path):
            with open(overlay_path, "rb") as f_img:
                b64_img = base64.b64encode(f_img.read()).decode("ascii")
            res["resource"] = {
                "blob": b64_img,
                "mimeType": "image/png",
                "fileName": f"ndvi_{res.get('scene_id', 'field')}.png",
            }
        prov = build_provenance("field_ndvi", input_args, res, [])
        return {"result": res, "provenance": prov}
    except Exception as e:
        prov = build_provenance("field_ndvi", input_args, {"error": str(e)}, [], is_error=True)
        return {"error": str(e), "provenance": prov}


async def _background_drain_loop():
    """Background publisher loop for draining attestation queue every 10 seconds."""
    import asyncio
    while True:
        try:
            from dora_chain.queue import drain_queue
            await asyncio.to_thread(drain_queue)
        except Exception as e:
            logger.exception("Error in background publisher drain loop: %s", e)
        await asyncio.sleep(10)


def create_http_app() -> Any:
    """Create Starlette application with transport security disabled (for reverse proxies/testclient) and Bearer auth."""
    import asyncio
    from contextlib import asynccontextmanager

    sec = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    inner = mcp.streamable_http_app(
        stateless_http=True,
        json_response=True,
        transport_security=sec,
    )

    orig_lifespan = inner.router.lifespan_context

    @asynccontextmanager
    async def app_lifespan(app_inst):
        drain_task = None
        if os.environ.get("DORA_DISABLE_BACKGROUND_PUBLISHER") != "1":
            drain_task = asyncio.create_task(_background_drain_loop())
        try:
            if orig_lifespan:
                async with orig_lifespan(app_inst) as maybe_state:
                    yield maybe_state
            else:
                yield
        finally:
            if drain_task:
                drain_task.cancel()
                try:
                    await drain_task
                except (asyncio.CancelledError, Exception):
                    pass

    inner.router.lifespan_context = app_lifespan
    return AuthMiddleware(inner)
