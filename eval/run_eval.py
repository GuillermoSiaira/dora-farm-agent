"""Run evaluation harness over eval/questions.jsonl and write results to eval/results/.

Conditions of E1 (docs/plan-de-pruebas.md): --baseline is the model alone (A), --no-verifier is DORA
without the verifier (B), and the default is DORA complete (C)."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from urllib.parse import urlparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import unicodedata
from dora.agent import Agent, default_client
from dora.verifier import _PATTERN, _SCALES, _readings, _tolerance, verify, SEASON_SOLVING_TOOLS
from eval.baseline import ask_baseline
from eval.build_answers import IOWA_SUPPORTED, extract_field
from eval.plan_check import evaluate_plan

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
            # "19,5%" matches a share (0.195) and a percentage field (19.5): the verifier accepts both.
            candidates = [(val / 100.0, _tolerance(val, decimals) / 100.0), (val, _tolerance(val, decimals))] if pct \
                else [(val, _tolerance(val, decimals))]
            if any(abs(c - target) <= tol + 1e-6 for c, tol in candidates):
                return True
    return False


def _read_jsonl(paths) -> list[dict]:
    """Lines of one or several JSONL files, in order."""
    if isinstance(paths, (str, Path)):
        paths = [paths]
    items = []
    for p in paths:
        p = Path(p)
        if not p.is_file():
            continue
        with open(p, encoding="utf-8") as f:
            items += [json.loads(line) for line in f if line.strip()]
    return items


def _has_plan(q: dict) -> bool:
    """A single farm whose plan the engine can evaluate (not a refusal, not a comparison of regions)."""
    check = q.get("check") or {}
    return q.get("expect") != "refuse" and check.get("tool") != "compare_regions" and not q.get("e5")


def _number(v) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.replace(",", ""))
        except ValueError:
            return None
    return None


REGION_SYNONYMS = {
    "pampas_core": ["pergamino", "pampas core", "zona núcleo", "zona nucleo", "núcleo", "nucleo"],
    "southeast_buenos_aires": ["sudeste", "southeast", "balcarce"],
    "iowa": ["iowa"],
    "mato_grosso": ["mato grosso"],
}

VERDICT_WORDS = [
    "conviene", "gana", "mejor", "rinde más", "rinde mas", "queda primero",
    "better", "best", "wins", "ahead",
]

_LEADING_CLAUSE_RE = re.compile(
    r"^\s*(?:entre\s+[^,]+,|between\s+[^,]+,|comparando\s+[^,]+,|comparing\s+[^,]+,)",
    re.IGNORECASE,
)


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _normalize(s: str) -> str:
    return _strip_accents(s.lower())


def decision_named(reply: str, expected: str, regions: list[str]) -> bool:
    if not reply or not expected:
        return False
    pieces = re.split(r"[\n.!:]+", reply)
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        cleaned = _LEADING_CLAUSE_RE.sub("", piece).strip()
        norm_cleaned = _normalize(cleaned)

        has_verdict = any(_normalize(vw) in norm_cleaned for vw in VERDICT_WORDS)
        if not has_verdict:
            continue

        region_positions = []
        for r in regions:
            syns = REGION_SYNONYMS.get(r, [r])
            first_pos = None
            for syn in syns:
                norm_syn = _normalize(syn)
                m = re.search(r"\b" + re.escape(norm_syn) + r"\b", norm_cleaned)
                if m:
                    pos = m.start()
                    if first_pos is None or pos < first_pos:
                        first_pos = pos
            if first_pos is not None:
                region_positions.append((first_pos, r))

        if not region_positions:
            continue

        region_positions.sort(key=lambda x: x[0])
        first_region = region_positions[0][1]
        return first_region == expected

    return False


def _agent_plan_and_value(q: dict, calls: list[dict], results: list[str]) -> tuple[dict | None, Any, bool]:
    """From the agent's tool results: the hectares of its last solved season matching the scenario,
    and the asked field as the last call of the checked tool returned it.
    Returns: (hectares, value, plan_scenario_mismatch)."""
    hectares = None
    value = None
    seasons_solved = False
    scenario_matched = False
    check = q.get("check") or {}
    q_sc = q.get("scenario") or {}

    for call, raw in zip(calls, results):
        if call.get("rejected"):
            continue
        try:
            res = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(res, dict) or "error" in res:
            continue

        tool_name = call.get("tool")
        arg_str = call.get("arguments", "{}")
        try:
            args = json.loads(arg_str) if isinstance(arg_str, str) else (arg_str or {})
        except json.JSONDecodeError:
            args = {}
        call_sc = args.get("scenario", {}) if isinstance(args.get("scenario"), dict) else args

        if tool_name in SEASON_SOLVING_TOOLS:
            seasons_solved = True

        call_matched = False
        if tool_name == "evaluate_season":
            if match_scenario(call_sc, q_sc):
                call_matched = True
                scenario_matched = True
                if isinstance(res.get("hectares"), dict):
                    hectares = res["hectares"]
        elif tool_name == "sensitivity":
            param = args.get("parameter")
            q_param_val = q_sc.get(param)
            for row in res.get("results", []):
                row_val = row.get(param)
                row_sc = {**call_sc, param: row_val}
                if row_val == q_param_val and match_scenario(row_sc, q_sc):
                    call_matched = True
                    scenario_matched = True
                    if isinstance(row.get("hectares"), dict):
                        hectares = row["hectares"]
                    break
        elif tool_name == "compare_regions":
            expected_sc = {k: v for k, v in q_sc.items() if k != "region"}
            if match_scenario(call_sc, expected_sc):
                call_matched = True
                scenario_matched = True
        elif tool_name == "shadow_prices":
            if match_scenario(call_sc, q_sc):
                call_matched = True
                scenario_matched = True

        if check and tool_name == check.get("tool") and call_matched:
            try:
                value = extract_field(res, check["field"])
            except KeyError:
                pass

    plan_scenario_mismatch = bool(seasons_solved and not scenario_matched)
    return hectares, value, plan_scenario_mismatch


def _refused(text: str) -> bool:
    return any(m in text.lower() for m in REFUSE_MARKERS)


REFUSE_MARKERS = [
    "no soporta", "arroz", "inválido", "negativ", "superficie", "falta", "aclarar", "cuántas ha",
    "cuántas hectáreas", "necesito", "no puedo", "no se puede", "error",
    "not valid", "isn't valid", "invalid", "not supported", "missing", "clarify",
    "how many", "can't", "cannot", "isn't possible", "not possible", "has to be"
]


def _fold(text: str) -> str:
    """Lowercase without accents, so the E5 rules are written once ("rotacion" matches "rotación")."""
    return "".join(ch for ch in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(ch) != "Mn")


def e5_check(text: str, rule: dict, unsupported_final: list[str]) -> dict:
    """E5 (robustness): does the reply pass the question's rule?

    pass_if_any is a list of alternatives, each a list of regexes that must all match the folded text;
    one matching alternative is enough. Any match of fail_if_any fails. require_verified also asks that
    the reply shown to the farmer have no number without support (eval/questions_e5.jsonl)."""
    folded = _fold(text)
    matched = next((i for i, alt in enumerate(rule.get("pass_if_any", []))
                    if all(re.search(rx, folded) for rx in alt)), None)
    failed_by = next((rx for rx in rule.get("fail_if_any", []) if re.search(rx, folded)), None)
    verified_ok = not (rule.get("require_verified") and unsupported_final)
    return {"pass": matched is not None and failed_by is None and verified_ok,
            "matched_alternative": matched, "failed_by": failed_by, "verified_ok": verified_ok}


def rescore_e5(results_path: Path | str, questions_path: Path | str) -> dict:
    """Apply the current E5 rules to a saved results file, without calling the model again.

    The verdict given at run time stays in each record as "e5_at_run"; answer_correctness, "e5" and
    the counts are rewritten, and the file records the commit that rescored it."""
    path = Path(results_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    rules = {q["id"]: q["e5"] for q in _read_jsonl(questions_path) if q.get("e5")}
    for run, metric in zip(data["detailed_results"], data["run_metrics"]):
        for rec in run:
            if rec["id"] not in rules:
                continue
            rec.setdefault("e5_at_run", rec.get("e5"))
            rec["e5"] = e5_check(rec["reply"], rules[rec["id"]], rec.get("unsupported") or [])
            rec["answer_correctness"] = rec["e5"]["pass"]
        metric["answer_correctness"] = _rate(run, "answer_correctness")
    vals = [m["answer_correctness"] for m in data["run_metrics"] if m["answer_correctness"] is not None]
    data["aggregated"]["answer_correctness"] = {"mean": sum(vals) / len(vals) if vals else None,
                                                "min": min(vals, default=None), "max": max(vals, default=None)}
    for i, qid in enumerate(data["question_ids"]):
        data["per_question"][qid]["correct_runs"] = sum(1 for run in data["detailed_results"] if run[i]["answer_correctness"])
    data["rescored_with_commit"] = _commit()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return data


def _spread(values: list[float]) -> dict:
    """Mean, sample standard deviation and coefficient of variation of the repeated numbers."""
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": None, "std": None, "cv": None, "distinct": 0}
    mean = sum(values) / n
    std = (sum((v - mean) ** 2 for v in values) / (n - 1)) ** 0.5 if n > 1 else 0.0
    return {"n": n, "mean": mean, "std": std, "cv": std / abs(mean) if abs(mean) > 1e-9 else None,
            "distinct": len({round(v, 6) for v in values})}


def _rate(records: list[dict], key: str) -> float | None:
    vals = [r[key] for r in records if r.get(key) is not None]
    return sum(1 for v in vals if v) / len(vals) if vals else None


def _mean(records: list[dict], key: str) -> float | None:
    vals = [r[key] for r in records if r.get(key) is not None]
    return sum(vals) / len(vals) if vals else None


def run_evaluation(
    client=None,
    model: str = "default",
    runs: int = 1,
    use_verifier: bool = True,
    limit: int | None = None,
    questions_path: Path | str | list = DEFAULT_QUESTIONS_PATH,
    answers_path: Path | str | list = DEFAULT_ANSWERS_PATH,
    output_path: Path | str | None = None,
    baseline: bool = False,
    ids: list[str] | None = None,
    provider: str | None = None,
    concurrency: int = 1,
) -> dict:
    """Run the evaluation suite over the questions.

    baseline=True is condition A of E1: the model alone, with the engine's data in text and no tools
    (eval/baseline.py). Otherwise the DORA agent answers, with or without the verifier (B and C).
    In every condition the plan's hectares are evaluated in the engine (eval/plan_check.py)."""
    questions = _read_jsonl(questions_path)
    active_questions = [q for q in questions if IOWA_SUPPORTED or q.get("region") != "iowa"]
    if ids:
        active_questions = [q for q in active_questions if q["id"] in set(ids)]
    if limit is not None and limit > 0:
        active_questions = active_questions[:limit]

    answers_map: dict[str, Any] = {a["id"]: a["expected_value"] for a in _read_jsonl(answers_path)}
    if baseline and client is None:
        client = default_client()

    run_metrics = []
    detailed_results = []

    for run_idx in range(runs):
        if concurrency > 1:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                if baseline:
                    q_results = list(executor.map(lambda q: _baseline_record(client, model, q, answers_map), active_questions))
                else:
                    q_results = list(executor.map(lambda q: _agent_record(client, model, use_verifier, q, answers_map), active_questions))
        else:
            q_results = []
            for q in active_questions:
                if baseline:
                    rec = _baseline_record(client, model, q, answers_map)
                else:
                    rec = _agent_record(client, model, use_verifier, q, answers_map)
                q_results.append(rec)

        n_q = len(q_results)
        tokens_in = [r["prompt_tokens"] for r in q_results]
        tokens_out = [r["completion_tokens"] for r in q_results]
        run_metric = {
            "run_index": run_idx,
            "tool_accuracy": _rate(q_results, "tool_accuracy"),
            "answer_correctness": _rate(q_results, "answer_correctness"),
            "formulation_accuracy": _rate(q_results, "formulation_accuracy"),
            "unsupported_numbers_rate": _rate(q_results, "has_unsupported_before_correction"),
            "verified_rate": _rate(q_results, "verified"),
            "calls_per_question": _mean(q_results, "tool_calls_count"),
            "prompt_tokens_per_question": sum(tokens_in) / n_q if n_q else 0.0,
            "completion_tokens_per_question": sum(tokens_out) / n_q if n_q else 0.0,
            "plan_given_rate": _rate(q_results, "plan_given"),
            "feasible_rate": _rate([r for r in q_results if r.get("plan_given")], "plan_feasible"),
            "gap_pct_mean": _mean(q_results, "plan_gap_pct"),
            "questions_count": n_q,
        }
        if not baseline and run_metric["formulation_accuracy"] is None:
            run_metric["formulation_accuracy"] = 1.0
        run_metrics.append(run_metric)
        detailed_results.append(q_results)

    # Aggregated metrics over all runs
    def agg(key: str) -> dict[str, float | None]:
        vals = [r[key] for r in run_metrics if r[key] is not None]
        return {
            "mean": sum(vals) / len(vals) if vals else None,
            "min": min(vals) if vals else None,
            "max": max(vals) if vals else None,
        }

    aggregated = {k: agg(k) for k in (
        "tool_accuracy", "answer_correctness", "formulation_accuracy", "unsupported_numbers_rate", "verified_rate",
        "calls_per_question", "prompt_tokens_per_question", "completion_tokens_per_question",
        "plan_given_rate", "feasible_rate", "gap_pct_mean")}

    # Dispersion: the same question asked `runs` times; how much the reported number and the plan move.
    per_question = {}
    for i, q in enumerate(active_questions):
        recs = [detailed_results[r][i] for r in range(runs)]
        reported = [v for v in (_number(r["reported_value"]) for r in recs) if v is not None]
        npvs = [r["plan_npv_usd"] for r in recs if r.get("plan_npv_usd") is not None]
        per_question[q["id"]] = {
            "expected_value": answers_map.get(q["id"]),
            "correct_runs": sum(1 for r in recs if r["answer_correctness"]),
            "reported_value": _spread(reported),
            "reported_values": [r["reported_value"] for r in recs],
            "plan_npv_usd": _spread(npvs),
            "feasible_runs": sum(1 for r in recs if r.get("plan_feasible")),
            "plan_runs": sum(1 for r in recs if r.get("plan_feasible") is not None),
            "no_plan_runs": sum(1 for r in recs if r.get("plan_given") is False),
        }
    cvs = [p["reported_value"]["cv"] for p in per_question.values() if p["reported_value"]["cv"] is not None]
    aggregated["reported_value_cv_mean"] = sum(cvs) / len(cvs) if cvs else None
    aggregated["questions_with_one_value"] = sum(1 for p in per_question.values() if p["reported_value"]["distinct"] == 1)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    model_slug = re.sub(r"[^\w\-]", "_", model)
    condition = "baseline" if baseline else ("with_verifier" if use_verifier else "no_verifier")

    base_url = str(getattr(client, "base_url", "")) if client is not None else os.environ.get("DORA_API_BASE", "")
    api_host = None
    if base_url:
        parsed = urlparse(base_url)
        api_host = parsed.hostname or parsed.netloc or str(base_url)

    results_data = {
        "model": model,
        "provider": provider,
        "api_host": api_host,
        "condition": condition,
        "commit": _commit(),
        "use_verifier": use_verifier and not baseline,
        "runs": runs,
        "timestamp": timestamp,
        "question_ids": [q["id"] for q in active_questions],
        "run_metrics": run_metrics,
        "aggregated": aggregated,
        "per_question": per_question,
        "detailed_results": detailed_results,
    }

    if output_path is None:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        output_file = RESULTS_DIR / f"{model_slug}_{condition}_{timestamp}.json"
    else:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=2, ensure_ascii=False)

    return results_data


def _plan_fields(q: dict, hectares: dict | None) -> dict:
    """The engine's verdict on the plan, for a single-farm question; None fields when there is no plan."""
    out = {"plan_hectares": hectares, "plan_given": None, "plan_feasible": None, "plan_violations": None,
           "plan_npv_usd": None, "plan_gap_usd": None, "plan_gap_pct": None, "npv_optimal_usd": None}
    if not _has_plan(q):
        return out
    if hectares is None:
        out["plan_given"] = False
        return out
    ev = evaluate_plan(q["scenario"], hectares)
    out.update({"plan_given": True, "plan_feasible": ev["feasible"], "plan_violations": ev["violations"],
                "plan_npv_usd": ev["npv_plan_usd"], "plan_gap_usd": ev["gap_usd"], "plan_gap_pct": ev["gap_pct"],
                "npv_optimal_usd": ev["npv_optimal_usd"]})
    return out


def _baseline_record(client, model: str, q: dict, answers_map: dict) -> dict:
    """Condition A: one question, the model alone."""
    if (q.get("check") or {}).get("tool") == "compare_regions":
        # compare_regions builds each region's scenario (rent, taxes, routes) inside the tool;
        # describing it here would copy that code, so these questions stay out of condition A.
        return {"id": q["id"], "text": q["text"], "skipped": "compare_regions", "reply": "", "reported_value": None,
                "answer_correctness": None, "has_unsupported_before_correction": None,
                "requests": 0, "prompt_tokens": 0, "completion_tokens": 0, "latency_s": 0.0,
                **_plan_fields(q, None)}
    t0 = time.perf_counter()
    a = ask_baseline(client, model, q)
    latency_s = time.perf_counter() - t0
    text = a["text"]
    if q.get("expect") == "refuse":
        no_plan = not bool(a.get("hectares"))
        contains_refusal = "?" in text or any(m in text.lower() for m in REFUSE_MARKERS)
        hit = bool(no_plan and contains_refusal)
    elif (q.get("check") or {}).get("kind") == "decision":
        expected = answers_map.get(q["id"])
        regions = q.get("check", {}).get("payload", {}).get("regions", ["pampas_core", "iowa"])
        hit = decision_named(text, expected, regions)
    elif q["id"] in answers_map:
        hit = text_contains_expected_value(text, answers_map[q["id"]])
    else:
        hit = False
    # Numbers without support: every number in the answer must be in the data given or the question.
    unsupported = verify(text, [a["prompt"]], [q["text"]])
    rec = {
        "id": q["id"],
        "text": q["text"],
        "reply": text,
        "raw": a["raw"],
        "parse_error": a["parse_error"],
        "reported_value": a["answer_value"],
        "expected_npv_usd": a["expected_npv_usd"],
        "sales": a.get("sales"),
        "answer_correctness": hit,
        "has_unsupported_before_correction": len(unsupported) > 0,
        "unsupported": [u.text for u in unsupported],
        "requests": a["usage"].get("requests", 1),
        "prompt_tokens": a["usage"]["prompt_tokens"],
        "completion_tokens": a["usage"]["completion_tokens"],
        "latency_s": round(latency_s, 4),
        **_plan_fields(q, a["hectares"]),
    }
    if "cached_prompt_tokens" in a["usage"]:
        rec["cached_prompt_tokens"] = a["usage"]["cached_prompt_tokens"]
    return rec


def _agent_record(client, model: str, use_verifier: bool, q: dict, answers_map: dict) -> dict:
    """Conditions B and C: one question, the DORA agent with tools."""
    agent = Agent(client=client, model=model, use_verifier=use_verifier)
    t0 = time.perf_counter()
    reply = agent.ask(q["text"])
    latency_s = time.perf_counter() - t0
    calls = reply.tool_calls

    # 1. Formulation accuracy
    is_formulation = q.get("type") == "formulation"
    formulation_hit = False
    if is_formulation:
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
                expected_sc = q["scenario"]
                if c.get("tool") == "compare_regions":      # regions go in their own argument
                    expected_sc = {k: v for k, v in expected_sc.items() if k != "region"}
                if match_scenario(sc, expected_sc):
                    tool_hit = True
                    break

    # 3. Answer correctness
    answer_hit = False
    if q.get("expect") == "refuse":
        has_season_solved = any(
            c.get("tool") in SEASON_SOLVING_TOOLS and not c.get("rejected") and not c.get("error")
            for c in calls
        )
        no_plan = not has_season_solved
        contains_refusal = "?" in reply.text or any(m in reply.text.lower() for m in REFUSE_MARKERS)
        answer_hit = bool(no_plan and contains_refusal)
    elif (q.get("check") or {}).get("kind") == "decision":
        expected = answers_map.get(q["id"])
        regions = q.get("check", {}).get("payload", {}).get("regions", ["pampas_core", "iowa"])
        answer_hit = decision_named(reply.text, expected, regions)
    elif q["id"] in answers_map:
        answer_hit = text_contains_expected_value(reply.text, answers_map[q["id"]])
    e5 = e5_check(reply.text, q["e5"], [u.text for u in reply.unsupported]) if q.get("e5") else None
    if e5:
        answer_hit = e5["pass"]

    hectares, value, plan_scenario_mismatch = _agent_plan_and_value(q, calls, agent.tool_results)
    rec = {
        "id": q["id"],
        "text": q["text"],
        "reply": reply.text,
        "verified": reply.verified,
        "tool_calls": calls,
        "tool_calls_count": len(calls),
        "tool_accuracy": tool_hit,
        "answer_correctness": answer_hit,
        "formulation_accuracy": formulation_hit if is_formulation else None,
        "has_unsupported_before_correction": len(reply.initial_unsupported) > 0,
        "reported_value": value,
        "requests": reply.usage.get("requests", 0),
        "prompt_tokens": reply.usage.get("prompt_tokens", 0),
        "completion_tokens": reply.usage.get("completion_tokens", 0),
        "latency_s": round(latency_s, 4),
        "scenario_rejections": [
            {"parameter": p.parameter, "value": p.value, "reason": p.reason}
            for p in reply.scenario_rejections
        ],
        "style_problems": reply.style_problems,
        **_plan_fields(q, hectares),
    }
    if e5:
        rec["e5"] = e5
        rec["unsupported_initial"] = [u.text for u in reply.initial_unsupported]
        rec["unsupported"] = [u.text for u in reply.unsupported]
    if plan_scenario_mismatch:
        rec["plan_scenario_mismatch"] = True
    if "cached_prompt_tokens" in reply.usage:
        rec["cached_prompt_tokens"] = reply.usage["cached_prompt_tokens"]
    return rec


def _commit() -> str | None:
    """The code the run used: commit hash, marked dirty when the working tree has uncommitted changes."""
    import subprocess
    try:
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=PROJECT_ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return head + ("-dirty" if dirty else "")


def _load_dotenv(path: Path) -> None:
    """KEY=value lines of .env into the environment, without overriding what is already set."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


# Providers with their own keys in .env: --provider X points DORA_API_BASE / DORA_API_KEY / DORA_MODEL at them.
# (variable for the base URL, for the key, for the model, default base URL, default model)
# Baseten: the hackathon key only opens muse-spark-open-1026 ("[HACKATHON] Muse Spark Open", same weights
# Muse-Spark-Open-816B-A42B-NVFP4 as meta-models/muse-spark-open, which answers 403 with it).
PROVIDERS = {
    "baseten": ("BASETEN_API_BASE", "BASETEN_API_KEY", "BASETEN_MODEL",
                "https://inference.baseten.co/v1", "meta-models/muse-spark-open-1026"),
    "modal": ("MODAL_API_BASE", "MODAL_API_KEY", "MODAL_MODEL", None, None),
}


def _use_provider(provider: str | None) -> None:
    """Point the DORA_* variables at the provider's own ones, so the agent and the baseline use them."""
    if provider not in PROVIDERS:
        return
    base_var, key_var, model_var, base_default, model_default = PROVIDERS[provider]
    base = os.environ.get(base_var, base_default)
    key = os.environ.get(key_var)
    if not base or not key:
        sys.exit(f"--provider {provider} needs {key_var} (and {base_var}) in .env")
    os.environ["DORA_API_BASE"] = base
    os.environ["DORA_API_KEY"] = key
    model = os.environ.get(model_var, model_default)
    if model:
        os.environ["DORA_MODEL"] = model


def main():
    _load_dotenv(PROJECT_ROOT / ".env")
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--provider", type=str, default=None)
    _use_provider(pre.parse_known_args()[0].provider)
    parser = argparse.ArgumentParser(description="Run DORA evaluation harness")
    parser.add_argument("--model", type=str, default=os.environ.get("DORA_MODEL", "default"), help="Model name")
    parser.add_argument("--runs", type=int, default=5, help="Number of runs (default: 5)")
    parser.add_argument("--no-verifier", action="store_true", help="Disable verifier correction rounds")
    parser.add_argument("--baseline", action="store_true",
                        help="Condition A of E1: the model alone, with the engine's data in text and no tools")
    parser.add_argument("--ids", type=str, default=None, help="Comma-separated question ids to run (e.g. q04,q08)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of questions to evaluate")
    parser.add_argument("--questions", type=str, nargs="+", default=[str(DEFAULT_QUESTIONS_PATH)],
                        help="One or more questions .jsonl files")
    parser.add_argument("--answers", type=str, nargs="+", default=[str(DEFAULT_ANSWERS_PATH)],
                        help="One or more answers .jsonl files")
    parser.add_argument("--output", type=str, default=None, help="Output path for results JSON")
    parser.add_argument("--provider", type=str, default=None, help="Provider name (e.g. meta, baseten, modal)")
    parser.add_argument("--concurrency", type=int, default=1, help="Concurrent workers (default: 1)")
    parser.add_argument("--rescore", type=str, nargs="+", default=None,
                        help="E5: apply the rules in --questions to these saved results files, without calling the model")

    args = parser.parse_args()
    if args.rescore:
        for f in args.rescore:
            d = rescore_e5(f, args.questions[0])
            print(f"{f}: answer correctness {d['aggregated']['answer_correctness']['mean']:.1%}")
        return

    res = run_evaluation(
        model=args.model,
        runs=args.runs,
        use_verifier=not args.no_verifier,
        limit=args.limit,
        questions_path=args.questions,
        answers_path=args.answers,
        output_path=args.output,
        baseline=args.baseline,
        ids=[i.strip() for i in args.ids.split(",")] if args.ids else None,
        provider=args.provider,
        concurrency=args.concurrency,
    )
    agg = res["aggregated"]

    def pct(key):
        v = agg[key]["mean"]
        return "n/a" if v is None else f"{v:.1%}"

    print(f"Evaluation complete. Condition: {res['condition']}, runs: {args.runs}, questions: {len(res['question_ids'])}")
    print(f"Answer Correctness: {pct('answer_correctness')}")
    print(f"Tool Accuracy: {pct('tool_accuracy')}  Verified Rate: {pct('verified_rate')}")
    print(f"Feasible plans: {pct('feasible_rate')}  Mean gap: {agg['gap_pct_mean']['mean']}%")
    print(f"Tokens per question: {agg['prompt_tokens_per_question']['mean']:.0f} in, "
          f"{agg['completion_tokens_per_question']['mean']:.0f} out")


if __name__ == "__main__":
    main()
