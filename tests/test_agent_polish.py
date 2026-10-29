"""Tests for SPEC-15: Agent answers polish with localized fortnights, stretch rates, and percentages."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dora.engine import optimize
from dora.scenario import Scenario, fortnight_name
from dora.tools import evaluate_season, shadow_prices
from dora.verifier import verify


def test_fortnight_name_spanish():
    # 1. fortnight_name(21, "es") returns a Spanish name; fortnight_name(21) is unchanged.
    assert fortnight_name(21, "es") == "2ª quincena de mar"
    assert fortnight_name(21) == "late Mar"
    assert fortnight_name(0, "es") == "1ª quincena de may"
    assert fortnight_name(0) == "early May"
    assert fortnight_name(24, "es") == "1ª quincena de may (año 2)"
    assert fortnight_name(24) == "early May (year 2)"


def test_evaluate_season_spanish_fortnights():
    # 2. evaluate_season({... "lang": "es"}) has no English month abbreviations in any fortnight field.
    res = evaluate_season({"area_ha": 500, "own_capital_usd": 50000, "lang": "es"})

    english_indicators = ["early", "late", "Dec", "Aug", "Jan", "Feb", "Apr", "Oct", "Nov"]

    def _check(obj, path=""):
        if isinstance(obj, str):
            if "fortnight" in path.lower() or "month" in path.lower():
                for ind in english_indicators:
                    assert ind not in obj, f"Found English indicator '{ind}' in {path}: '{obj}'"
        elif isinstance(obj, dict):
            for k, v in obj.items():
                _check(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                _check(v, f"{path}[{i}]")

    _check(res)
    assert res["max_credit_fortnight"] == "1ª quincena de dic"
    assert any("quincena" in fn for fn in res["fortnights_with_scarce_capital"])


def test_stretch_rate_calculation():
    # 3. For the base Balcarce scenario, the stretch rate equals λ_start / λ_end − 1 computed from cash_value.
    sc = Scenario(area_ha=500, own_capital_usd=50000, region="southeast_buenos_aires")
    r = optimize(sc)
    stretches = r.get_capital_stretches()
    assert len(stretches) > 0

    first = stretches[0]
    s = first["start_fortnight_idx"]
    e = first["end_fortnight_idx"]
    expected_rate = r.cash_value[s] / r.cash_value[e] - 1.0

    assert abs(first["rate_for_stretch"] - expected_rate) < 1e-4
    assert first["rate_for_stretch_pct"] == round(expected_rate * 100.0, 1)
    assert first["capital_shadow_price_today"] == round(float(r.capital_shadow_price), 4)


def test_return_on_capital_percentage():
    # 4. return_on_capital_pct = round(100 × return_on_capital, 1).
    res = evaluate_season({"area_ha": 500, "own_capital_usd": 50000})
    assert "return_on_capital_pct" in res
    assert res["return_on_capital_pct"] == round(100.0 * res["return_on_capital"], 1)
    assert "return_on_capital_and_land_pct" in res
    assert res["return_on_capital_and_land_pct"] == round(100.0 * res["return_on_capital_and_land"], 1)


def test_verifier_accepts_percentage_and_fraction():
    # 5. The verifier accepts "12,3%" when a tool returned 12.3 (pct field) and when it returned 0.123 (share).
    res_pct = [{"return_pct": 12.3}]
    problems_pct = verify("El rendimiento obtenido fue de 12,3%.", res_pct, [])
    assert len(problems_pct) == 0

    res_share = [{"return": 0.123}]
    problems_share = verify("El rendimiento obtenido fue de 12,3%.", res_share, [])
    assert len(problems_share) == 0

    # It rejects an invented percentage
    problems_fake = verify("El rendimiento obtenido fue de 45,6%.", res_share, [])
    assert len(problems_fake) == 1
    assert problems_fake[0].text == "45,6%"


def test_eval_answers_contain_q31_to_q36():
    # 6. The new eval questions have answers in answers.jsonl.
    answers_path = Path(__file__).resolve().parent.parent / "eval" / "answers.jsonl"
    assert answers_path.exists()

    answers = {}
    with open(answers_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                answers[data["id"]] = data

    for qid in ("q31", "q32", "q33", "q34", "q35", "q36"):
        assert qid in answers, f"Question {qid} is missing from answers.jsonl"
        assert answers[qid]["expected_value"] is not None
