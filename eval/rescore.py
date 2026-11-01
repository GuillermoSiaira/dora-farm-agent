#!/usr/bin/env python3
"""Recomputes E1 evaluation metrics from stored result JSON files without network.

Implements the SPEC-27 offline rescoring rules:
- refusal rule (stored plan_hectares stands for 'a season was solved'),
- decision rule for q33 (decision_named),
- plan_given and plan_feasible for {} plans (calling evaluate_plan, no network).

Never overwrites the input file.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.plan_check import evaluate_plan
from eval.run_eval import (
    REFUSE_MARKERS, _has_plan, _mean, _rate, decision_named,
)


def load_all_questions() -> dict[str, dict]:
    questions: dict[str, dict] = {}
    for pattern in ["questions.jsonl", "questions_*.jsonl"]:
        for path in (ROOT).glob(pattern):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            q = json.loads(line)
                            questions[q["id"]] = q
                        except Exception:
                            pass
    return questions


def rescore_data(data: dict, questions: dict[str, dict]) -> dict:
    """Rescore in-memory evaluation results dict according to SPEC-27."""
    res = json.loads(json.dumps(data))  # deep copy
    detailed_results = res.get("detailed_results", [])
    runs = len(detailed_results)

    # Store before counts per question
    before_counts: dict[str, int] = {}
    for qid, pq in res.get("per_question", {}).items():
        before_counts[qid] = pq.get("correct_runs", 0)

    # Process each record
    for run_idx, q_results in enumerate(detailed_results):
        for rec in q_results:
            qid = rec["id"]
            q = questions.get(qid, {})
            text = rec.get("reply", "")

            # 1. Refusal rule
            if q.get("expect") == "refuse":
                no_plan = not bool(rec.get("plan_hectares"))
                contains_refusal = "?" in text or any(m in text.lower() for m in REFUSE_MARKERS)
                rec["answer_correctness"] = bool(no_plan and contains_refusal)

            # 2. Decision rule for q33 and kind == "decision"
            elif qid == "q33" or q.get("check", {}).get("kind") == "decision":
                expected = "iowa" if qid == "q33" else rec.get("expected_value")
                regions = q.get("check", {}).get("payload", {}).get("regions", ["pampas_core", "iowa"])
                rec["answer_correctness"] = decision_named(text, expected, regions)

            # 3. Plan fields update
            ha = rec.get("plan_hectares")
            if ha == {} and _has_plan(q):
                try:
                    sc = q.get("scenario", {})
                    ev = evaluate_plan(sc, {})
                    rec["plan_given"] = True
                    rec["plan_feasible"] = ev["feasible"]
                    rec["plan_violations"] = ev["violations"]
                    rec["plan_npv_usd"] = ev["npv_plan_usd"]
                    rec["plan_gap_usd"] = ev["gap_usd"]
                    rec["plan_gap_pct"] = ev["gap_pct"]
                    rec["npv_optimal_usd"] = ev["npv_optimal_usd"]
                except Exception:
                    pass
            elif ha is None:
                rec["plan_given"] = False
                rec["plan_feasible"] = None
                rec["plan_violations"] = None
            elif isinstance(ha, dict):
                rec["plan_given"] = True

        # Recompute run_metrics for this run
        if run_idx < len(res.get("run_metrics", [])):
            rm = res["run_metrics"][run_idx]
            rm["answer_correctness"] = _rate(q_results, "answer_correctness")
            rm["plan_given_rate"] = _rate(q_results, "plan_given")
            rm["feasible_rate"] = _rate([r for r in q_results if r.get("plan_given")], "plan_feasible")

    # Recompute aggregated metrics
    run_metrics = res.get("run_metrics", [])
    def agg(key: str) -> dict[str, float | None]:
        vals = [r[key] for r in run_metrics if r.get(key) is not None]
        return {
            "mean": sum(vals) / len(vals) if vals else None,
            "min": min(vals) if vals else None,
            "max": max(vals) if vals else None,
        }

    if "aggregated" in res:
        for k in ("answer_correctness", "plan_given_rate", "feasible_rate"):
            res["aggregated"][k] = agg(k)

    # Recompute per_question
    per_question = res.get("per_question", {})
    all_qids = (
        res.get("question_ids")
        or list(per_question.keys())
        or [r.get("id") or r.get("question_id") for r in (detailed_results[0] if detailed_results else [])]
    )
    for idx, qid in enumerate(all_qids):
        recs = [detailed_results[r][idx] for r in range(runs) if idx < len(detailed_results[r])]
        if qid not in per_question:
            per_question[qid] = {}
        per_question[qid]["correct_runs"] = sum(1 for r in recs if r.get("answer_correctness"))
        per_question[qid]["feasible_runs"] = sum(1 for r in recs if r.get("plan_feasible"))
        per_question[qid]["plan_runs"] = sum(1 for r in recs if r.get("plan_feasible") is not None)
        per_question[qid]["no_plan_runs"] = sum(1 for r in recs if r.get("plan_given") is False)

    res["per_question"] = per_question
    return res


def main():
    parser = argparse.ArgumentParser(description="Recompute E1 results from stored JSON file")
    parser.add_argument("results_file", type=str, help="Path to evaluation results JSON file")
    parser.add_argument("--out", type=str, default=None, help="Output path (cannot be the input file)")
    args = parser.parse_args()

    in_path = Path(args.results_file).resolve()
    if not in_path.is_file():
        print(f"Error: file not found: {in_path}", file=sys.stderr)
        sys.exit(1)

    if args.out:
        out_path = Path(args.out).resolve()
        if out_path == in_path:
            print("Error: --out path cannot overwrite the input file.", file=sys.stderr)
            sys.exit(1)
    else:
        out_path = None

    print(f"Rescoring {in_path.name}...")
    print("Note: Older files have no tool results, so a sensitivity plan cannot be recovered there.")

    with open(in_path, encoding="utf-8") as f:
        data = json.load(f)

    questions = load_all_questions()

    before_counts = {}
    if "per_question" in data:
        before_counts = {qid: pq.get("correct_runs", 0) for qid, pq in data["per_question"].items()}
    else:
        for q_results in data.get("detailed_results", []):
            for rec in q_results:
                qid = rec.get("id") or rec.get("question_id")
                if qid:
                    before_counts[qid] = before_counts.get(qid, 0) + int(bool(rec.get("answer_correctness") or rec.get("answer_correct")))
    before_feasible = data.get("aggregated", {}).get("feasible_rate", {}).get("mean")

    rescored = rescore_data(data, questions)

    after_counts = {qid: pq.get("correct_runs", 0) for qid, pq in rescored.get("per_question", {}).items()}
    after_feasible = rescored.get("aggregated", {}).get("feasible_rate", {}).get("mean")

    print("\nPer-question correct runs (before -> after):")
    print(f"{'Question':<10} | {'Before':<8} | {'After':<8} | {'Diff':<8}")
    print("-" * 42)
    for qid in sorted(before_counts.keys() | after_counts.keys()):
        bef = before_counts.get(qid, 0)
        aft = after_counts.get(qid, 0)
        diff = aft - bef
        diff_str = f"+{diff}" if diff > 0 else (str(diff) if diff < 0 else "=")
        if diff != 0 or qid in ("q17", "q30", "q33", "q06"):
            print(f"{qid:<10} | {bef:<8} | {aft:<8} | {diff_str:<8}")

    print("\nSummary:")
    old_acc = data.get("aggregated", {}).get("answer_correctness", {}).get("mean")
    new_acc = rescored.get("aggregated", {}).get("answer_correctness", {}).get("mean")
    print(f"Answer Correctness: {old_acc:.1%} -> {new_acc:.1%}" if old_acc is not None and new_acc is not None else "")
    print(f"Feasible rate:      {before_feasible:.1%} -> {after_feasible:.1%}" if before_feasible is not None and after_feasible is not None else "")

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(rescored, f, indent=2, ensure_ascii=False)
        print(f"\nRescored results saved to: {out_path}")


if __name__ == "__main__":
    main()
