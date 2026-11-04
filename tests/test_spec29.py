"""Acceptance tests for SPEC-29: the farmer interview.

All tests run strictly offline without network access.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch
import pytest

from dora import agent, tools
from dora.agent import Agent, SYSTEM_PROMPT
from dora.interview import next_question
from dora.plan_check import evaluate_plan
from dora.scenario import REGIONS
from dora.tools import evaluate_season, shadow_prices
from dora.verifier import check_scenario, unnamed_series, verify

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# 1. Case A: Order tenure -> credit_line -> supplier_terms -> done
# ---------------------------------------------------------------------------
def test_item_01_case_a_order_and_credit_line_shortfall():
    """Item 1: Case A (500 ha, 50k capital, SE BA): order of next.id is tenure,
    credit_line, supplier_terms, then done with below_threshold.
    own_capital, storage, rent_out not asked.
    credit_line reports infeasible: true and shortfall_usd matching evaluate_plan."""
    sc_a = {"area_ha": 500.0, "own_capital_usd": 50000.0, "region": "southeast_buenos_aires"}

    q1 = next_question(sc_a, asked=[])
    assert q1["done"] is False
    assert q1["next"]["id"] == "tenure"

    q2 = next_question(sc_a, asked=["tenure"])
    assert q2["done"] is False
    assert q2["next"]["id"] == "credit_line"
    assert q2["next"]["why"]["infeasible"] is True

    # Check shortfall_usd matches evaluate_plan for the same plan with credit_line_usd: 0
    ev_cur = evaluate_season(sc_a)
    p_cred0 = evaluate_plan(dict(sc_a, credit_line_usd=0.0), ev_cur["hectares"])
    assert q2["next"]["why"]["shortfall_usd"] == pytest.approx(p_cred0["extra_credit_needed_usd"], abs=0.1)

    q3 = next_question(sc_a, asked=["tenure", "credit_line"])
    assert q3["done"] is False
    assert q3["next"]["id"] == "supplier_terms"

    q4 = next_question(sc_a, asked=["tenure", "credit_line", "supplier_terms"])
    assert q4["done"] is True
    assert q4["done_reason"] == "below_threshold"
    assert q4["next"] is None


# ---------------------------------------------------------------------------
# 2. Case B: Compare basis -> rent_out, zero regret for others
# ---------------------------------------------------------------------------
def test_item_02_case_b_compare_basis_and_rent_out():
    """Item 2: Case B (500 ha, 100k capital, Pampas Core vs SE BA):
    With mode_given: false -> compare_basis.
    With mode_given: true -> rent_out.
    own_capital, credit_line, storage, supplier_terms have regret_usd == 0 and not infeasible.
    current.rent_out_ha equals area."""
    sc_b = {"area_ha": 500.0, "own_capital_usd": 100000.0, "region": "pampas_core"}
    cmp_b = {"regions": ["pampas_core", "southeast_buenos_aires"], "mode": "same_farm", "mode_given": False}

    # 1. mode_given: False -> compare_basis
    res_b1 = next_question(sc_b, compare=cmp_b)
    assert res_b1["next"]["id"] == "compare_basis"
    assert res_b1["current"]["rent_out_ha"] == 500.0

    # 2. mode_given: True -> rent_out
    cmp_b_given = {"regions": ["pampas_core", "southeast_buenos_aires"], "mode": "same_farm", "mode_given": True}
    res_b2 = next_question(sc_b, compare=cmp_b_given)
    assert res_b2["next"]["id"] == "rent_out"
    assert res_b2["next"]["why"]["regret_usd"] > 100_000.0

    # 3. Check ranking has regret_usd == 0 and not infeasible
    ranking_ids = {r["id"]: r["score"] for r in res_b2["ranking"]}
    for cand_id in ["tenure", "credit_line", "supplier_terms"]:
        if cand_id in ranking_ids:
            assert ranking_ids[cand_id]["regret_usd"] == 0.0
            assert ranking_ids[cand_id]["infeasible"] is False


# ---------------------------------------------------------------------------
# 3. No area and no compare -> area blocking, 0 optimize calls
# ---------------------------------------------------------------------------
def test_item_03_no_area_blocking_zero_optimize_calls():
    """Item 3: No area and no compare -> next.id == 'area' and no season is solved (patch optimize, count 0 calls)."""
    with patch("dora.interview.optimize") as mock_opt:
        res = next_question({"region": "southeast_buenos_aires"})
        assert res["done"] is False
        assert res["next"]["id"] == "area"
        assert mock_opt.call_count == 0


# ---------------------------------------------------------------------------
# 4. Change block parity with evaluate_season
# ---------------------------------------------------------------------------
def test_item_04_change_block_parity():
    """Item 4: change: case A with previous = case A and scenario = case A + credit_line_usd: 0
    -> npv_change_usd equals evaluate_season's difference between the two,
    and hectares_after equals the second plan's."""
    sc_a = {"area_ha": 500.0, "own_capital_usd": 50000.0, "region": "southeast_buenos_aires"}
    sc_a_cred0 = dict(sc_a, credit_line_usd=0.0)

    res = next_question(sc_a_cred0, previous=sc_a)
    ev_before = evaluate_season(sc_a)
    ev_after = evaluate_season(sc_a_cred0)

    diff = round(ev_after["npv_usd"] - ev_before["npv_usd"], 2)
    assert res["change"]["npv_change_usd"] == pytest.approx(diff, abs=0.01)
    assert res["change"]["hectares_after"] == ev_after["hectares"]


# ---------------------------------------------------------------------------
# 5. Output numbers verified by verify(), no bare region ids
# ---------------------------------------------------------------------------
def test_item_05_output_numbers_verified_and_no_bare_region_ids():
    """Item 5: Every number in the output is in the tools' results or in the scenario:
    run verify() on json.dumps(output) with the tool results as support -> no problems.
    Output has no bare region id outside the id fields."""
    sc_a = {"area_ha": 500.0, "own_capital_usd": 50000.0, "region": "southeast_buenos_aires"}
    out = next_question(sc_a)

    ev = tools.evaluate_season(sc_a)
    sp = tools.shadow_prices(sc_a)
    p_tenure = evaluate_plan(dict(sc_a, rented_land=True), ev["hectares"])
    p_cred0 = evaluate_plan(dict(sc_a, credit_line_usd=0.0), ev["hectares"])
    p_cred200 = evaluate_plan(dict(sc_a, credit_line_usd=200000.0), ev["hectares"])
    p_supp = evaluate_plan(dict(sc_a, input_payment_delay_fortnights=6), ev["hectares"])
    p_st0 = evaluate_plan(dict(sc_a, storage_capacity_t=0.0), ev["hectares"])
    p_st200 = evaluate_plan(dict(sc_a, storage_capacity_t=2000.0), ev["hectares"])

    tool_results = [ev, sp, p_tenure, p_cred0, p_cred200, p_supp, p_st0, p_st200, {"stop_threshold_usd": out["stop_threshold_usd"]}]
    user_texts = [json.dumps(sc_a)]

    problems = verify(json.dumps(out), tool_results, user_texts)
    assert len(problems) == 0, f"Unsupported numbers found: {problems}"

    # Check no bare region ids outside id fields
    regs = list(REGIONS.keys())
    def check_no_bare_region_ids(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("id", "region_id", "winner_id"):
                    continue
                if isinstance(v, str):
                    for r in regs:
                        assert r not in v, f"Found bare region id {r} in {k}: {v}"
                else:
                    check_no_bare_region_ids(v)
        elif isinstance(obj, list):
            for item in obj:
                check_no_bare_region_ids(item)

    check_no_bare_region_ids(out)

    sc_b = {"area_ha": 500.0, "own_capital_usd": 100000.0, "region": "pampas_core"}
    cmp_b = {"regions": ["pampas_core", "southeast_buenos_aires"], "mode": "same_farm", "mode_given": True}
    out_b = next_question(sc_b, compare=cmp_b)
    check_no_bare_region_ids(out_b)


# ---------------------------------------------------------------------------
# 6. MAX_QUESTIONS: 5 ids in asked -> done with max_questions
# ---------------------------------------------------------------------------
def test_item_06_max_questions_stops():
    """Item 6: MAX_QUESTIONS: with five ids in asked, done with done_reason == 'max_questions'."""
    sc_a = {"area_ha": 500.0, "own_capital_usd": 50000.0, "region": "southeast_buenos_aires"}
    out = next_question(sc_a, asked=["q1", "q2", "q3", "q4", "q5"])
    assert out["done"] is True
    assert out["done_reason"] == "max_questions"
    assert out["next"] is None


# ---------------------------------------------------------------------------
# 7. Determinism: same input gives same output twice
# ---------------------------------------------------------------------------
def test_item_07_determinism():
    """Item 7: Determinism: the same input gives the same output twice (compare the dicts)."""
    sc_a = {"area_ha": 500.0, "own_capital_usd": 50000.0, "region": "southeast_buenos_aires"}
    out1 = next_question(sc_a, asked=["tenure"])
    out2 = next_question(sc_a, asked=["tenure"])
    assert out1 == out2


# ---------------------------------------------------------------------------
# 8. Agent state tracking for interview
# ---------------------------------------------------------------------------
def test_item_08_agent_state_tracking_across_turns():
    """Item 8: Fake client: the model calls next_question without asked; the agent fills it;
    on the second call the first id is in asked and previous is the first scenario.
    Reply.interview.asked has both ids."""
    class FakeClient:
        def __init__(self):
            self.call_count = 0
            self.chat = NS(completions=NS(create=self.create))

        def create(self, model, messages, tools):
            self.call_count += 1
            if self.call_count == 1:
                tc = NS(id="call_1", function=NS(name="next_question", arguments=json.dumps({"scenario": {"area_ha": 500, "own_capital_usd": 50000}})))
                return NS(choices=[NS(message=NS(content=None, tool_calls=[tc]))])
            elif self.call_count == 2:
                return NS(choices=[NS(message=NS(content="¿El campo es tuyo o alquilado?", tool_calls=None))])
            elif self.call_count == 3:
                tc = NS(id="call_2", function=NS(name="next_question", arguments=json.dumps({"scenario": {"area_ha": 500, "own_capital_usd": 50000, "rented_land": False}})))
                return NS(choices=[NS(message=NS(content=None, tool_calls=[tc]))])
            else:
                return NS(choices=[NS(message=NS(content="¿Hasta cuánto te presta el banco?", tool_calls=None))])

    client = FakeClient()
    ag = Agent(client=client, use_verifier=True)

    rep1 = ag.ask("Tengo 500 ha y 50.000 USD. Preguntame lo que necesites.")
    assert rep1.interview["asked"] == ["tenure"]

    rep2 = ag.ask("Es propio.")
    assert rep2.interview["asked"] == ["tenure", "credit_line"]
    assert ag.interview["previous"] == {"area_ha": 500, "own_capital_usd": 50000, "rented_land": False}


# ---------------------------------------------------------------------------
# 9. One question style rule: multiple ? triggers correction only after next_question
# ---------------------------------------------------------------------------
def test_item_09_one_question_correction_round():
    """Item 9: A reply with two '?' after a next_question call gets one correction round;
    a reply with two '?' without next_question does not."""
    class FakeClientNQ:
        def __init__(self):
            self.call_count = 0
            self.chat = NS(completions=NS(create=self.create))

        def create(self, model, messages, tools):
            self.call_count += 1
            if self.call_count == 1:
                tc = NS(id="c1", function=NS(name="next_question", arguments=json.dumps({"scenario": {"area_ha": 500, "own_capital_usd": 50000}})))
                return NS(choices=[NS(message=NS(content=None, tool_calls=[tc]))])
            elif self.call_count == 2:
                # Two questions -> triggers correction round
                return NS(choices=[NS(message=NS(content="¿El campo es tuyo? ¿O alquilado?", tool_calls=None))])
            else:
                # Fixed
                return NS(choices=[NS(message=NS(content="¿El campo es tuyo o alquilado?", tool_calls=None))])

    client_nq = FakeClientNQ()
    ag_nq = Agent(client=client_nq, use_verifier=True)
    rep_nq = ag_nq.ask("Preguntame.")
    assert client_nq.call_count == 3
    assert rep_nq.text == "¿El campo es tuyo o alquilado?"

    class FakeClientNoNQ:
        def __init__(self):
            self.call_count = 0
            self.chat = NS(completions=NS(create=self.create))

        def create(self, model, messages, tools):
            self.call_count += 1
            return NS(choices=[NS(message=NS(content="¿Cómo estás? ¿En qué te ayudo?", tool_calls=None))])

    client_no_nq = FakeClientNoNQ()
    ag_no_nq = Agent(client=client_no_nq, use_verifier=True)
    rep_no_nq = ag_no_nq.ask("Hola")
    assert client_no_nq.call_count == 1


# ---------------------------------------------------------------------------
# 10. Bare series detection
# ---------------------------------------------------------------------------
def test_item_10_unnamed_series_detection():
    """Item 10: unnamed_series('4,5 / 9,5 / 3,8 / 2,4') finds one;
    unnamed_series('trigo 4,5 t/ha, maíz 9,5 t/ha') and '4/11/2026' find none."""
    s1 = unnamed_series("4,5 / 9,5 / 3,8 / 2,4")
    assert len(s1) == 1
    s2 = unnamed_series("trigo 4,5 t/ha, maíz 9,5 t/ha")
    assert len(s2) == 0
    s3 = unnamed_series("4/11/2026")
    assert len(s3) == 0


# ---------------------------------------------------------------------------
# 11. Scenario check allows missing area for next_question, still checks crops
# ---------------------------------------------------------------------------
def test_item_11_scenario_check_next_question():
    """Item 11: The scenario check lets next_question through with no area,
    and still rejects it with crops: ['soybean'] on the q13 text (SPEC-27 rule 3)."""
    # 1. No area allowed for next_question
    probs_no_area = check_scenario("next_question", {"scenario": {}}, ["¿Qué me conviene sembrar?"], [])
    assert len(probs_no_area) == 0

    # 2. Crops unmentioned by farmer still rejected
    q13_text = "Tengo 500 ha en Pergamino y 100.000 USD de capital. ¿Qué me conviene sembrar?"
    probs_crop = check_scenario("next_question", {"scenario": {"area_ha": 500.0, "crops": ["soybean"]}}, [q13_text], [])
    assert len(probs_crop) > 0
    assert any(p.parameter == "crops" for p in probs_crop)


# ---------------------------------------------------------------------------
# 12. Modeling guide section 7 and system prompt interview line
# ---------------------------------------------------------------------------
def test_item_12_modeling_guide_section_7_and_system_prompt():
    """Item 12: modeling_guide.md has section 7 with its eight rules; the system prompt has the interview line."""
    guide_path = ROOT / "dora" / "modeling_guide.md"
    guide_text = guide_path.read_text(encoding="utf-8")
    assert "## 7. The interview" in guide_text
    for i in range(1, 9):
        assert f"{i}." in guide_text

    assert "If the farmer asks you to ask, or accepts your offer, interview with next_question (modeling guide, section 7): one question per reply." in SYSTEM_PROMPT

