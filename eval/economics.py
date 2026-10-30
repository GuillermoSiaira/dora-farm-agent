"""Economics of verified answers (SPEC-24).

Pure functions (no network) to calculate:
- Cost per question across pricing models (per-token, dedicated GPU, serverless GPU)
- Cost per verified correct answer
- Bootstrap 95% confidence intervals
- Exact McNemar paired comparisons
- Break-even volume for dedicated GPUs
- Fixed prompt overhead analysis
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import scipy.stats

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_PRICING_PATH = ROOT / "pricing.json"


def load_pricing(pricing_path: Path | str | None = None) -> dict[str, dict]:
    """Load pricing database from JSON file."""
    path = Path(pricing_path or DEFAULT_PRICING_PATH)
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_pricing_entry(pricing: dict[str, dict], model: str, provider: str | None = None) -> dict | None:
    """Look up pricing entry for model and optional provider.
    
    Checks exact matches like 'model@provider', provider-specific keys, or model alone.
    """
    if not pricing:
        return None
    candidates = []
    if provider:
        candidates.append(f"{model}@{provider}")
        if not provider.endswith("-dedicated"):
            candidates.append(f"{model}@{provider}-dedicated")
        candidates.append(f"default@{provider}")
        if not provider.endswith("-dedicated"):
            candidates.append(f"default@{provider}-dedicated")
        candidates.append(provider)
    candidates.append(model)
    candidates.append("default")

    for c in candidates:
        if c in pricing:
            return pricing[c]
    return None


def calculate_cost_per_question(record: dict, pricing_entry: dict | None) -> float | None:
    """Calculate the cost of a single question record in USD, or None if price is unknown."""
    if not pricing_entry:
        return None

    billing = pricing_entry.get("billing")
    if billing == "per_token":
        usd_in = pricing_entry.get("usd_per_m_input")
        usd_out = pricing_entry.get("usd_per_m_output")
        if usd_in is None or usd_out is None:
            return None
        usd_cached = pricing_entry.get("usd_per_m_cached_input")
        if usd_cached is None:
            usd_cached = usd_in

        pt = record.get("prompt_tokens", 0) or 0
        ct = record.get("completion_tokens", 0) or 0
        c_in = record.get("cached_prompt_tokens", 0) or 0
        uncached_in = max(0, pt - c_in)

        cost = (uncached_in * float(usd_in) + c_in * float(usd_cached) + ct * float(usd_out)) / 1_000_000.0
        return cost

    elif billing == "dedicated":
        usd_hour = pricing_entry.get("usd_per_gpu_hour")
        if usd_hour is None:
            return None
        gpus = float(pricing_entry.get("gpus", 1) or 1)
        latency_s = float(record.get("latency_s", 0.0) or 0.0)
        return float(usd_hour) * gpus * latency_s / 3600.0

    elif billing == "serverless_gpu":
        usd_sec = pricing_entry.get("usd_per_gpu_second")
        if usd_sec is None:
            return None
        gpus = float(pricing_entry.get("gpus", 1) or 1)
        latency_s = float(record.get("latency_s", 0.0) or 0.0)
        return float(usd_sec) * gpus * latency_s

    return None


def is_verified_correct(record: dict, condition: str | None = None) -> bool:
    """Determine whether an answer record is verified and correct.
    
    In condition A (baseline): verified means has_unsupported_before_correction is False.
    In conditions B and C: verified means record['verified'] is True.
    """
    ans_correct = bool(record.get("answer_correctness"))
    if not ans_correct:
        return False

    cond = condition or record.get("condition")
    if cond == "baseline" or ("verified" not in record and "has_unsupported_before_correction" in record):
        return not bool(record.get("has_unsupported_before_correction"))
    return bool(record.get("verified"))


def bootstrap_ci(
    records: list[dict] | dict,
    pricing_entry: dict | None = None,
    condition: str | None = None,
    n_resamples: int = 2000,
    seed: int = 20261029,
    metric: str | None = None,
) -> dict[str, Any] | tuple[float, float] | None | str:
    """Compute 95% bootstrap confidence intervals over questions using fixed random seed.
    
    Returns intervals for:
    - answer_correctness: (low, high)
    - verified_correct: (low, high)
    - usd_per_verified_correct_answer: (low, high) or None if price unknown
    """
    if isinstance(records, dict):
        det = records.get("detailed_results", [])
        if det and isinstance(det[0], list):
            rec_list = [r for run_recs in det for r in run_recs]
        else:
            rec_list = det
        cond = condition or records.get("condition")
    else:
        rec_list = records
        cond = condition

    n = len(rec_list)
    if n == 0:
        res = {
            "answer_correctness": (0.0, 0.0),
            "verified_correct": (0.0, 0.0),
            "usd_per_verified_correct_answer": None,
        }
        return res[metric] if metric is not None else res

    rng = np.random.default_rng(seed)

    correct_flags = np.array([1.0 if r.get("answer_correctness") else 0.0 for r in rec_list])
    vc_flags = np.array([1.0 if is_verified_correct(r, cond) else 0.0 for r in rec_list])
    costs = [calculate_cost_per_question(r, pricing_entry) for r in rec_list]
    has_costs = all(c is not None for c in costs)
    cost_arr = np.array([c if c is not None else 0.0 for c in costs])

    corr_samples = []
    vc_samples = []
    cost_vc_samples = []

    for _ in range(n_resamples):
        idx = rng.choice(n, size=n, replace=True)
        corr_samples.append(np.mean(correct_flags[idx]))
        vc_mean = np.mean(vc_flags[idx])
        vc_samples.append(vc_mean)

        if has_costs:
            sum_vc = np.sum(vc_flags[idx])
            if sum_vc > 0:
                cost_vc_samples.append(np.sum(cost_arr[idx]) / sum_vc)
            else:
                cost_vc_samples.append(float("inf"))

    corr_ci = (float(np.percentile(corr_samples, 2.5)), float(np.percentile(corr_samples, 97.5)))
    vc_ci = (float(np.percentile(vc_samples, 2.5)), float(np.percentile(vc_samples, 97.5)))

    cost_vc_ci = None
    if has_costs:
        valid_cost_samples = [c for c in cost_vc_samples if not math.isinf(c)]
        if not valid_cost_samples:
            cost_vc_ci = "∞ (no correct answers)"
        else:
            low = float(np.percentile(valid_cost_samples, 2.5))
            high = float(np.percentile(valid_cost_samples, 97.5))
            cost_vc_ci = (low, high)

    res = {
        "answer_correctness": corr_ci,
        "verified_correct": vc_ci,
        "usd_per_verified_correct_answer": cost_vc_ci,
    }
    return res[metric] if metric is not None else res


def mcnemar_exact(b: int, c: int) -> dict[str, Any]:
    """Exact McNemar test on discordant pairs (b, c) using exact binomial test.
    
    b: Condition 1 succeeds and Condition 2 fails
    c: Condition 1 fails and Condition 2 succeeds
    """
    total = b + c
    if total == 0:
        return {"b": b, "c": c, "p_value": 1.0}
    res = scipy.stats.binomtest(b, total, 0.5)
    return {"b": b, "c": c, "p_value": float(res.pvalue)}


def paired_mcnemar_comparison(
    results_1: dict | list[dict],
    results_2: dict | list[dict],
    metric: str = "verified_correct",
) -> dict[str, Any]:
    """Perform paired McNemar test between two evaluation runs on common questions.
    
    For multiple runs, takes each question's majority outcome.
    """
    def extract_question_outcomes(data: dict | list[dict]) -> dict[str, int]:
        outcomes = {}
        if isinstance(data, dict):
            cond = data.get("condition")
            det = data.get("detailed_results", [])
            if det and isinstance(det[0], list):
                # Multiple runs
                q_successes = {}
                q_counts = {}
                for run_recs in det:
                    for r in run_recs:
                        qid = r["id"]
                        success = (
                            is_verified_correct(r, cond)
                            if metric == "verified_correct"
                            else bool(r.get("answer_correctness"))
                        )
                        q_successes[qid] = q_successes.get(qid, 0) + (1 if success else 0)
                        q_counts[qid] = q_counts.get(qid, 0) + 1
                for qid, count in q_counts.items():
                    outcomes[qid] = 1 if (q_successes[qid] / count >= 0.5) else 0
            else:
                recs = det[0] if det else []
                for r in recs:
                    qid = r["id"]
                    success = (
                        is_verified_correct(r, cond)
                        if metric == "verified_correct"
                        else bool(r.get("answer_correctness"))
                    )
                    outcomes[qid] = 1 if success else 0
        elif isinstance(data, list):
            for r in data:
                qid = r["id"]
                success = (
                    is_verified_correct(r)
                    if metric == "verified_correct"
                    else bool(r.get("answer_correctness"))
                )
                outcomes[qid] = 1 if success else 0
        return outcomes

    o1 = extract_question_outcomes(results_1)
    o2 = extract_question_outcomes(results_2)

    common_ids = sorted(set(o1.keys()) & set(o2.keys()))
    b = sum(1 for qid in common_ids if o1[qid] == 1 and o2[qid] == 0)
    c = sum(1 for qid in common_ids if o1[qid] == 0 and o2[qid] == 1)

    result = mcnemar_exact(b, c)
    result["questions_compared"] = len(common_ids)
    return result


def calculate_breakeven_volume(
    usd_per_gpu_hour: float,
    gpus: int = 1,
    hours_on_per_month: float = 730.0,
    usd_per_question_per_token: float = 0.05,
) -> float:
    """Calculate break-even monthly question volume Q* for dedicated GPU vs per-token.
    
    Q* = usd_per_gpu_hour * gpus * hours_on_per_month / usd_per_question_per_token.
    """
    if usd_per_question_per_token <= 0:
        return float("inf")
    return float(usd_per_gpu_hour) * float(gpus) * float(hours_on_per_month) / float(usd_per_question_per_token)


def measure_fixed_prompt_overhead(client=None, model: str | None = None) -> int:
    """Send one minimal request to measure fixed prompt tokens with provider tokenizer."""
    from dora.agent import FULL_SYSTEM_PROMPT, TOOL_SCHEMAS, default_client
    c = client or default_client()
    m = model or "default"
    resp = c.chat.completions.create(
        model=m,
        messages=[
            {"role": "system", "content": FULL_SYSTEM_PROMPT},
            {"role": "user", "content": "Hola"},
        ],
        tools=TOOL_SCHEMAS,
        max_tokens=1,
    )
    usage = getattr(resp, "usage", None)
    if isinstance(usage, dict):
        return usage.get("prompt_tokens", 0) or 0
    return getattr(usage, "prompt_tokens", 0) or 0


def calculate_overhead_share(
    fixed_overhead: int,
    avg_requests_per_question: float,
    avg_prompt_tokens_per_question: float,
) -> float:
    """Calculate the share of input tokens that corresponds to the fixed prompt overhead."""
    if avg_prompt_tokens_per_question <= 0:
        return 0.0
    return (float(fixed_overhead) * float(avg_requests_per_question)) / float(avg_prompt_tokens_per_question)


def compute_run_economics(results_data: dict, pricing_entry: dict | None = None) -> dict[str, Any]:
    """Compute complete economic metrics for an evaluation results dictionary."""
    model = results_data.get("model", "unknown")
    provider = results_data.get("provider")
    condition = results_data.get("condition", "with_verifier")

    det = results_data.get("detailed_results", [])
    if det and isinstance(det[0], list):
        # Flatten all runs into single list of question records
        records = [r for run_recs in det for r in run_recs]
        # For question-level bootstrap, we group by question ID
        q_map: dict[str, list[dict]] = {}
        for idx, r in enumerate(records):
            qid = r.get("id", f"q_{idx}")
            q_map.setdefault(qid, []).append(r)
        # Unique question representatives with averaged metrics
        unique_records = []
        for qid, q_recs in q_map.items():
            rep = dict(q_recs[0])
            rep["prompt_tokens"] = sum(r.get("prompt_tokens", 0) for r in q_recs) / len(q_recs)
            rep["completion_tokens"] = sum(r.get("completion_tokens", 0) for r in q_recs) / len(q_recs)
            if any("cached_prompt_tokens" in r for r in q_recs):
                rep["cached_prompt_tokens"] = sum(r.get("cached_prompt_tokens", 0) for r in q_recs) / len(q_recs)
            rep["latency_s"] = sum(r.get("latency_s", 0.0) for r in q_recs) / len(q_recs)
            rep["requests"] = sum(r.get("requests", 0) for r in q_recs) / len(q_recs)
            corr_rate = sum(1 for r in q_recs if r.get("answer_correctness")) / len(q_recs)
            vc_rate = sum(1 for r in q_recs if is_verified_correct(r, condition)) / len(q_recs)
            rep["answer_correctness"] = corr_rate >= 0.5
            rep["verified"] = vc_rate >= 0.5
            unique_records.append(rep)
    elif det:
        records = det
        unique_records = det
    else:
        records = []
        unique_records = []

    n_q = len(unique_records)
    latencies = [float(r.get("latency_s", 0.0)) for r in records if r.get("latency_s") is not None]
    lat_p50 = float(np.percentile(latencies, 50)) if latencies else None
    lat_p95 = float(np.percentile(latencies, 95)) if latencies else None

    # Calculate question costs
    costs = [calculate_cost_per_question(r, pricing_entry) for r in unique_records]
    has_costs = (n_q > 0) and all(c is not None for c in costs)

    total_cost = sum(costs) if has_costs else None

    # Counts
    correct_count = sum(1 for r in unique_records if r.get("answer_correctness"))
    vc_count = sum(1 for r in unique_records if is_verified_correct(r, condition))

    corr_rate = correct_count / n_q if n_q > 0 else 0.0
    vc_rate = vc_count / n_q if n_q > 0 else 0.0

    # Headline metrics
    if not has_costs:
        usd_per_question = "price unknown"
        usd_per_corr = "price unknown"
        usd_per_vc = "price unknown"
    else:
        usd_per_question = (total_cost / n_q) if n_q > 0 else 0.0
        usd_per_corr = (total_cost / correct_count) if correct_count > 0 else "∞ (no correct answers)"
        usd_per_vc = (total_cost / vc_count) if vc_count > 0 else "∞ (no correct answers)"

    # Bootstrap intervals
    ci = bootstrap_ci(unique_records, pricing_entry, condition=condition)

    billing = pricing_entry.get("billing") if pricing_entry else None
    label_note = ""
    if billing == "dedicated":
        label_note = "upper bound, one request at a time"

    avg_p_tok = float(np.mean([r.get("prompt_tokens", 0) for r in unique_records])) if unique_records else 0.0
    avg_c_tok = float(np.mean([r.get("completion_tokens", 0) for r in unique_records])) if unique_records else 0.0
    avg_req = float(np.mean([r.get("requests", 0) for r in unique_records])) if unique_records else 0.0

    return {
        "model": model,
        "provider": provider,
        "condition": condition,
        "questions_count": n_q,
        "has_pricing": has_costs,
        "billing": billing,
        "prices_read_on": pricing_entry.get("read_on") if pricing_entry else None,
        "pricing_source": pricing_entry.get("source") if pricing_entry else None,
        "usd_per_question": usd_per_question,
        "usd_per_question_label": label_note,
        "total_cost_usd": total_cost,
        "correct_answers_count": correct_count,
        "verified_correct_count": vc_count,
        "answer_correctness_rate": corr_rate,
        "answer_correctness_ci": ci["answer_correctness"],
        "verified_correct_rate": vc_rate,
        "verified_correct_ci": ci["verified_correct"],
        "usd_per_correct_answer": usd_per_corr,
        "usd_per_verified_correct_answer": usd_per_vc,
        "usd_per_verified_correct_ci": ci["usd_per_verified_correct_answer"],
        "usd_per_verified_correct_answer_ci": ci["usd_per_verified_correct_answer"],
        "latency_p50_s": lat_p50,
        "latency_p95_s": lat_p95,
        "avg_prompt_tokens": avg_p_tok,
        "prompt_tokens_mean": avg_p_tok,
        "avg_completion_tokens": avg_c_tok,
        "completion_tokens_mean": avg_c_tok,
        "avg_requests": avg_req,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate economics of model answers")
    parser.add_argument("results", nargs="+", help="One or more evaluation result JSON files")
    parser.add_argument("--pricing", type=str, default=str(DEFAULT_PRICING_PATH), help="Path to pricing.json")
    args = parser.parse_args()

    pricing = load_pricing(args.pricing)

    for rf in args.results:
        p = Path(rf)
        if not p.is_file():
            print(f"File not found: {rf}")
            continue
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        pe = get_pricing_entry(pricing, data.get("model", ""), data.get("provider"))
        econ = compute_run_economics(data, pe)

        print("=" * 60)
        print(f"Model: {econ['model']} @ {econ['provider']} | Condition: {econ['condition']}")
        print(f"Questions: {econ['questions_count']}")
        print(f"Verified correct: {econ['verified_correct_rate']:.1%} (95% CI: [{econ['verified_correct_ci'][0]:.1%}, {econ['verified_correct_ci'][1]:.1%}])")

        if econ["has_pricing"]:
            print(f"USD / question: ${econ['usd_per_question']:.6f} {('(' + econ['usd_per_question_label'] + ')') if econ['usd_per_question_label'] else ''}")
            if isinstance(econ["usd_per_verified_correct_answer"], (int, float)):
                ci_str = ""
                if isinstance(econ["usd_per_verified_correct_ci"], tuple):
                    ci_str = f" (95% CI: [${econ['usd_per_verified_correct_ci'][0]:.4f}, ${econ['usd_per_verified_correct_ci'][1]:.4f}])"
                print(f"USD / verified correct answer: ${econ['usd_per_verified_correct_answer']:.4f}{ci_str}")
            else:
                print(f"USD / verified correct answer: {econ['usd_per_verified_correct_answer']}")
        else:
            print("Pricing: price unknown (prices not filled in)")

        if econ["latency_p50_s"] is not None:
            print(f"Latency: p50 = {econ['latency_p50_s']:.2f}s, p95 = {econ['latency_p95_s']:.2f}s")
        print("=" * 60)


if __name__ == "__main__":
    main()
