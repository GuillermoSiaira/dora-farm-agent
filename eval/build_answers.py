"""Generate eval/answers.jsonl from eval/questions.jsonl using the optimization engine.

Answers are calculated directly by run_tool, never typed by hand.
Re-running this script regenerates the expected answers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dora.tools import run_tool
DEFAULT_QUESTIONS_PATH = ROOT / "questions.jsonl"
# Set to True once SPEC-06 adds Iowa data to the engine; until then Iowa answers would use Argentine data.
IOWA_SUPPORTED = True
DEFAULT_ANSWERS_PATH = ROOT / "answers.jsonl"


def extract_field(data: Any, field_path: str) -> Any:
    """Extract nested field value from dict or list using dot notation."""
    curr = data
    for part in field_path.split("."):
        if isinstance(curr, dict):
            curr = curr.get(part, 0.0)
        elif isinstance(curr, list) and part.isdigit():
            idx = int(part)
            curr = curr[idx] if 0 <= idx < len(curr) else 0.0
        else:
            raise KeyError(f"Cannot access {part} on {type(curr)}")
    return curr


def build_answers(
    questions_path: Path | str = DEFAULT_QUESTIONS_PATH,
    output_path: Path | str = DEFAULT_ANSWERS_PATH,
) -> list[dict]:
    """Run non-refusal scenarios through run_tool and save answers.jsonl."""
    q_path = Path(questions_path)
    out_path = Path(output_path)

    questions: list[dict] = []
    with open(q_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))

    answers: list[dict] = []
    for q in questions:
        if q.get("region") == "iowa" and not IOWA_SUPPORTED:
            continue                    # the engine has no Iowa data until SPEC-06: no fake answers
        if q.get("expect") == "refuse":
            continue

        check = q.get("check")
        if not check:
            continue

        tool_name = check["tool"]
        field_name = check["field"]
        scenario = q["scenario"]

        payload = check.get("payload") or {"scenario": scenario}
        result_raw = run_tool(tool_name, json.dumps(payload))
        result_data = json.loads(result_raw)

        if "error" in result_data:
            raise RuntimeError(f"Engine returned error for question {q['id']}: {result_data['error']}")

        expected_val = extract_field(result_data, field_name)

        answers.append({
            "id": q["id"],
            "tool": tool_name,
            "field": field_name,
            "expected_value": expected_val,
        })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for ans in answers:
            f.write(json.dumps(ans, ensure_ascii=False) + "\n")

    return answers


if __name__ == "__main__":
    generated = build_answers()
    print(f"Generated {len(generated)} answers in {DEFAULT_ANSWERS_PATH}")
