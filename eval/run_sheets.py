"""SPEC-50 benchmark runner: evaluates models formulating linear programming spreadsheets.

    python eval/run_sheets.py --model Qwen/Qwen2.5-7B-Instruct --base <server URL>/v1 \
        --env D:/projects/dora-hackathon/.env --out eval/results/sheets/pilot

The runner evaluates models across three arms:
1. 'alone': only the required JSON format and basic instruction.
2. 'recipe': format + modelling recipe (Tow's 5 steps + Duality).
3. 'recipe_examples': recipe + two worked examples (prob_01 and prob_04).
   Problems 1 and 4 are excluded from recipe_examples score calculations.

Supports multi-turn evaluation for problems requiring economic reading of the sensitivity report.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

from eval.run_eval import _load_dotenv  # noqa: E402
from eval.sheets.grader import (  # noqa: E402
    extract_sheet_json,
    grade_reading,
    grade_sheet,
)
from eval.sheets.problems import load_problems  # noqa: E402


SYSTEM_PROMPT_ES = """Sos un asistente experto que formula modelos de programación lineal directamente como planillas de cálculo (estilo Excel / Google Sheets / OpenSolver).
Debés responder estrictamente con un único bloque JSON con el siguiente formato:

```json
{
  "cells": {
    "A1": "Cultivo", "B1": "Trigo", "C1": "Maíz",
    "A2": "Margen", "B2": 300, "C2": 400,
    "B5": 0, "C5": 0,
    "F10": "=SUMPRODUCT(B5:C5, B2:C2)",
    "F11": "=B5 + C5"
  },
  "variables": "B5:C5",
  "objective": {"cell": "F10", "sense": "max"},
  "constraints": [
    {"lhs": "F11", "op": "<=", "rhs": 100},
    {"lhs": "B5:C5", "op": ">=", "rhs": 0}
  ],
  "assumptions": ["Supuesto explícito si falta algún dato"],
  "questions_to_user": ["Pregunta al usuario si el problema está incompleto"],
  "dual_sheet": {
    "cells": { ... },
    "variables": "B5:C5",
    "price_of_row": [0, 1],
    "objective": {"cell": "H10", "sense": "min"},
    "constraints": [ ... ]
  }
}
```

Reglas estrictas de la planilla:
1. En las fórmulas solo se permiten: referencias de celda o rango en notación A1 (ej. B5, B5:C5), números, operadores +, -, *, /, paréntesis, y las funciones SUM y SUMPRODUCT.
2. Está prohibido usar IF, MAX, MIN u otras funciones no lineales.
3. Declarar siempre las restricciones de no negatividad (>= 0).
4. Usar únicamente los números provistos en el enunciado. No inventar parámetros no dados; si falta información, declararla en "assumptions" o formular una pregunta en "questions_to_user".
5. Si el problema solicita el dual ("dual_sheet"), formular la planilla dual como la transpuesta del primal, donde cada variable dual representa el precio de una fila primal indicada en "price_of_row".
"""

SYSTEM_PROMPT_EN = """You are an expert assistant that formulates linear programming models directly as spreadsheets (Excel / Google Sheets / OpenSolver style).
You must answer strictly with a single JSON block formatted as follows:

```json
{
  "cells": {
    "A1": "Crop", "B1": "Wheat", "C1": "Corn",
    "A2": "Margin", "B2": 300, "C2": 400,
    "B5": 0, "C5": 0,
    "F10": "=SUMPRODUCT(B5:C5, B2:C2)",
    "F11": "=B5 + C5"
  },
  "variables": "B5:C5",
  "objective": {"cell": "F10", "sense": "max"},
  "constraints": [
    {"lhs": "F11", "op": "<=", "rhs": 100},
    {"lhs": "B5:C5", "op": ">=", "rhs": 0}
  ],
  "assumptions": ["Explicit assumption if any data is unstated"],
  "questions_to_user": ["Clarification question to user if incomplete"],
  "dual_sheet": {
    "cells": { ... },
    "variables": "B5:C5",
    "price_of_row": [0, 1],
    "objective": {"cell": "H10", "sense": "min"},
    "constraints": [ ... ]
  }
}
```

Strict spreadsheet rules:
1. In formulas, only cell/range references (A1 notation), numbers, operators +, -, *, /, parentheses, and functions SUM and SUMPRODUCT are allowed.
2. Disallowed: IF, MAX, MIN, or nonlinear functions.
3. Always explicitly include non-negativity constraints (>= 0).
4. Use only numbers given in the problem statement. Do not invent constants; if unstated, declare in "assumptions" or query in "questions_to_user".
5. If the problem requests the dual ("dual_sheet"), formulate the dual sheet as the transpose of the primal, mapping variables via "price_of_row".
"""

EXCLUDED_EXAMPLE_IDS = {"prob_01", "prob_04"}


def load_recipe(language: str = "es") -> str:
    fname = "recipe.es.md" if language == "es" else "recipe.en.md"
    p = ROOT / "sheets" / "data" / fname
    if p.exists():
        return p.read_text(encoding="utf-8")
    return ""


def load_examples_block(language: str = "es") -> str:
    """Build the two worked examples from prob_01 and prob_04."""
    fixtures_dir = ROOT.parent / "tests" / "fixtures" / "spec50"
    p1 = json.loads((fixtures_dir / "prob_01.json").read_text(encoding="utf-8"))
    p4 = json.loads((fixtures_dir / "prob_04.json").read_text(encoding="utf-8"))

    if language == "es":
        return f"""
### Ejemplos Resueltos de Referencia

#### Ejemplo 1: prob_01 (Dos cultivos, tierra y trabajo)
Enunciado: Un productor dispone de 100 ha de tierra y 160 horas de trabajo. Trigo rinde 300 USD/ha (1 h/ha) y maíz 400 USD/ha (2 h/ha).
Razonamiento: Las actividades son B5 (ha trigo) y C5 (ha maíz). Se maximiza el margen neto sujeto a tierra disponible y trabajo.

```json
{json.dumps(p1, indent=2, ensure_ascii=False)}
```

#### Ejemplo 2: prob_04 (Venta en cosecha vs almacenamiento)
Enunciado: Cosecha de soja (400 t) y maíz (600 t). Venta inmediata o almacenamiento en tres silos (A cap 300, B cap 250, C cap 400).
Razonamiento: Ocho actividades de decisión (ventas directas y almacenadas). Restricciones de cosecha total y capacidad de cada silo.

```json
{json.dumps(p4, indent=2, ensure_ascii=False)}
```
"""
    else:
        return f"""
### Worked Reference Examples

#### Example 1: prob_01 (Two crops, land and labour)
Statement: A farmer has 100 ha of land and 160 hours of labour. Wheat yields 300 USD/ha (1 h/ha), corn 400 USD/ha (2 h/ha).
Reasoning: Decision activities are B5 (wheat ha) and C5 (corn ha). Maximize margin subject to land and labour availability.

```json
{json.dumps(p1, indent=2, ensure_ascii=False)}
```

#### Example 2: prob_04 (Harvest sale vs storage)
Statement: Harvest of soybean (400 t) and corn (600 t). Direct sale or storage across three silos (A cap 300, B cap 250, C cap 400).
Reasoning: Eight decision variables (direct sales and silo storage). Balance constraints for harvested volume and individual silo capacities.

```json
{json.dumps(p4, indent=2, ensure_ascii=False)}
```
"""


def build_system_prompt(arm: str, language: str = "es") -> str:
    base = SYSTEM_PROMPT_ES if language == "es" else SYSTEM_PROMPT_EN
    if arm == "alone":
        return base
    elif arm == "recipe":
        recipe = load_recipe(language)
        return f"{base}\n\n---\n## Receta Metodológica\n\n{recipe}"
    elif arm == "recipe_examples":
        recipe = load_recipe(language)
        examples = load_examples_block(language)
        return f"{base}\n\n---\n## Receta Metodológica\n\n{recipe}\n\n---\n{examples}"
    return base


def format_sensitivity_report_prompt(report: dict[str, Any], questions: list[dict[str, Any]], language: str = "es") -> str:
    """Format the sensitivity report and the reading questions for turn 2."""
    if language == "es":
        txt = ["A continuación se presenta el Informe de Sensibilidad (Solver) generado a partir de tu planilla:"]
        txt.append("\n1. Precios Sombra y Holguras de Restricciones:")
        for con, sp in report.get("shadow_prices", {}).items():
            sl = report.get("slacks", {}).get(con, 0.0)
            txt.append(f"  - {con}: Precio Sombra = {sp}, Holgura = {sl}")

        txt.append("\n2. Costos Reducidos de Variables:")
        for var, rc in report.get("reduced_costs", {}).items():
            txt.append(f"  - {var}: Costo Reducido = {rc}")

        txt.append("\n3. Rangos de Variación Permisible (Lado Derecho / RHS):")
        for con, r in report.get("rhs_ranges", {}).items():
            txt.append(f"  - {con}: Base = {r['base']}, Inferior = {r['lower']}, Superior = {r['upper']}")

        txt.append("\n4. Rangos de Variación Permisible (Coeficientes Función Objetivo):")
        for var, r in report.get("obj_ranges", {}).items():
            txt.append(f"  - {var}: Base = {r['base']}, Inferior = {r['lower']}, Superior = {r['upper']}")

        txt.append("\nPor favor, responde a las siguientes preguntas económicas en formato JSON:")
        txt.append('```json\n{\n  "answers": [')
        for q in questions:
            txt.append(f'    {{"q": {q["q"]}, "pregunta": "{q.get("text_es", "")}", "value": <número>, "unit": "<unidad>"}},')
        txt.append('  ]\n}\n```')
        return "\n".join(txt)
    else:
        txt = ["Below is the Sensitivity Report (Solver) generated from your spreadsheet:"]
        txt.append("\n1. Constraint Shadow Prices and Slacks:")
        for con, sp in report.get("shadow_prices", {}).items():
            sl = report.get("slacks", {}).get(con, 0.0)
            txt.append(f"  - {con}: Shadow Price = {sp}, Slack = {sl}")

        txt.append("\n2. Variable Reduced Costs:")
        for var, rc in report.get("reduced_costs", {}).items():
            txt.append(f"  - {var}: Reduced Cost = {rc}")

        txt.append("\n3. Allowable RHS Ranges:")
        for con, r in report.get("rhs_ranges", {}).items():
            txt.append(f"  - {con}: Base = {r['base']}, Lower = {r['lower']}, Upper = {r['upper']}")

        txt.append("\n4. Allowable Objective Coefficient Ranges:")
        for var, r in report.get("obj_ranges", {}).items():
            txt.append(f"  - {var}: Base = {r['base']}, Lower = {r['lower']}, Upper = {r['upper']}")

        txt.append("\nPlease answer the following economic questions in JSON format:")
        txt.append('```json\n{\n  "answers": [')
        for q in questions:
            txt.append(f'    {{"q": {q["q"]}, "question": "{q.get("text_en", "")}", "value": <number>, "unit": "<unit>"}},')
        txt.append('  ]\n}\n```')
        return "\n".join(txt)


def evaluate_problem(
    client: Any,
    model: str,
    problem: dict[str, Any],
    arm: str,
    language: str = "es",
    max_tokens: int = 8192,
) -> dict[str, Any]:
    """Execute evaluation for one problem in one arm (up to two conversational turns)."""
    system_prompt = build_system_prompt(arm, language=language)
    user_prompt = problem["statement_es"] if language == "es" else problem["statement_en"]

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    t0 = time.perf_counter()
    resp1 = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
    )
    raw1 = resp1.choices[0].message.content or ""
    usage1 = resp1.usage
    tokens1 = {
        "prompt_tokens": getattr(usage1, "prompt_tokens", 0) if usage1 else 0,
        "completion_tokens": getattr(usage1, "completion_tokens", 0) if usage1 else 0,
    }

    parsed1 = extract_sheet_json(raw1)
    grade1 = grade_sheet(parsed1, problem=problem) if parsed1 is not None else {
        "status": "invalid",
        "error": "No valid JSON found in model response",
        "objective": None,
        "solution": None,
        "objective_ok": False,
        "solution_ok": False,
        "missing_nonneg": False,
        "invented_numbers": [],
        "asked_or_declared": False,
        "solved": False,
        "handled": False,
    }

    turn2_data = None
    if problem.get("asks_reading") and grade1.get("status") == "optimal" and grade1.get("sensitivity_report"):
        rep = grade1["sensitivity_report"]
        q_prompt = format_sensitivity_report_prompt(rep, problem["asks_reading"], language=language)
        messages.append({"role": "assistant", "content": raw1})
        messages.append({"role": "user", "content": q_prompt})

        resp2 = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
        )
        raw2 = resp2.choices[0].message.content or ""
        usage2 = resp2.usage
        tokens2 = {
            "prompt_tokens": getattr(usage2, "prompt_tokens", 0) if usage2 else 0,
            "completion_tokens": getattr(usage2, "completion_tokens", 0) if usage2 else 0,
        }
        parsed2 = extract_sheet_json(raw2)
        answers = parsed2.get("answers") if isinstance(parsed2, dict) else None
        read_grade = grade_reading(answers, rep, problem) if answers is not None else {
            "reading_ok": False,
            "results": [],
            "error": "No valid answers list in turn 2 JSON",
        }
        turn2_data = {
            "raw_reply": raw2,
            "parsed_json": parsed2,
            "tokens": tokens2,
            "reading_grade": read_grade,
        }

    wall_s = round(time.perf_counter() - t0, 2)
    return {
        "problem_id": problem["id"],
        "arm": arm,
        "raw_reply": raw1,
        "parsed_sheet": parsed1,
        "grade_result": grade1,
        "tokens": tokens1,
        "turn2": turn2_data,
        "wall_s": wall_s,
    }


def aggregate_arm_results(results: list[dict[str, Any]], arm: str, usd_per_m: tuple[float, float, float] | None = None) -> dict[str, Any]:
    """Calculate aggregated benchmark statistics for one arm."""
    # Filter out excluded problems for recipe_examples arm
    eval_recs = [r for r in results if not (arm == "recipe_examples" and r["problem_id"] in EXCLUDED_EXAMPLE_IDS)]
    n = len(eval_recs)
    if n == 0:
        return {}

    valid_count = sum(1 for r in eval_recs if r["grade_result"].get("status") != "invalid")
    optimal_count = sum(1 for r in eval_recs if r["grade_result"].get("status") == "optimal")
    solved_count = sum(1 for r in eval_recs if r["grade_result"].get("solved") is True)
    handled_count = sum(1 for r in eval_recs if r["grade_result"].get("handled") is True)

    dual_recs = [r for r in eval_recs if "dual_ok" in r["grade_result"]]
    dual_ok_count = sum(1 for r in dual_recs if r["grade_result"].get("dual_ok") is True)
    dual_of_correct_primal = sum(1 for r in dual_recs if r["grade_result"].get("dual_ok") is True and r["grade_result"].get("objective_ok") is True)

    read_recs = [r for r in eval_recs if r.get("turn2") and r["turn2"].get("reading_grade")]
    reading_ok_count = sum(1 for r in read_recs if r["turn2"]["reading_grade"].get("reading_ok") is True)

    missing_nonneg_count = sum(1 for r in eval_recs if r["grade_result"].get("missing_nonneg") is True)
    invented_counts = [len(r["grade_result"].get("invented_numbers", [])) for r in eval_recs]

    total_tokens = sum(r["tokens"].get("prompt_tokens", 0) + r["tokens"].get("completion_tokens", 0) for r in eval_recs)

    agg = {
        "n_problems": n,
        "valid_rate": round(valid_count / n, 4),
        "optimal_rate": round(optimal_count / n, 4),
        "solved_rate": round(solved_count / n, 4),
        "handled_incomplete_rate": round(handled_count / n, 4),
        "invented_numbers_mean": round(sum(invented_counts) / n, 2),
        "missing_nonneg_rate": round(missing_nonneg_count / n, 4),
        "dual_ok_rate": round(dual_ok_count / len(dual_recs), 4) if dual_recs else None,
        "dual_of_correct_primal_rate": round(dual_of_correct_primal / len(dual_recs), 4) if dual_recs else None,
        "reading_ok_rate": round(reading_ok_count / len(read_recs), 4) if read_recs else None,
        "tokens_per_problem": round(total_tokens / n, 1),
    }

    if usd_per_m:
        p_in, p_cached, p_out = usd_per_m
        prompt_tok = sum(r["tokens"].get("prompt_tokens", 0) for r in eval_recs)
        compl_tok = sum(r["tokens"].get("completion_tokens", 0) for r in eval_recs)
        cost = (prompt_tok * p_in + compl_tok * p_out) / 1e6
        agg["cost_usd"] = round(cost, 4)

    return agg


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--model", required=True)
    p.add_argument("--base", default=None)
    p.add_argument("--key-var", default="MODEL_PROXY_API_KEY")
    p.add_argument("--env", nargs="+", default=[str(ROOT.parent / ".env")])
    p.add_argument("--max-tokens", type=int, default=8192)
    p.add_argument("--concurrency", type=int, default=2)
    p.add_argument("--out", default=str(ROOT / "results" / "sheets"))
    p.add_argument("--arms", default="alone,recipe,recipe_examples")
    p.add_argument("--ids", default=None, help="Comma-separated problem IDs to evaluate")
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--language", default="es", choices=["es", "en"])
    p.add_argument("--usd-per-m", type=float, nargs=3, default=None)
    p.add_argument("--gpu-usd-per-s", type=float, default=0.0)
    p.add_argument("--problems-file", default=None)
    a = p.parse_args()

    for env_file in a.env:
        _load_dotenv(Path(env_file))

    api_key = os.environ.get(a.key_var)
    if not api_key:
        sys.exit(f"Missing API key variable {a.key_var} in environment")

    # Configure client
    from openai import OpenAI
    client = OpenAI(base_url=a.base, api_key=api_key)

    all_probs = load_problems(a.problems_file)
    if a.ids:
        selected_ids = set(a.ids.split(","))
        probs = [p for p in all_probs if p["id"] in selected_ids]
    else:
        probs = all_probs

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^\w\-]", "_", a.model.split("/")[-1])

    summary: dict[str, Any] = {"model": a.model, "arms": {}}

    for arm in a.arms.split(","):
        arm = arm.strip()
        print(f"Running arm '{arm}' for model {a.model}...", flush=True)
        results = []

        with ThreadPoolExecutor(max_workers=a.concurrency) as executor:
            futures = [
                executor.submit(evaluate_problem, client, a.model, prob, arm, language=a.language, max_tokens=a.max_tokens)
                for prob in probs
            ]
            for fut in as_completed(futures):
                res = fut.result()
                results.append(res)
                g = res["grade_result"]
                print(f"  [{res['problem_id']}] status={g.get('status')} solved={g.get('solved')} invented={len(g.get('invented_numbers', []))}", flush=True)

        # Save arm detailed results
        arm_out = out / f"{slug}_{arm}.json"
        arm_out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

        agg = aggregate_arm_results(results, arm, usd_per_m=tuple(a.usd_per_m) if a.usd_per_m else None)
        summary["arms"][arm] = agg
        print(f"Arm '{arm}' complete: solved_rate={agg.get('solved_rate')}, optimal_rate={agg.get('optimal_rate')}", flush=True)

    summary_file = out / f"{slug}_summary.json"
    summary_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Summary saved to {summary_file}")


if __name__ == "__main__":
    main()
