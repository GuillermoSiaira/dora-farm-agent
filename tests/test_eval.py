"""Acceptance tests for SPEC-05: evaluation set with exact answers. No network calls."""
import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from dora.tools import ScenarioError, build_scenario, run_tool
from eval.build_answers import build_answers, extract_field
from eval.report import generate_report
from eval.run_eval import run_evaluation

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS_PATH = ROOT / "eval" / "questions.jsonl"
ANSWERS_PATH = ROOT / "eval" / "answers.jsonl"


def tool_call(name, args, i=1):
    return NS(id=f"call_{i}", function=NS(name=name, arguments=json.dumps(args)))


class ScriptedModel:
    """Returns scripted messages in order for agent completions."""

    def __init__(self, script):
        self.script = list(script)
        self.seen = []
        self.chat = NS(completions=NS(create=self.create))

    def create(self, model, messages, tools):
        self.seen.append(list(messages))
        step = self.script.pop(0)
        msg = NS(content=None, tool_calls=step) if isinstance(step, list) else NS(content=step, tool_calls=None)
        return NS(choices=[NS(message=msg)])


# 1. questions.jsonl has 30 valid lines, and every scenario passes build_scenario
#    without error (except the 3 must-refuse ones, which are marked "expect": "refuse").
def test_questions_file_30_lines_and_valid_scenarios():
    assert QUESTIONS_PATH.is_file(), "eval/questions.jsonl must exist"

    questions = []
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))

    assert len(questions) == 30, f"Expected exactly 30 questions, found {len(questions)}"

    refuse_questions = [q for q in questions if q.get("expect") == "refuse"]
    assert len(refuse_questions) == 3, f"Expected exactly 3 refuse questions, found {len(refuse_questions)}"

    # Check non-refusal questions pass build_scenario
    for q in questions:
        sc = q["scenario"]
        if q.get("expect") == "refuse":
            with pytest.raises(ScenarioError):
                build_scenario(sc)
        else:
            res = build_scenario(sc)
            assert "scenario" in res


# 2. build_answers.py produces an answer for every non-refuse question,
#    and the answers equal a direct run_tool call.
def test_build_answers_produces_answer_equal_to_run_tool(tmp_path):
    answers_temp = tmp_path / "answers.jsonl"
    answers = build_answers(questions_path=QUESTIONS_PATH, output_path=answers_temp)

    assert len(answers) == 27, f"Expected 27 non-refusal answers, got {len(answers)}"

    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = {q["id"]: q for q in (json.loads(l) for l in f if l.strip())}

    for ans in answers:
        qid = ans["id"]
        q = questions[qid]
        assert q.get("expect") != "refuse"

        tool_name = q["check"]["tool"]
        field_name = q["check"]["field"]
        direct_raw = run_tool(tool_name, json.dumps({"scenario": q["scenario"]}))
        direct_data = json.loads(direct_raw)
        direct_val = extract_field(direct_data, field_name)

        assert ans["expected_value"] == direct_val, f"Mismatch on {qid}: {ans['expected_value']} != {direct_val}"


# 3. run_eval.py with the scripted model from tests/test_agent.py runs end to end
#    on 3 questions and writes a results file.
def test_run_eval_scripted_model_end_to_end_3_questions(tmp_path):
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = [json.loads(line) for line in f if line.strip()][:3]

    # Script for 3 questions
    script = [
        [tool_call("evaluate_season", {"scenario": questions[0]["scenario"]})],
        "Se sembrarán 250 ha de soja.",
        [tool_call("evaluate_season", {"scenario": questions[1]["scenario"]})],
        "El valor presente con la venta forward es de USD 85.760.",
        [tool_call("evaluate_season", {"scenario": questions[2]["scenario"]})],
        "El valor presente con insumos a cosecha es de USD 91.015.",
    ]

    model = ScriptedModel(script)
    results_path = tmp_path / "results_test.json"

    result = run_evaluation(
        client=model,
        model="scripted-test-model",
        runs=1,
        limit=3,
        questions_path=QUESTIONS_PATH,
        answers_path=ANSWERS_PATH,
        output_path=results_path,
    )

    assert results_path.is_file(), "Results file must be written"
    with open(results_path, encoding="utf-8") as f:
        saved_data = json.load(f)

    assert saved_data["model"] == "scripted-test-model"
    assert "aggregated" in saved_data
    assert saved_data["aggregated"]["tool_accuracy"]["mean"] == 1.0
    assert saved_data["aggregated"]["answer_correctness"]["mean"] == 1.0
    assert saved_data["aggregated"]["formulation_accuracy"]["mean"] == 1.0


# 4. report.py turns a small results file into a table with all metrics.
def test_report_generates_markdown_table_with_all_metrics(tmp_path):
    sample_results = {
        "model": "demo-eval-model",
        "use_verifier": True,
        "runs": 2,
        "aggregated": {
            "tool_accuracy": {"mean": 0.90, "min": 0.85, "max": 0.95},
            "answer_correctness": {"mean": 0.88, "min": 0.80, "max": 0.96},
            "formulation_accuracy": {"mean": 1.0, "min": 1.0, "max": 1.0},
            "unsupported_numbers_rate": {"mean": 0.05, "min": 0.0, "max": 0.10},
            "verified_rate": {"mean": 0.95, "min": 0.90, "max": 1.0},
            "calls_per_question": {"mean": 2.2, "min": 2.0, "max": 2.4},
            "prompt_tokens_per_question": {"mean": 1250.0, "min": 1200.0, "max": 1300.0},
            "completion_tokens_per_question": {"mean": 180.0, "min": 160.0, "max": 200.0},
        },
    }

    report_path = tmp_path / "REPORT.md"
    table_text = generate_report(sample_results, output_path=report_path)

    assert report_path.is_file()
    assert "| Metric | With Verifier | Without Verifier |" in table_text
    assert "Tool accuracy" in table_text
    assert "Answer correctness" in table_text
    assert "Formulation accuracy" in table_text
    assert "Unsupported numbers (before correction)" in table_text
    assert "Verified after correction" in table_text
    assert "Calls per question" in table_text
    assert "Prompt tokens / question" in table_text
    assert "Completion tokens / question" in table_text
    assert "90.0% (85.0% - 95.0%)" in table_text
