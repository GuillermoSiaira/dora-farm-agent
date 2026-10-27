"""Run evaluation harness over eval/questions.jsonl and write results to eval/results/."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dora.agent import Agent
from dora.verifier import _PATTERN, _SCALES, _readings, _tolerance
from eval.build_answers import IOWA_SUPPORTED

DEFAULT_QUESTIONS_PATH = ROOT / "questions.jsonl"
DEFAULT_ANSWERS_PATH = ROOT / "answers.jsonl"
RESULTS_DIR = ROOT / "results"


def match_scenario(actual: dict, expected: dict) -> bool:
    """Check if actual scenario matches expected scenario within 1% for numbers."""
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    actual = dict(actual)
    if "area_ha" not in actual and "owned_ha" in actual:     # owned_ha is the same farm size (SPEC-10)
        actual["area_ha"] = actual["owned_ha"]
    for k, v in expected.items():
        if k not in actual:
            return False
        act_v = actual[k]
        if k == "constraints":
            if not isinstance(act_v, list) or len(act_v) != len(v):
                return False
            for act_c, exp_c in zip(act_v, v):
                if act_c.get("type") != exp_c.get("type"):
                    return False
                if act_c.get("crop") != exp_c.get("crop"):
                    return False
                if "month" in exp_c and act_c.get("month") != exp_c.get("month"):
                    return False
                for num_field in ("ha", "share", "tonnes", "price_usd_t"):
                    if num_field in exp_c:
                        if num_field not in act_c:
                            return False
                        exp_num = float(exp_c[num_field])
                        act_num = float(act_c[num_field])
                        denom = max(abs(exp_num), 1e-9)
                        if abs(act_num - exp_num) / denom > 0.01:
                            return False
        elif isinstance(v, dict):
            if not isinstance(act_v, dict):
                return False
            for sub_k, sub_v in v.items():
                if sub_k not in act_v:
                    return False
                if isinstance(sub_v, (int, float)):
                    exp_num = float(sub_v)
                    act_num = float(act_v[sub_k])
                    denom = max(abs(exp_num), 1e-9)
                    if abs(act_num - exp_num) / denom > 0.01:
                        return False
                elif act_v[sub_k] != sub_v:
                    return False
        elif isinstance(v, bool):
            if act_v is not v:
                return False
        elif isinstance(v, (int, float)):
            exp_num = float(v)
            try:
                act_num = float(act_v)
            except (ValueError, TypeError):
                return False
            denom = max(abs(exp_num), 1e-9)
            if abs(act_num - exp_num) / denom > 0.01:
                return False
        else:
            if act_v != v:
                return False
    return True


def text_contains_expected_value(text: str, expected_val: Any) -> bool:
    """Check if the text contains expected_val using the verifier's number reader."""
    if isinstance(expected_val, str):
        return expected_val.lower() in text.lower()
    if not isinstance(expected_val, (int, float)):
        return False

    target = float(expected_val)
    for m in _PATTERN.finditer(text):
        scale_str = (m.group("scale") or "").lower()
        factor = _SCALES.get(scale_str, 1)
        pct = bool(m.group("pct"))
        for v, decimals in _readings(m.group("num")):
            val = v * factor
            if pct:
                val /= 100.0
            tol = _tolerance(val, decimals)
            # Accept if target is within tolerance
            if abs(val - target) <= tol + 1e-6:
                return True
    return False


def run_evaluation(
    client=None,
    model: str = "default",
    runs: int = 1,
    use_verifier: bool = True,
    limit: int | None = None,
    questions_path: Path | str = DEFAULT_QUESTIONS_PATH,
    answers_path: Path | str = DEFAULT_ANSWERS_PATH,
    output_path: Path | str | None = None,
) -> dict:
    """Run the evaluation suite over the questions."""
    q_file = Path(questions_path)
    a_file = Path(answers_path)

    questions: list[dict] = []
    with open(q_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))

    # Skip Iowa questions only if not supported
    if not IOWA_SUPPORTED:
        active_questions = [q for q in questions if q.get("region") != "iowa"]
    else:
        active_questions = list(questions)
    if limit is not None and limit > 0:
        active_questions = active_questions[:limit]

    answers_map: dict[str, Any] = {}
    if a_file.is_file():
        with open(a_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    item = json.loads(line)
                    answers_map[item["id"]] = item["expected_value"]

    run_metrics = []
    detailed_results = []

    for run_idx in range(runs):
        q_results = []
        tool_acc_hits = 0
        answer_correct_hits = 0
        formulation_hits = 0
        formulation_total = 0
        unsupported_count = 0
        verified_count = 0
        total_calls = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0

        for q in active_questions:
            agent = Agent(client=client, model=model, use_verifier=use_verifier)
            reply = agent.ask(q["text"])

            calls = reply.tool_calls
            total_calls += len(calls)
            total_prompt_tokens += reply.usage.get("prompt_tokens", 0)
            total_completion_tokens += reply.usage.get("completion_tokens", 0)

            # 1. Formulation accuracy
            is_formulation = q.get("type") == "formulation"
            formulation_hit = False
            if is_formulation:
                formulation_total += 1
                for c in calls:
                    arg_str = c.get("arguments", "{}")
                    try:
                        args = json.loads(arg_str) if isinstance(arg_str, str) else arg_str
                    except json.JSONDecodeError:
                        args = {}
                    sc = args.get("scenario", {})
                    if match_scenario(sc, q["scenario"]):
                        formulation_hit = True
                        break
                if formulation_hit:
                    formulation_hits += 1

            # 2. Tool accuracy
            tool_hit = False
            if q.get("expect") == "refuse":
                eval_calls = [c for c in calls if c.get("tool") == "evaluate_season"]
                tool_hit = len(eval_calls) == 0
            else:
                expected_tools = set(q.get("expected_tools", []))
                if "evaluate_season" in expected_tools:      # these tools also solve the season
                    expected_tools |= {"sensitivity", "shadow_prices"}
                for c in calls:
                    if c.get("tool") in expected_tools:
                        arg_str = c.get("arguments", "{}")
                        try:
                            args = json.loads(arg_str) if isinstance(arg_str, str) else arg_str
                        except json.JSONDecodeError:
                            args = {}
                        sc = args.get("scenario", {})
                        if match_scenario(sc, q["scenario"]):
                            tool_hit = True
                            break
            if tool_hit:
                tool_acc_hits += 1

            # 3. Answer correctness
            answer_hit = False
            if q.get("expect") == "refuse":
                refuse_markers = ["no soporta", "arroz", "inválido", "negativ", "superficie", "falta", "aclarar", "cuántas ha", "error",
                                  "not valid", "isn't valid", "invalid", "not supported", "missing", "clarify"]
                answer_hit = any(m in reply.text.lower() for m in refuse_markers)
            elif q["id"] in answers_map:
                exp_val = answers_map[q["id"]]
                answer_hit = text_contains_expected_value(reply.text, exp_val)
            if answer_hit:
                answer_correct_hits += 1

            # 4. Unsupported numbers before correction
            has_unsupported = len(reply.initial_unsupported) > 0
            if has_unsupported:
                unsupported_count += 1

            # 5. Verified after correction
            if reply.verified:
                verified_count += 1

            q_results.append({
                "id": q["id"],
                "text": q["text"],
                "reply": reply.text,
                "verified": reply.verified,
                "tool_calls_count": len(calls),
                "tool_accuracy": tool_hit,
                "answer_correctness": answer_hit,
                "formulation_accuracy": formulation_hit if is_formulation else None,
                "has_unsupported_before_correction": has_unsupported,
            })

        n_q = len(active_questions)
        run_metric = {
            "run_index": run_idx,
            "tool_accuracy": tool_acc_hits / n_q if n_q else 0.0,
            "answer_correctness": answer_correct_hits / n_q if n_q else 0.0,
            "formulation_accuracy": formulation_hits / formulation_total if formulation_total else 1.0,
            "unsupported_numbers_rate": unsupported_count / n_q if n_q else 0.0,
            "verified_rate": verified_count / n_q if n_q else 0.0,
            "calls_per_question": total_calls / n_q if n_q else 0.0,
            "prompt_tokens_per_question": total_prompt_tokens / n_q if n_q else 0.0,
            "completion_tokens_per_question": total_completion_tokens / n_q if n_q else 0.0,
            "questions_count": n_q,
        }
        run_metrics.append(run_metric)
        detailed_results.append(q_results)

    # Aggregated metrics over all runs
    def agg(key: str) -> dict[str, float]:
        vals = [r[key] for r in run_metrics]
        return {
            "mean": sum(vals) / len(vals) if vals else 0.0,
            "min": min(vals) if vals else 0.0,
            "max": max(vals) if vals else 0.0,
        }

    aggregated = {
        "tool_accuracy": agg("tool_accuracy"),
        "answer_correctness": agg("answer_correctness"),
        "formulation_accuracy": agg("formulation_accuracy"),
        "unsupported_numbers_rate": agg("unsupported_numbers_rate"),
        "verified_rate": agg("verified_rate"),
        "calls_per_question": agg("calls_per_question"),
        "prompt_tokens_per_question": agg("prompt_tokens_per_question"),
        "completion_tokens_per_question": agg("completion_tokens_per_question"),
    }

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    model_slug = re.sub(r"[^\w\-]", "_", model)

    results_data = {
        "model": model,
        "use_verifier": use_verifier,
        "runs": runs,
        "timestamp": timestamp,
        "run_metrics": run_metrics,
        "aggregated": aggregated,
        "detailed_results": detailed_results,
    }

    if output_path is None:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        verifier_suffix = "with_verifier" if use_verifier else "no_verifier"
        output_file = RESULTS_DIR / f"{model_slug}_{verifier_suffix}_{timestamp}.json"
    else:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=2, ensure_ascii=False)

    return results_data


def main():
    parser = argparse.ArgumentParser(description="Run DORA evaluation harness")
    parser.add_argument("--model", type=str, default=os.environ.get("DORA_MODEL", "default"), help="Model name")
    parser.add_argument("--runs", type=int, default=5, help="Number of runs (default: 5)")
    parser.add_argument("--no-verifier", action="store_true", help="Disable verifier correction rounds")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of questions to evaluate")
    parser.add_argument("--questions", type=str, default=str(DEFAULT_QUESTIONS_PATH), help="Path to questions.jsonl")
    parser.add_argument("--answers", type=str, default=str(DEFAULT_ANSWERS_PATH), help="Path to answers.jsonl")
    parser.add_argument("--output", type=str, default=None, help="Output path for results JSON")

    args = parser.parse_args()

    res = run_evaluation(
        model=args.model,
        runs=args.runs,
        use_verifier=not args.no_verifier,
        limit=args.limit,
        questions_path=args.questions,
        answers_path=args.answers,
        output_path=args.output,
    )
    print(f"Evaluation complete. Runs: {args.runs}, Verifier: {not args.no_verifier}")
    print(f"Tool Accuracy: {res['aggregated']['tool_accuracy']['mean']:.1%}")
    print(f"Answer Correctness: {res['aggregated']['answer_correctness']['mean']:.1%}")
    print(f"Verified Rate: {res['aggregated']['verified_rate']['mean']:.1%}")


if __name__ == "__main__":
    main()
