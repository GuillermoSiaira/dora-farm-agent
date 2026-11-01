"""The farmer interview — one question at a time, the one that changes the decision most.

SPEC-29 implementation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from dora.engine import optimize
from dora.plan_check import evaluate_plan
from dora.scenario import REGIONS, Scenario, ScenarioError, load_land_data, load_taxes_data
from dora.tools import (
    PARAMETERS,
    _prepare_region_scenario,
    _validate,
    compare_regions,
    evaluate_season,
    shadow_prices,
)

STOP_SHARE = 0.01       # stops when max regret < 1% of current NPV
MAX_QUESTIONS = 5      # stops after 5 asked questions

# Design constants for tested alternatives
ALTERNATIVES = {
    "tenure": "flip_rented_land",
    "rent_out": [{"allow_rent_out": False}],
    "own_capital": "half_and_double",
    "credit_line": "zero_and_double",
    "supplier_terms": [{"input_payment_delay_fortnights": 6}],
    "storage": "zero_and_double",
}


def _get_limit(sc_dict: dict, lang: str = "es") -> dict | None:
    """Identify what limits the farmer: first capital stretch if capital has positive shadow price,

    else land, else storage, else None."""
    try:
        sc, _ = _validate(sc_dict)
        r = optimize(sc)
        if r.capital_shadow_price > 1e-6:
            stretches = r.get_capital_stretches(lang=lang)
            if stretches:
                first = stretches[0]
                return {
                    "resource": "capital",
                    "start_fortnight": first.get("start_fortnight"),
                    "end_fortnight": first.get("end_fortnight"),
                    "rate_for_stretch_pct": first.get("rate_for_stretch_pct"),
                }
            return {
                "resource": "capital",
                "usd_per_extra_dollar": round(float(r.capital_shadow_price), 4),
            }
        if r.land_shadow_price > 1e-6:
            return {
                "resource": "land",
                "usd_per_extra_ha": round(float(r.land_shadow_price), 2),
            }
        if sum(r.storage_shadow_price) > 1e-6:
            return {
                "resource": "storage",
                "usd_per_extra_tonne": round(float(sum(r.storage_shadow_price)), 2),
            }
    except Exception:
        pass
    return None


@dataclass
class AlternativeResult:
    alt: dict
    infeasible: bool
    shortfall_usd: float | None
    regret_usd: float
    winner_under_alternative: str | None = None

    @property
    def score_tuple(self) -> tuple[int, float]:
        # Priority level 3: infeasible with no shortfall (cannot be carried out)
        if self.infeasible and self.shortfall_usd is None:
            return (3, 0.0)
        # Priority level 2: cash shortfall
        if self.infeasible and self.shortfall_usd is not None:
            return (2, float(self.shortfall_usd))
        # Priority level 1: feasible regret
        return (1, float(self.regret_usd))


def next_question(
    scenario: dict | Scenario,
    asked: list[str] | None = None,
    compare: dict | None = None,
    previous: dict | None = None,
    lang: str | None = None,
) -> dict:
    """Determine the next most important question to ask the farmer."""
    if isinstance(scenario, Scenario):
        scenario_dict = {
            f.name: getattr(scenario, f.name)
            for f in scenario.__dataclass_fields__.values()
            if getattr(scenario, f.name) is not None
        }
    else:
        scenario_dict = dict(scenario or {})

    asked_set = set(asked or [])
    clean_lang = (lang or scenario_dict.get("lang") or "es").strip().lower()
    es = (clean_lang == "es")

    # -------------------------------------------------------------------------
    # 1. Blocking candidates
    # -------------------------------------------------------------------------
    # Area blocking check (except for same_budget mode)
    mode = str(compare.get("mode") if compare else scenario_dict.get("mode") or "same_farm").strip().lower()
    is_same_budget = (compare is not None and mode == "same_budget")
    has_area = (
        ("area_ha" in scenario_dict and scenario_dict["area_ha"] is not None)
        or ("owned_ha" in scenario_dict and scenario_dict["owned_ha"] is not None)
    )

    if not has_area and not is_same_budget:
        # Do not solve any season
        return {
            "done": False,
            "next": {
                "id": "area",
                "question": "¿Cuántas hectáreas tenés?" if es else "How many hectares do you have?",
                "if_unknown": None,
                "why": None,
            },
            "current": None,
            "change": None,
            "ranking": [],
            "stop_threshold_usd": 0.0,
        }

    # Compare basis blocking check
    if compare is not None and not compare.get("mode_given", False) and "compare_basis" not in asked_set:
        # Compute current for compare
        regs = compare.get("regions", ["pampas_core", "southeast_buenos_aires"])
        cur_cmp = compare_regions(scenario_dict, regions=regs, mode=mode)
        w = cur_cmp["best_region"]
        w_entry = cur_cmp["regions"][w]
        w_name = REGIONS[w].get("name", w)
        current_dict = {
            "npv_usd": w_entry["npv_usd"],
            "hectares": w_entry["hectares"],
            "rent_out_ha": w_entry.get("rent_out_ha", 0.0),
            "winner": w_name,
            "winner_id": w,
            "gap_usd": cur_cmp.get("npv_gap_to_next_usd"),
        }
        stop_thresh = round(STOP_SHARE * abs(w_entry["npv_usd"]), 2)
        return {
            "done": False,
            "next": {
                "id": "compare_basis",
                "question": (
                    "¿Comparás con el mismo campo en los dos lugares, o con la misma plata para comprar o alquilar campo en cada uno?"
                    if es else
                    "Are you comparing with the same farm in both places, or with the same money to buy or rent land in each?"
                ),
                "if_unknown": {"parameter": "mode", "value": "same_farm", "origin": "model assumption"},
                "why": None,
            },
            "current": current_dict,
            "change": None,
            "ranking": [],
            "stop_threshold_usd": stop_thresh,
        }

    # -------------------------------------------------------------------------
    # 2. Solve current situation
    # -------------------------------------------------------------------------
    if compare is None:
        cur_eval = evaluate_season(scenario_dict)
        cur_npv = cur_eval["npv_usd"]
        cur_plan = cur_eval["hectares"]
        cur_rent_out_ha = cur_eval.get("rent_out_ha", 0.0)
        current_dict = {
            "npv_usd": cur_npv,
            "hectares": cur_plan,
            "rent_out_ha": cur_rent_out_ha,
            "winner": None,
            "gap_usd": None,
        }
        sp_res = shadow_prices(scenario_dict, lang=clean_lang)
    else:
        regs = compare.get("regions", ["pampas_core", "southeast_buenos_aires"])
        cur_cmp = compare_regions(scenario_dict, regions=regs, mode=mode)
        w = cur_cmp["best_region"]
        w_entry = cur_cmp["regions"][w]
        w_name = REGIONS[w].get("name", w)
        cur_npv = w_entry["npv_usd"]
        cur_plan = w_entry["hectares"]
        cur_rent_out_ha = w_entry.get("rent_out_ha", 0.0)
        current_dict = {
            "npv_usd": cur_npv,
            "hectares": cur_plan,
            "rent_out_ha": cur_rent_out_ha,
            "winner": w_name,
            "winner_id": w,
            "gap_usd": cur_cmp.get("npv_gap_to_next_usd"),
        }
        sp_res = shadow_prices(dict(scenario_dict, region=w), lang=clean_lang)

    stop_threshold = round(STOP_SHARE * abs(cur_npv), 2)

    # -------------------------------------------------------------------------
    # 3. Change block (if previous is given)
    # -------------------------------------------------------------------------
    change_dict = None
    if previous:
        try:
            if compare is None:
                b_eval = evaluate_season(previous)
                a_eval = cur_eval
                npv_b = b_eval["npv_usd"]
                npv_a = a_eval["npv_usd"]
                change_dict = {
                    "npv_before_usd": npv_b,
                    "npv_after_usd": npv_a,
                    "npv_change_usd": round(npv_a - npv_b, 2),
                    "hectares_before": b_eval["hectares"],
                    "hectares_after": a_eval["hectares"],
                    "winner_before": None,
                    "winner_after": None,
                    "gap_before_usd": None,
                    "gap_after_usd": None,
                    "limit_before": _get_limit(previous, lang=clean_lang),
                    "limit_after": _get_limit(scenario_dict, lang=clean_lang),
                }
            else:
                regs = compare.get("regions", ["pampas_core", "southeast_buenos_aires"])
                b_cmp = compare_regions(previous, regions=regs, mode=mode)
                a_cmp = cur_cmp
                w_b = b_cmp["best_region"]
                w_a = a_cmp["best_region"]
                npv_b = b_cmp["regions"][w_b]["npv_usd"]
                npv_a = a_cmp["regions"][w_a]["npv_usd"]
                change_dict = {
                    "npv_before_usd": npv_b,
                    "npv_after_usd": npv_a,
                    "npv_change_usd": round(npv_a - npv_b, 2),
                    "hectares_before": b_cmp["regions"][w_b]["hectares"],
                    "hectares_after": a_cmp["regions"][w_a]["hectares"],
                    "winner_before": REGIONS[w_b].get("name", w_b),
                    "winner_after": REGIONS[w_a].get("name", w_a),
                    "gap_before_usd": b_cmp.get("npv_gap_to_next_usd"),
                    "gap_after_usd": a_cmp.get("npv_gap_to_next_usd"),
                    "limit_before": _get_limit(dict(previous, region=w_b), lang=clean_lang),
                    "limit_after": _get_limit(dict(scenario_dict, region=w_a), lang=clean_lang),
                }
        except Exception:
            change_dict = None

    # Check MAX_QUESTIONS stop
    if len(asked_set) >= MAX_QUESTIONS:
        return {
            "done": True,
            "done_reason": "max_questions",
            "next": None,
            "current": current_dict,
            "change": change_dict,
            "ranking": [],
            "stop_threshold_usd": stop_threshold,
        }

    # -------------------------------------------------------------------------
    # 4. Catalog and candidate evaluation
    # -------------------------------------------------------------------------
    candidate_defs = [
        {
            "id": "tenure",
            "param": "rented_land",
            "question_es": "¿El campo es tuyo o alquilado?",
            "question_en": "Is the land owned or rented?",
            "if_unknown": {"parameter": "rented_land", "value": False, "origin": "model assumption"},
            "resource": None,
            "skip": "rented_land" in scenario_dict or "tenure" in asked_set,
            "alts": lambda sc: [{"rented_land": not bool(sc.get("rented_land", False))}],
        },
        {
            "id": "rent_out",
            "param": "allow_rent_out",
            "question_es": "¿Lo querés trabajar vos, o lo darías en alquiler si conviene más?",
            "question_en": "Do you want to farm it yourself, or would you rent it out if that pays more?",
            "if_unknown": {"parameter": "allow_rent_out", "value": True, "origin": "model assumption"},
            "resource": None,
            "skip": "allow_rent_out" in scenario_dict or "rent_out" in asked_set or cur_rent_out_ha <= 1e-6,
            "alts": lambda sc: [{"allow_rent_out": False}],
        },
        {
            "id": "own_capital",
            "param": "own_capital_usd",
            "question_es": "¿Con cuánta plata propia arrancás la campaña?",
            "question_en": "How much of your own capital do you start the season with?",
            "if_unknown": {"parameter": "own_capital_usd", "value": 50000.0, "origin": "model assumption"},
            "resource": "capital",
            "skip": "own_capital_usd" in scenario_dict or "own_capital" in asked_set,
            "alts": lambda sc: [
                {"own_capital_usd": float(sc.get("own_capital_usd", 50000.0)) * 0.5},
                {"own_capital_usd": float(sc.get("own_capital_usd", 50000.0)) * 2.0},
            ],
        },
        {
            "id": "credit_line",
            "param": "credit_line_usd",
            "question_es": "¿Hasta cuánto te presta el banco?",
            "question_en": "How much does the bank lend you?",
            "if_unknown": {"parameter": "credit_line_usd", "value": 100000.0, "origin": "model assumption"},
            "resource": "credit_line",
            "skip": "credit_line_usd" in scenario_dict or "credit_line" in asked_set,
            "alts": lambda sc: [
                {"credit_line_usd": 0.0},
                {"credit_line_usd": float(sc.get("credit_line_usd", 100000.0)) * 2.0},
            ],
        },
        {
            "id": "supplier_terms",
            "param": "input_payment_delay_fortnights",
            "question_es": "¿A cuántos días te deja pagar los insumos tu proveedor?",
            "question_en": "How many days does your supplier allow you to pay for inputs?",
            "if_unknown": {"parameter": "input_payment_delay_fortnights", "value": 0, "origin": "model assumption"},
            "resource": None,
            "skip": "input_payment_delay_fortnights" in scenario_dict or "supplier_terms" in asked_set,
            "alts": lambda sc: [{"input_payment_delay_fortnights": 6}],
        },
        {
            "id": "storage",
            "param": "storage_capacity_t",
            "question_es": "¿Cuántas toneladas podés guardar, en silo o silobolsa?",
            "question_en": "How many tonnes can you store, in silos or silo bags?",
            "if_unknown": {"parameter": "storage_capacity_t", "value": 1000.0, "origin": "model assumption"},
            "resource": "storage",
            "skip": "storage_capacity_t" in scenario_dict or "storage" in asked_set,
            "alts": lambda sc: [
                {"storage_capacity_t": 0.0},
                {"storage_capacity_t": float(sc.get("storage_capacity_t", 1000.0)) * 2.0},
            ],
        },
    ]

    evaluated_candidates = []
    for cdef in candidate_defs:
        if cdef["skip"]:
            continue

        c_id = cdef["id"]
        alts_to_test = cdef["alts"](scenario_dict)
        alt_results: list[AlternativeResult] = []

        for alt in alts_to_test:
            if compare is None:
                sc_alt = dict(scenario_dict, **alt)
                p_eval = evaluate_plan(sc_alt, cur_plan)
                if not p_eval["feasible"]:
                    alt_results.append(AlternativeResult(
                        alt=alt,
                        infeasible=True,
                        shortfall_usd=p_eval.get("extra_credit_needed_usd"),
                        regret_usd=0.0,
                    ))
                else:
                    alt_results.append(AlternativeResult(
                        alt=alt,
                        infeasible=False,
                        shortfall_usd=None,
                        regret_usd=float(p_eval.get("gap_usd") or 0.0),
                    ))
            else:
                regs = compare.get("regions", ["pampas_core", "southeast_buenos_aires"])
                cmp_alt = compare_regions(dict(scenario_dict, **alt), regions=regs, mode=mode)
                win_alt = cmp_alt["best_region"]
                win_alt_name = REGIONS[win_alt].get("name", win_alt)
                best_npv_alt = cmp_alt["regions"][win_alt]["npv_usd"]

                reg_info = REGIONS[w]
                tax_info = load_taxes_data(w)
                land_info = load_land_data(w)
                reg_w_sc_alt = _prepare_region_scenario(w, dict(scenario_dict, **alt), mode, tax_info, land_info, reg_info)
                p_eval = evaluate_plan(reg_w_sc_alt, cur_plan)

                if not p_eval["feasible"]:
                    alt_results.append(AlternativeResult(
                        alt=alt,
                        infeasible=True,
                        shortfall_usd=p_eval.get("extra_credit_needed_usd"),
                        regret_usd=0.0,
                        winner_under_alternative=win_alt_name,
                    ))
                else:
                    plan_w_npv = float(p_eval.get("npv_plan_usd") or 0.0)
                    regret = max(0.0, round(best_npv_alt - plan_w_npv, 2))
                    alt_results.append(AlternativeResult(
                        alt=alt,
                        infeasible=False,
                        shortfall_usd=None,
                        regret_usd=regret,
                        winner_under_alternative=win_alt_name,
                    ))

        if not alt_results:
            continue

        # Candidate's score is its worst alternative
        worst_alt_res = max(alt_results, key=lambda ar: ar.score_tuple)
        evaluated_candidates.append({
            "def": cdef,
            "worst": worst_alt_res,
        })

    # Sort candidates by worst score descending
    evaluated_candidates.sort(key=lambda ec: ec["worst"].score_tuple, reverse=True)

    if not evaluated_candidates:
        return {
            "done": True,
            "done_reason": "below_threshold",
            "next": None,
            "current": current_dict,
            "change": change_dict,
            "ranking": [],
            "stop_threshold_usd": stop_threshold,
            "max_regret_left_usd": 0.0,
        }

    top = evaluated_candidates[0]
    top_worst = top["worst"]
    top_def = top["def"]

    # Stop if top candidate is feasible and below threshold
    if not top_worst.infeasible and top_worst.regret_usd < stop_threshold:
        return {
            "done": True,
            "done_reason": "below_threshold",
            "next": None,
            "current": current_dict,
            "change": change_dict,
            "ranking": [],
            "stop_threshold_usd": stop_threshold,
            "max_regret_left_usd": round(top_worst.regret_usd, 2),
        }

    # Build `next` object
    why_obj: dict[str, Any] = {
        "alternative": top_worst.alt,
        "infeasible": top_worst.infeasible,
    }
    if top_worst.infeasible:
        if top_worst.shortfall_usd is not None:
            why_obj["shortfall_usd"] = round(top_worst.shortfall_usd, 2)
    else:
        why_obj["regret_usd"] = round(top_worst.regret_usd, 2)
        if top_worst.winner_under_alternative:
            why_obj["winner_under_alternative"] = top_worst.winner_under_alternative

    # Attach shadow price if applicable
    res_type = top_def["resource"]
    if res_type == "credit_line" and "credit_line" in sp_res:
        why_obj["shadow_price"] = {
            "resource": "credit_line",
            "usd_per_extra_dollar": round(float(sp_res["credit_line"].get("usd_per_extra_dollar", 0.0)), 4),
        }
    elif res_type == "capital" and "own_capital" in sp_res:
        why_obj["shadow_price"] = {
            "resource": "capital",
            "usd_per_extra_dollar": round(float(sp_res["own_capital"].get("usd_per_extra_dollar", 0.0)), 4),
        }
    elif res_type == "storage" and "storage" in sp_res:
        why_obj["shadow_price"] = {
            "resource": "storage",
            "usd_per_extra_tonne": round(float(sp_res["storage"].get("usd_per_extra_tonne", 0.0)), 2),
        }

    next_obj = {
        "id": top_def["id"],
        "question": top_def["question_es"] if es else top_def["question_en"],
        "if_unknown": top_def["if_unknown"],
        "why": why_obj,
    }

    # Build ranking (up to 3 after next)
    ranking_list = []
    for cand in evaluated_candidates[1:4]:
        c_w = cand["worst"]
        r_entry = {
            "id": cand["def"]["id"],
            "score": {
                "infeasible": c_w.infeasible,
                "shortfall_usd": round(c_w.shortfall_usd, 2) if c_w.shortfall_usd is not None else None,
                "regret_usd": round(c_w.regret_usd, 2) if not c_w.infeasible else None,
            },
        }
        ranking_list.append(r_entry)

    return {
        "done": False,
        "next": next_obj,
        "current": current_dict,
        "change": change_dict,
        "ranking": ranking_list,
        "stop_threshold_usd": stop_threshold,
    }

