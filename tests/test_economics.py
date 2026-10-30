"""Acceptance tests for SPEC-24: Cost per verified answer.

No network calls.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import numpy as np
import pytest
from scipy.stats import binomtest

from dora.tools import evaluate_season, shadow_prices
from eval.economics import (
    bootstrap_ci,
    calculate_breakeven_volume,
    calculate_cost_per_question,
    compute_run_economics,
    mcnemar_exact,
)
from eval.frontier import find_efficient_frontier
from eval.report import generate_report
from eval.run_eval import run_evaluation
from tests.test_agent import ScriptedModel, tool_call
from tests.test_e1_baseline import FakeModel

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS_PATH = ROOT / "eval" / "questions.jsonl"
ANSWERS_PATH = ROOT / "eval" / "answers.jsonl"


# ------------------------------------------------------------------------------
# Test 1: Telemetry fields and no API key in results file
# ------------------------------------------------------------------------------
def test_1_telemetry_fields_and_no_api_key_in_results(tmp_path):
    """1. run_eval.py with the scripted model from tests/test_agent.py (conditions B and C)

    and with the fake model of tests/test_e1_baseline.py (condition A) writes latency_s,
    requests, prompt_tokens and completion_tokens for every question, and provider,
    api_host, commit at top level. No API key appears anywhere in the file.
    """
    secret_key = "sk-antigravity-secret-key-12345"

    class ScriptedModelWithTelemetry(ScriptedModel):
        def __init__(self, script, base_url=None):
            super().__init__(script)
            self.base_url = base_url

        def create(self, model, messages, tools):
            res = super().create(model, messages, tools)
            res.usage = NS(prompt_tokens=450, completion_tokens=85)
            return res

    # 1. Condition A (baseline)
    fake_reply = json.dumps({
        "hectares": {"wheat": 250},
        "sales": {},
        "expected_npv_usd": 100000,
        "answer_value": 250,
        "answer_text": "Te conviene sembrar 250 ha de trigo.",
    })
    model_a = FakeModel([fake_reply])
    model_a.base_url = f"https://api.fake-provider.com/v1?auth={secret_key}"

    path_a = tmp_path / "cond_a.json"
    with patch.dict("os.environ", {"DORA_API_KEY": secret_key}):
        res_a = run_evaluation(
            client=model_a,
            model="fake-model",
            runs=1,
            baseline=True,
            ids=["q08"],
            questions_path=QUESTIONS_PATH,
            answers_path=ANSWERS_PATH,
            output_path=path_a,
            provider="fake-provider",
        )

    assert res_a["provider"] == "fake-provider"
    assert res_a["api_host"] == "api.fake-provider.com"
    assert res_a["commit"] is not None
    rec_a = res_a["detailed_results"][0][0]
    assert "latency_s" in rec_a and isinstance(rec_a["latency_s"], (int, float)) and rec_a["latency_s"] >= 0
    assert rec_a["requests"] == 1
    assert rec_a["prompt_tokens"] == 1200
    assert rec_a["completion_tokens"] == 300

    raw_text_a = path_a.read_text(encoding="utf-8")
    assert secret_key not in raw_text_a
    assert "sk-" not in raw_text_a

    # 2. Condition B (no_verifier) and C (with_verifier)
    q08_sc = {"area_ha": 500, "own_capital_usd": 50000}
    for use_ver, cond_name, file_name in [(False, "no_verifier", "cond_b.json"), (True, "with_verifier", "cond_c.json")]:
        script = [
            [tool_call("evaluate_season", {"scenario": q08_sc})],
            "Te conviene sembrar 250 ha de trigo.",
        ]
        model_bc = ScriptedModelWithTelemetry(script, base_url="https://api.meta.ai/v1")
        path_bc = tmp_path / file_name

        with patch.dict("os.environ", {"DORA_API_KEY": secret_key}):
            res_bc = run_evaluation(
                client=model_bc,
                model="muse-spark-1.3",
                runs=1,
                use_verifier=use_ver,
                ids=["q08"],
                questions_path=QUESTIONS_PATH,
                answers_path=ANSWERS_PATH,
                output_path=path_bc,
                provider="meta",
            )

        assert res_bc["provider"] == "meta"
        assert res_bc["api_host"] == "api.meta.ai"
        assert res_bc["commit"] is not None
        assert res_bc["condition"] == cond_name
        rec_bc = res_bc["detailed_results"][0][0]
        assert "latency_s" in rec_bc and isinstance(rec_bc["latency_s"], (int, float)) and rec_bc["latency_s"] >= 0
        assert rec_bc["requests"] == 2
        assert rec_bc["prompt_tokens"] == 900  # 2 calls * 450
        assert rec_bc["completion_tokens"] == 170  # 2 calls * 85

        raw_text_bc = path_bc.read_text(encoding="utf-8")
        assert secret_key not in raw_text_bc
        assert "sk-" not in raw_text_bc


# ------------------------------------------------------------------------------
# Test 2: Cost per question hand calculation with and without cached tokens
# ------------------------------------------------------------------------------
def test_2_cost_per_question_hand_calculation():
    """2. Cost per question on a hand-built results file with known tokens and prices

    equals the hand calculation (to 1e-12), with and without cached tokens.
    """
    pricing = {
        "billing": "per_token",
        "usd_per_m_input": 2.0,
        "usd_per_m_cached_input": 0.5,
        "usd_per_m_output": 10.0,
    }

    # Case without cached tokens:
    # 10,000 prompt tokens, 2,000 completion tokens
    # Cost = 10,000 * 2.0 / 1e6 + 2,000 * 10.0 / 1e6 = 0.02 + 0.02 = 0.04
    rec_without_cache = {
        "prompt_tokens": 10000,
        "completion_tokens": 2000,
    }
    cost_no_cache = calculate_cost_per_question(rec_without_cache, pricing)
    expected_no_cache = 0.04
    assert abs(cost_no_cache - expected_no_cache) < 1e-12

    # Case with cached tokens:
    # 10,000 prompt tokens, 8,000 cached prompt tokens, 2,000 completion tokens
    # Uncached prompt: 10,000 - 8,000 = 2,000
    # Cost = 2,000 * 2.0 / 1e6 + 8,000 * 0.5 / 1e6 + 2,000 * 10.0 / 1e6
    #      = 0.004 + 0.004 + 0.02 = 0.028
    rec_with_cache = {
        "prompt_tokens": 10000,
        "cached_prompt_tokens": 8000,
        "completion_tokens": 2000,
    }
    cost_with_cache = calculate_cost_per_question(rec_with_cache, pricing)
    expected_with_cache = 0.028
    assert abs(cost_with_cache - expected_with_cache) < 1e-12

    # Average over both questions
    results_mock = {
        "detailed_results": [[rec_without_cache, rec_with_cache]],
    }
    econ = compute_run_economics(results_mock, pricing)
    expected_avg = (expected_no_cache + expected_with_cache) / 2.0
    assert abs(econ["usd_per_question"] - expected_avg) < 1e-12


# ------------------------------------------------------------------------------
# Test 3: Null price gives 'price unknown' and tokens only
# ------------------------------------------------------------------------------
def test_3_null_price_reports_price_unknown():
    """3. A null price gives 'price unknown' and tokens only; no exception, no zero cost."""
    pricing_null = {
        "billing": "per_token",
        "usd_per_m_input": None,
        "usd_per_m_cached_input": None,
        "usd_per_m_output": None,
    }
    rec = {
        "id": "q01",
        "prompt_tokens": 15000,
        "completion_tokens": 1200,
        "answer_correctness": True,
        "verified": True,
        "latency_s": 2.5,
    }
    results = {"detailed_results": [[rec]]}

    cost = calculate_cost_per_question(rec, pricing_null)
    assert cost is None

    econ = compute_run_economics(results, pricing_null)
    assert econ["usd_per_question"] == "price unknown"
    assert econ["usd_per_correct_answer"] == "price unknown"
    assert econ["usd_per_verified_correct_answer"] == "price unknown"
    assert econ["usd_per_verified_correct_answer_ci"] is None
    # Tokens and latency are reported
    assert econ["prompt_tokens_mean"] == 15000.0
    assert econ["completion_tokens_mean"] == 1200.0
    assert econ["latency_p50_s"] == 2.5


# ------------------------------------------------------------------------------
# Test 4: Cost per verified correct answer counts only correct & verified
# ------------------------------------------------------------------------------
def test_4_zero_verified_correct_reports_infinity():
    """4. Cost per verified correct answer counts only answers that are correct and verified;

    with zero such answers it reports '∞ (no correct answers)'.
    """
    pricing = {
        "billing": "per_token",
        "usd_per_m_input": 1.0,
        "usd_per_m_output": 2.0,
    }
    # 4 questions:
    # q1: correct, not verified
    # q2: incorrect, verified
    # q3: incorrect, not verified
    # q4: incorrect, not verified
    recs = [
        {"id": "q1", "prompt_tokens": 1000, "completion_tokens": 100, "answer_correctness": True, "verified": False},
        {"id": "q2", "prompt_tokens": 1000, "completion_tokens": 100, "answer_correctness": False, "verified": True},
        {"id": "q3", "prompt_tokens": 1000, "completion_tokens": 100, "answer_correctness": False, "verified": False},
        {"id": "q4", "prompt_tokens": 1000, "completion_tokens": 100, "answer_correctness": False, "verified": False},
    ]
    results = {"detailed_results": [recs]}
    econ = compute_run_economics(results, pricing)
    assert econ["verified_correct_count"] == 0
    assert econ["usd_per_verified_correct_answer"] == "∞ (no correct answers)"

    # Now add one question that is both correct and verified
    recs.append({"id": "q5", "prompt_tokens": 1000, "completion_tokens": 100, "answer_correctness": True, "verified": True})
    results_with_one = {"detailed_results": [recs]}
    econ_one = compute_run_economics(results_with_one, pricing)
    assert econ_one["verified_correct_count"] == 1
    assert isinstance(econ_one["usd_per_verified_correct_answer"], float)


# ------------------------------------------------------------------------------
# Test 5: Bootstrap reproducibility and all-correct [1.0, 1.0]
# ------------------------------------------------------------------------------
def test_5_bootstrap_reproducibility_and_all_correct():
    """5. Bootstrap with the fixed seed gives the same interval twice;

    with all answers correct, the interval for correctness is [1, 1].
    """
    pricing = {"billing": "per_token", "usd_per_m_input": 1.0, "usd_per_m_output": 1.0}
    recs_all_correct = [
        {"id": f"q{i}", "prompt_tokens": 1000, "completion_tokens": 100, "answer_correctness": True, "verified": True}
        for i in range(20)
    ]
    results_all = {"detailed_results": [recs_all_correct]}

    ci_1 = bootstrap_ci(results_all, pricing, metric="answer_correctness", n_resamples=2000, seed=20261029)
    ci_2 = bootstrap_ci(results_all, pricing, metric="answer_correctness", n_resamples=2000, seed=20261029)
    assert ci_1 == ci_2
    assert ci_1 == (1.0, 1.0)

    # Mixed results: verify identical intervals on consecutive calls with fixed seed
    recs_mixed = [
        {"id": f"q{i}", "prompt_tokens": 1000, "completion_tokens": 100, "answer_correctness": (i % 2 == 0), "verified": (i % 2 == 0)}
        for i in range(20)
    ]
    results_mixed = {"detailed_results": [recs_mixed]}
    ci_m1 = bootstrap_ci(results_mixed, pricing, metric="answer_correctness", n_resamples=2000, seed=20261029)
    ci_m2 = bootstrap_ci(results_mixed, pricing, metric="answer_correctness", n_resamples=2000, seed=20261029)
    assert ci_m1 == ci_m2
    assert 0.0 < ci_m1[0] < ci_m1[1] < 1.0


# ------------------------------------------------------------------------------
# Test 6: McNemar exact test for b=8, c=1
# ------------------------------------------------------------------------------
def test_6_mcnemar_exact_b8_c1():
    """6. McNemar: for b = 8, c = 1 the p-value equals scipy.stats.binomtest(1, 9, 0.5).pvalue."""
    expected_p = binomtest(1, 9, 0.5).pvalue
    res = mcnemar_exact(b=8, c=1)
    assert res["b"] == 8
    assert res["c"] == 1
    assert abs(res["p_value"] - expected_p) < 1e-12
    assert abs(res["p_value"] - 0.0390625) < 1e-12


# ------------------------------------------------------------------------------
# Test 7: Break-even volume for dedicated GPU
# ------------------------------------------------------------------------------
def test_7_breakeven_dedicated_gpu():
    """7. Break-even: for 1.00 USD/GPU-hour, 1 GPU, 730 h and 0.05 USD/question, Q* = 14,600."""
    q_star = calculate_breakeven_volume(
        usd_per_gpu_hour=1.00,
        gpus=1,
        hours_on_per_month=730,
        usd_per_question_per_token=0.05,
    )
    assert q_star == 14600


# ------------------------------------------------------------------------------
# Test 8: Frontier marks dominated point as not efficient
# ------------------------------------------------------------------------------
def test_8_frontier_dominated_point_not_efficient():
    """8. Frontier: in a set of 4 points, the dominated point is not marked efficient."""
    points = [
        {"name": "point_A", "cost": 0.01, "accuracy": 0.80},
        {"name": "point_B", "cost": 0.02, "accuracy": 0.75},  # Dominated by point_A (higher cost, lower accuracy)
        {"name": "point_C", "cost": 0.02, "accuracy": 0.90},  # Higher accuracy than A
        {"name": "point_D", "cost": 0.05, "accuracy": 0.95},  # Highest accuracy
    ]
    frontier = find_efficient_frontier(points)
    by_name = {p["name"]: p["efficient"] for p in frontier}
    assert by_name["point_A"] is True
    assert by_name["point_B"] is False, "Point B is dominated by Point A and must not be efficient"
    assert by_name["point_C"] is True
    assert by_name["point_D"] is True


# ------------------------------------------------------------------------------
# Test 9: Report renders old results and appends Economics section when present
# ------------------------------------------------------------------------------
def test_9_report_renders_old_and_adds_economics(tmp_path):
    """9. report.py still renders the old results files (without the new fields)

    and adds the Economics section when they exist.
    """
    pricing_file = tmp_path / "pricing.json"
    pricing_file.write_text(json.dumps({
        "muse-spark-1.3@meta": {
            "billing": "per_token",
            "usd_per_m_input": 0.50,
            "usd_per_m_cached_input": 0.125,
            "usd_per_m_output": 1.50,
            "source": "https://api.meta.ai/pricing",
            "read_on": "2026-10-30",
        }
    }), encoding="utf-8")

    # Old results file (no latency_s, no requests, no provider, no api_host)
    old_results = {
        "model": "muse-spark-1.3",
        "condition": "no_verifier",
        "commit": "abc1234",
        "use_verifier": False,
        "runs": 1,
        "timestamp": "20261028_120000",
        "question_ids": ["q01"],
        "run_metrics": [{"tool_accuracy": 1.0, "answer_correctness": 1.0, "verified_rate": 1.0}],
        "aggregated": {
            "tool_accuracy": {"mean": 1.0},
            "answer_correctness": {"mean": 1.0},
            "formulation_accuracy": {"mean": 1.0},
            "unsupported_numbers_rate": {"mean": 0.0},
            "verified_rate": {"mean": 1.0},
            "calls_per_question": {"mean": 1.0},
            "prompt_tokens_per_question": {"mean": 1000.0},
            "completion_tokens_per_question": {"mean": 200.0},
            "feasible_rate": {"mean": 1.0},
            "gap_pct_mean": {"mean": 0.0},
        },
        "per_question": {"q01": {"expected_value": 100, "correct_runs": 1}},
        "detailed_results": [[{
            "id": "q01",
            "text": "How many ha?",
            "reply": "100 ha",
            "tool_accuracy": True,
            "answer_correctness": True,
            "verified": True,
            "prompt_tokens": 1000,
            "completion_tokens": 200,
        }]],
    }
    old_file = tmp_path / "old_run.json"
    old_file.write_text(json.dumps(old_results), encoding="utf-8")

    out_old = tmp_path / "REPORT_old.md"
    rep_old = generate_report(results_path=old_file, output_path=out_old, pricing_path=pricing_file)
    assert "Evaluation Report" in rep_old
    assert "muse-spark-1.3" in rep_old
    # Old file renders without error and generates Economics section based on token counts
    assert "## Economics" in rep_old

    # New results file with new fields (latency_s, requests, provider)
    new_results = dict(old_results)
    new_results.update({
        "provider": "meta",
        "api_host": "api.meta.ai",
    })
    new_results["detailed_results"] = [[{
        "id": "q01",
        "text": "How many ha?",
        "reply": "100 ha",
        "tool_accuracy": True,
        "answer_correctness": True,
        "verified": True,
        "requests": 2,
        "latency_s": 1.25,
        "prompt_tokens": 1000,
        "completion_tokens": 200,
    }]]
    new_file = tmp_path / "new_run.json"
    new_file.write_text(json.dumps(new_results), encoding="utf-8")

    out_new = tmp_path / "REPORT_new.md"
    rep_new = generate_report(results_path=new_file, output_path=out_new, pricing_path=pricing_file)
    assert "## Economics" in rep_new
    assert "muse-spark-1.3@meta" in rep_new
    assert "Latency p50 / p95" in rep_new


# ------------------------------------------------------------------------------
# Test 10: Engine numbers unchanged compared to main to 1e-9
# ------------------------------------------------------------------------------
def test_10_engine_numbers_unchanged():
    """10. The engine's numbers do not change: evaluate_season and shadow_prices

    for the default scenario equal main (to 1e-9).
    """
    fixture_path = ROOT / "tests" / "data" / "spec23_main_tool_numbers.json"
    assert fixture_path.is_file(), f"Fixture missing: {fixture_path}"

    with open(fixture_path, "r", encoding="utf-8") as f:
        baseline = json.load(f)["numbers"]

    def extract_numbers(obj, prefix=""):
        nums = {}
        if isinstance(obj, dict):
            for k, v in obj.items():
                p = f"{prefix}.{k}" if prefix else k
                nums.update(extract_numbers(v, p))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                p = f"{prefix}[{i}]"
                nums.update(extract_numbers(v, p))
        elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
            nums[prefix] = float(obj)
        return nums

    default_sc = {
        "area_ha": 500.0,
        "crops": ["wheat", "corn", "soybean", "sunflower"],
        "own_capital_usd": 50000.0,
        "credit_line_usd": 100000.0,
        "region": "southeast_buenos_aires",
    }
    eval_actual = extract_numbers(evaluate_season(default_sc, lang="es"))
    eval_base = baseline["form_default|evaluate_season|es"]
    for k, base_val in eval_base.items():
        assert k in eval_actual, f"Missing key {k} in evaluate_season"
        assert eval_actual[k] == pytest.approx(base_val, abs=1e-9), f"Mismatch at {k}"

    shadow_actual = extract_numbers(shadow_prices(default_sc, lang="es"))
    shadow_base = baseline["form_default|shadow_prices|es"]
    for k, base_val in shadow_base.items():
        assert k in shadow_actual, f"Missing key {k} in shadow_prices"
        assert shadow_actual[k] == pytest.approx(base_val, abs=1e-9), f"Mismatch at {k}"
