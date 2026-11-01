"""Run experiment E7: the farmer interview with a simulated farmer.

SPEC-29 implementation.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_dotenv(PROJECT_ROOT / ".env")

from dora.agent import Agent, default_client
from dora.tools import compare_regions, evaluate_season

FARMS_PATH = ROOT / "e7" / "farms.jsonl"
RESULTS_PATH = ROOT / "results" / "e7_results.json"


def load_farms() -> list[dict]:
    farms = []
    with open(FARMS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                farms.append(json.loads(line))
    return farms


def simulated_farmer_reply(next_id: str | None, hidden: dict) -> str:
    """Deterministic simulated farmer response based on hidden scenario."""
    if not next_id:
        return "seguí"
    if next_id == "area":
        return f"Tengo {hidden.get('area_ha', 500):.0f} hectáreas."
    if next_id == "compare_basis":
        if hidden.get("mode") == "same_farm":
            return "Comparo con el mismo campo en los dos lugares."
        return "Comparo con la misma plata para comprar o alquilar campo en cada uno."
    if next_id == "tenure":
        return "El campo es alquilado." if hidden.get("rented_land") else "El campo es propio."
    if next_id == "rent_out":
        if not hidden.get("allow_rent_out", True):
            return "Lo quiero trabajar yo, no quiero alquilarlo."
        return "Si conviene más alquilarlo, lo alquilo."
    if next_id == "own_capital":
        if "own_capital_usd" in hidden:
            return f"Arranco con {hidden['own_capital_usd']:.0f} USD propios."
        return "No sé."
    if next_id == "credit_line":
        if "credit_line_usd" in hidden:
            val = hidden["credit_line_usd"]
            return f"El banco me presta hasta {val:.0f} USD." if val > 0 else "No tengo crédito."
        return "No sé."
    if next_id == "supplier_terms":
        if "input_payment_delay_fortnights" in hidden:
            days = int(hidden["input_payment_delay_fortnights"] * 15)
            return f"El proveedor me deja pagar los insumos a {days} días." if days > 0 else "Pago al contado."
        return "No sé."
    if next_id == "storage":
        if "storage_capacity_t" in hidden:
            return f"Tengo {hidden['storage_capacity_t']:.0f} toneladas de silo."
        return "No sé."
    return "No sé."


def compute_ground_truth(case: dict) -> dict:
    hidden = dict(case["hidden_farm"])
    if case.get("compare"):
        mode = hidden.pop("mode", "same_farm")
        hidden.pop("mode_given", None)
        regs = hidden.pop("regions", case["compare"]["regions"])
        cmp_res = compare_regions(hidden, regions=regs, mode=mode)
        w = cmp_res["best_region"]
        return {
            "winner": w,
            "npv_usd": cmp_res["regions"][w]["npv_usd"],
            "hectares": cmp_res["regions"][w]["hectares"],
        }
    else:
        ev = evaluate_season(hidden)
        return {
            "winner": None,
            "npv_usd": ev["npv_usd"],
            "hectares": ev["hectares"],
        }


def hectares_match(actual: dict, expected: dict, tol: float = 1.0) -> bool:
    all_crops = set(actual.keys()) | set(expected.keys())
    for c in all_crops:
        if abs(float(actual.get(c, 0.0)) - float(expected.get(c, 0.0))) > tol:
            return False
    return True


def run_interview_case(agent: Agent, case: dict, max_turns: int = 6) -> dict:
    hidden = case["hidden_farm"]
    gt = compute_ground_truth(case)

    turns = []
    msg = case["opening_message"]
    decision_reached_at_turn = None

    for turn_idx in range(1, max_turns + 1):
        t0 = time.time()
        prev_usage = dict(agent.usage)
        rep = agent.ask(msg)
        elapsed = round(time.time() - t0, 2)

        turn_prompt = agent.usage.get("prompt_tokens", 0) - prev_usage.get("prompt_tokens", 0)
        turn_comp = agent.usage.get("completion_tokens", 0) - prev_usage.get("completion_tokens", 0)
        turn_total = turn_prompt + turn_comp

        text = rep.text
        has_more_than_one_q = text.count("?") > 1
        says_if_unknown = any(w in text.lower() for w in ["si no sabés", "si no sabes", "por defecto", "típico", "tipico", "supuesto", "sigo con", "asumo"])

        # Check if decision matched ground truth in this turn
        matched_gt = False
        interview_info = rep.interview or {}
        next_id = interview_info.get("next_id")
        done = interview_info.get("done", False)

        turn_record = {
            "turn": turn_idx,
            "farmer_message": msg,
            "reply": text,
            "verified": rep.verified,
            "next_id": next_id,
            "done": done,
            "seconds": elapsed,
            "tokens": turn_total,
            "more_than_one_question": has_more_than_one_q,
            "says_if_unknown": says_if_unknown,
            "style_problems": rep.style_problems,
        }
        turns.append(turn_record)

        if done or turn_idx == max_turns:
            break

        # Simulate farmer response
        msg = simulated_farmer_reply(next_id, hidden)

    return {
        "case_id": case["id"],
        "name": case["name"],
        "ground_truth": gt,
        "turns_count": len(turns),
        "total_seconds": round(sum(t["seconds"] for t in turns), 2),
        "total_tokens": sum(t["tokens"] for t in turns),
        "stopped_by_itself": any(t["done"] for t in turns),
        "replies_with_multiple_questions": sum(1 for t in turns if t["more_than_one_question"]),
        "questions_with_if_unknown": sum(1 for t in turns if t["says_if_unknown"]),
        "turns": turns,
    }


def main():
    parser = argparse.ArgumentParser(description="Run E7 interview evaluation")
    parser.add_argument("--pilot", action="store_true", help="Run pilot (case_a, 1 run)")
    parser.add_argument("--case", type=str, default=None, help="Run specific case_id")
    parser.add_argument("--runs", type=int, default=1, help="Number of runs per case")
    parser.add_argument("--out", type=str, default=str(RESULTS_PATH), help="Output path")
    args = parser.parse_args()

    farms = load_farms()
    if args.pilot:
        farms = [f for f in farms if f["id"] == "case_a"]
        args.runs = 1
    elif args.case:
        farms = [f for f in farms if f["id"] == args.case]

    client = default_client()
    model = os.environ.get("DORA_MODEL", "")

    print(f"Running E7 evaluation on {len(farms)} case(s), {args.runs} run(s) per case using model {model}...")

    all_results = []
    for farm in farms:
        for run_i in range(1, args.runs + 1):
            print(f"\n--- {farm['id']} (Run {run_i}/{args.runs}) ---")
            ag = Agent(client=client, model=model, use_verifier=True)
            res = run_interview_case(ag, farm)
            res["run"] = run_i
            all_results.append(res)
            print(f"Finished in {res['turns_count']} turns, {res['total_seconds']}s, {res['total_tokens']} tokens.")
            print(f"Stopped by itself: {res['stopped_by_itself']}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()

