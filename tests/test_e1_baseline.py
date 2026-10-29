"""E1 of docs/plan-de-pruebas.md: the model alone (--baseline) and the engine's check of a plan. No network calls."""
import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from dora.tools import _validate, evaluate_season
from eval.baseline import build_messages, data_text, parse_reply
from eval.plan_check import evaluate_plan
from eval.run_eval import run_evaluation

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = ROOT / "eval" / "questions.jsonl"
ANSWERS = ROOT / "eval" / "answers.jsonl"
FARM = {"area_ha": 500, "own_capital_usd": 50000}


def _question(qid):
    return next(q for q in map(json.loads, QUESTIONS.read_text(encoding="utf-8").splitlines()) if q["id"] == qid)


class FakeModel:
    """Replies to condition A with the given contents, in order; counts tokens like the API."""

    def __init__(self, contents):
        self.contents = list(contents)
        self.seen = []
        self.chat = NS(completions=NS(create=self.create))

    def create(self, model, messages):
        self.seen.append(messages)
        return NS(choices=[NS(message=NS(content=self.contents.pop(0)))],
                  usage=NS(prompt_tokens=1200, completion_tokens=300))


# --- evaluate_plan -------------------------------------------------------------------------------

def test_the_engines_own_plan_is_feasible_with_no_gap():
    best = evaluate_season(FARM)
    ev = evaluate_plan(FARM, best["hectares"])
    assert ev["feasible"] and ev["violations"] == []
    assert ev["gap_usd"] == pytest.approx(0.0, abs=1.0)
    assert ev["npv_optimal_usd"] == pytest.approx(best["npv_usd"], abs=0.01)


def test_a_worse_plan_leaves_money_on_the_table():
    ev = evaluate_plan(FARM, {"sunflower": 250})
    assert ev["feasible"]
    assert ev["gap_usd"] > 1000
    assert ev["npv_plan_usd"] + ev["gap_usd"] == pytest.approx(ev["npv_optimal_usd"], abs=0.02)


def test_rotation_land_and_crop_violations_are_named():
    assert "rotation" in evaluate_plan(FARM, {"soybean": 300})["violations"][0]
    assert "land" in evaluate_plan(FARM, {"wheat": 250, "corn": 250, "soybean": 250})["violations"][0]
    assert "not available" in evaluate_plan(FARM, {"rice": 100})["violations"][0]


def test_a_plan_without_the_money_says_how_much_credit_it_lacks():
    ev = evaluate_plan({"area_ha": 500, "own_capital_usd": 5000, "credit_line_usd": 10000}, {"corn": 250, "soybean": 250})
    assert not ev["feasible"]
    assert ev["violations"][0].startswith("cash")
    assert ev["extra_credit_needed_usd"] > 0


def test_a_plan_that_cannot_deliver_its_forward_sale_is_infeasible():
    sc = dict(FARM, constraints=[{"type": "forward_sale", "crop": "wheat", "month": "2027-01", "tonnes": 400, "price_usd_t": 210}])
    ev = evaluate_plan(sc, {"soybean": 250})
    assert not ev["feasible"]
    assert "forward sales of wheat" in ev["violations"][0]


def test_the_farmers_minimum_area_is_checked():
    sc = dict(FARM, constraints=[{"type": "min_area", "crop": "soybean", "ha": 200}])
    assert "min_area" in evaluate_plan(sc, {"wheat": 100})["violations"][0]


# --- the prompt carries the engine's own numbers ------------------------------------------------

def test_data_text_quotes_the_scenarios_coefficients():
    sc, _ = _validate(FARM)
    text = data_text(FARM)
    assert f"yield {sc.crop_yield('soybean'):.3f} t/ha" in text
    assert f"f23: {sc.net_price('soybean', 23):.2f}" in text
    assert f"f3: {sc.payments_per_ha('wheat')[3]:.2f}" in text
    assert "50,000.00 USD" in text


def test_refusal_questions_get_their_regions_default_data():
    msgs = build_messages(_question("q18"))
    assert "Quiero sembrar 300 hectáreas de arroz" in msgs[1]["content"]
    assert "Region: southeast_buenos_aires" in msgs[1]["content"]


def test_parse_reply_reads_fenced_json_and_rejects_prose():
    assert parse_reply('```json\n{"hectares": {"soybean": 250}}\n```')["hectares"] == {"soybean": 250}
    with pytest.raises(ValueError):
        parse_reply("Sembrá soja.")


# --- run_evaluation --baseline -------------------------------------------------------------------

def _reply(hectares, value, text):
    return json.dumps({"hectares": hectares, "sales": {}, "expected_npv_usd": 1, "answer_value": value, "answer_text": text})


def test_baseline_scores_answer_plan_and_spread(tmp_path):
    q08 = _question("q08")
    expected = next(a for a in map(json.loads, ANSWERS.read_text(encoding="utf-8").splitlines()) if a["id"] == "q08")["expected_value"]
    best = evaluate_season(q08["scenario"])["hectares"]
    model = FakeModel([
        _reply(best, expected, f"Te conviene sembrar {expected} ha de trigo."),
        _reply({"wheat": 150, "corn": 150, "soybean": 150}, 150, "Sembrá 150 ha de trigo."),
    ])
    res = run_evaluation(client=model, model="fake", runs=2, baseline=True, ids=["q08"],
                         questions_path=QUESTIONS, answers_path=ANSWERS, output_path=tmp_path / "a.json")
    first, second = res["detailed_results"][0][0], res["detailed_results"][1][0]
    assert first["answer_correctness"] and first["plan_feasible"] and first["plan_gap_usd"] == pytest.approx(0, abs=1)
    assert not second["answer_correctness"] and not second["plan_feasible"]
    assert res["condition"] == "baseline"
    pq = res["per_question"]["q08"]
    assert pq["correct_runs"] == 1 and pq["feasible_runs"] == 1
    assert pq["reported_value"]["distinct"] == 2
    assert res["aggregated"]["prompt_tokens_per_question"]["mean"] == 1200
    assert [m["role"] for m in model.seen[0]] == ["system", "user"]     # one call, no tools (create takes none)


def test_baseline_counts_numbers_without_support_and_bad_json(tmp_path):
    model = FakeModel(["no sé", _reply({"soybean": 250}, 12345.6, "Vas a ganar 12.345,6 USD.")])
    res = run_evaluation(client=model, model="fake", runs=2, baseline=True, ids=["q04"],
                         questions_path=QUESTIONS, answers_path=ANSWERS, output_path=tmp_path / "a.json")
    bad, made_up = res["detailed_results"][0][0], res["detailed_results"][1][0]
    assert bad["parse_error"] and bad["plan_feasible"] is False
    assert made_up["has_unsupported_before_correction"]


def test_baseline_skips_region_comparisons(tmp_path):
    res = run_evaluation(client=FakeModel([]), model="fake", runs=1, baseline=True, ids=["q33"],
                         questions_path=QUESTIONS, answers_path=ANSWERS, output_path=tmp_path / "a.json")
    assert res["detailed_results"][0][0]["skipped"] == "compare_regions"


# --- conditions B and C: the agent's plan is checked the same way -------------------------------

def test_agent_plan_and_reported_value_come_from_its_last_season(tmp_path):
    from tests.test_eval import ScriptedModel, tool_call
    q08 = _question("q08")
    expected = evaluate_season(q08["scenario"])["hectares"]["wheat"]
    model = ScriptedModel([[tool_call("evaluate_season", {"scenario": q08["scenario"]})],
                           f"Conviene sembrar {expected} ha de trigo."])
    res = run_evaluation(client=model, model="fake", runs=1, use_verifier=False, ids=["q08"],
                         questions_path=QUESTIONS, answers_path=ANSWERS, output_path=tmp_path / "b.json")
    rec = res["detailed_results"][0][0]
    assert rec["reported_value"] == expected
    assert rec["plan_feasible"] and rec["plan_gap_usd"] == pytest.approx(0, abs=1)
    assert res["condition"] == "no_verifier"
