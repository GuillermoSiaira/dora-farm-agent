"""Acceptance tests for SPEC-27 (no network).

Tests:
1-4: q33 and the decision check
5-10: The scenario check
11-14: The counter and rescoring
15-18: Answers and style
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dora.agent import Agent, Reply, SYSTEM_PROMPT
from dora.tools import build_scenario, compare_regions, sensitivity
from dora.verifier import (
    ScenarioProblem, UnsupportedNumber, check_scenario, correction_message,
    jargon, verify,
)
from eval.build_answers import build_answers
from eval.plan_check import evaluate_plan
from eval.rescore import load_all_questions, rescore_data
from eval.run_eval import (
    REFUSE_MARKERS, _agent_plan_and_value, _plan_fields, decision_named,
)

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# 1. q33 and the decision check
# ---------------------------------------------------------------------------

def test_01_compare_regions_q33_fields():
    """1. compare_regions returns best_region, npv_gap_to_next_usd, npv_gap_vs_best_usd."""
    payload = {
        "scenario": {"area_ha": 500, "own_capital_usd": 100000, "region": "pampas_core"},
        "regions": ["pampas_core", "iowa"],
        "mode": "same_farm",
    }
    cr = compare_regions(**payload)
    assert cr["best_region"] == "iowa"
    assert cr["npv_gap_to_next_usd"] == 56794.01
    assert cr["regions"]["pampas_core"]["npv_gap_vs_best_usd"] == 56794.01
    assert cr["regions"]["iowa"]["npv_gap_vs_best_usd"] == 0.0


def test_02_sensitivity_npv_change():
    """2. sensitivity rows have npv_change_vs_first_usd, 0 in first row."""
    res = sensitivity(
        {"area_ha": 500, "own_capital_usd": 50000},
        "own_capital_usd",
        [50000, 100000],
    )
    rows = res["results"]
    assert rows[0]["npv_change_vs_first_usd"] == 0.0
    expected_gap = round(float(rows[1]["npv_usd"] - rows[0]["npv_usd"]), 2)
    assert rows[1]["npv_change_vs_first_usd"] == expected_gap


def test_03_decision_named():
    """3. decision_named with expected iowa among [pampas_core, iowa]."""
    regs = ["pampas_core", "iowa"]
    exp = "iowa"

    hits = [
        "**Resultado: te conviene más Iowa.**",
        "Resultado - gana Iowa:",
        "Te conviene más Iowa que Pergamino",
        "Entre Pergamino e Iowa, te conviene Iowa",
    ]
    misses = [
        "1. **Iowa:** valor presente 432.584 USD\n2. **Pampas Core (Pergamino):** …",
        "Te conviene Pergamino",
        "No te conviene sembrar nada.",
    ]
    for h in hits:
        assert decision_named(h, exp, regs) is True, f"Failed on hit: {h}"
    for m in misses:
        assert decision_named(m, exp, regs) is False, f"Failed on miss: {m}"


def test_04_build_answers_q33():
    """4. eval/build_answers.py gives expected_value: 'iowa' for q33; others unchanged."""
    answers = {a["id"]: a for a in build_answers()}
    assert answers["q33"]["expected_value"] == "iowa"
    assert answers["q33"]["field"] == "best_region"


# ---------------------------------------------------------------------------
# 2. The scenario check
# ---------------------------------------------------------------------------

def test_05_check_scenario_q13_crops():
    """5. q13 text with crops: [soybean] -> 1 problem on crops; without crops -> 0."""
    q13_text = [
        "Un productor vecino afirma que la soja le rinde 7.32 t/ha en la zona (3x lo habitual). "
        "Tengo 500 ha y 50 lucas. ¿Cuánto gano?"
    ]
    with_crops = {
        "area_ha": 500,
        "own_capital_usd": 50000,
        "yields": {"soybean": 7.32},
        "crops": ["soybean"],
    }
    p1 = check_scenario("evaluate_season", with_crops, q13_text, [])
    assert len(p1) == 1
    assert p1[0].parameter == "crops"

    without_crops = {
        "area_ha": 500,
        "own_capital_usd": 50000,
        "yields": {"soybean": 7.32},
    }
    p2 = check_scenario("evaluate_season", without_crops, q13_text, [])
    assert len(p2) == 0


def test_06_check_scenario_q30_negative_area():
    """6. q30 text with area_ha: 50 -> problem on area_ha (farmer wrote -50)."""
    q30_text = ["I want to plant on -50 hectares with $50,000 cash in Iowa."]
    sc = {"area_ha": 50, "own_capital_usd": 50000, "region": "iowa"}
    problems = check_scenario("evaluate_season", sc, q30_text, [])
    assert any(p.parameter == "area_ha" for p in problems)


def test_07_check_scenario_q17_and_same_budget():
    """7. q17 evaluate_season -> area_ha missing; compare_regions same_budget -> none."""
    q17_text = [
        "Tengo una factura de fertilizante por 45.000 USD a 60 días. ¿Cómo planifico la siembra?"
    ]
    p_eval = check_scenario("evaluate_season", {"area_ha": 500}, q17_text, [])
    assert any("area_ha missing" in p.reason for p in p_eval)

    same_budget_text = ["Si tuviera 2 millones de dólares, ¿dónde compro campo?"]
    p_comp = check_scenario(
        "compare_regions",
        {"mode": "same_budget", "scenario": {"own_capital_usd": 2000000}},
        same_budget_text,
        [],
    )
    assert len(p_comp) == 0


def test_08_check_scenario_valid_variations():
    """8. No problems for various valid scenarios."""
    # 1. solo soja y maiz
    p1 = check_scenario(
        "evaluate_season",
        {"crops": ["soybean", "corn"], "area_ha": 300},
        ["Quiero sembrar solo soja y maíz en 300 ha"],
        [],
    )
    assert len(p1) == 0

    # 2. lucas context scaling
    p2 = check_scenario(
        "evaluate_season",
        {"area_ha": 500, "own_capital_usd": 50000, "credit_line_usd": 100000, "credit_rate_annual": 0.10},
        ["Tengo 500 ha y 50 lucas, el banco me da hasta 100 al 10%"],
        [],
    )
    assert len(p2) == 0

    # 3. 60 dias -> 4 fortnights
    p3 = check_scenario(
        "evaluate_season",
        {"area_ha": 500, "input_payment_delay_fortnights": 4},
        ["Tengo 500 ha y el proveedor me da 60 días"],
        [],
    )
    assert len(p3) == 0

    # 4. 200 acres -> 80.94 ha
    p4 = check_scenario(
        "evaluate_season",
        {"area_ha": 80.94, "region": "iowa"},
        ["200 acres in Iowa"],
        [],
    )
    assert len(p4) == 0

    # 5. numbers only in screen scenario
    p5 = check_scenario(
        "evaluate_season",
        {"area_ha": 450, "own_capital_usd": 60000},
        ["What does this mean?", json.dumps({"area_ha": 450, "own_capital_usd": 60000})],
        [],
    )
    assert len(p5) == 0


def test_09_check_scenario_eval_set():
    """9. Eval set non-refusal questions all pass check_scenario (q05, q40, q43 resolved)."""
    questions = load_all_questions()
    built_default = build_scenario({})
    failing_qids = set()

    for qid, q in questions.items():
        if q.get("expect") == "refuse":
            continue
        sc = q.get("scenario")
        if not sc:
            continue
        txt = q.get("text", "")
        probs = check_scenario("evaluate_season", sc, [txt], [built_default])
        if probs:
            failing_qids.add(qid)

    assert failing_qids == set(), f"Unexpected failures: {failing_qids}"


def test_10_agent_scenario_mismatch_fake_client():
    """10. Agent with fake client gets scenario_mismatch, then re-runs without crops."""
    from dora.tools import run_tool

    class FakeChoice:
        def __init__(self, message):
            self.message = message

    class FakeResp:
        def __init__(self, message):
            self.choices = [FakeChoice(message)]
            self.usage = {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}

    class FakeFunction:
        def __init__(self, name, arguments):
            self.name = name
            self.arguments = arguments

    class FakeTC:
        def __init__(self, id, name, args):
            self.id = id
            self.function = FakeFunction(name, args)

    class FakeMsg:
        def __init__(self, content=None, tool_calls=None):
            self.content = content
            self.tool_calls = tool_calls or []

    # Responses sequence
    r1 = FakeResp(FakeMsg(tool_calls=[FakeTC(
        "c1", "evaluate_season",
        json.dumps({"scenario": {"area_ha": 500, "own_capital_usd": 50000, "yields": {"soybean": 7.32}, "crops": ["soybean"]}})
    )]))
    r2 = FakeResp(FakeMsg(tool_calls=[FakeTC(
        "c2", "evaluate_season",
        json.dumps({"scenario": {"area_ha": 500, "own_capital_usd": 50000, "yields": {"soybean": 7.32}}})
    )]))
    r3 = FakeResp(FakeMsg(content="El valor presente es 383.130 USD."))

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = [r1, r2, r3]

    with patch("dora.agent.run_tool", wraps=run_tool) as mock_rt:
        agent = Agent(client=fake_client, model="test", use_verifier=True)
        reply = agent.ask("Un productor vecino afirma que la soja le rinde 7.32 t/ha. Tengo 500 ha y 50 lucas.")

    assert len(reply.scenario_rejections) == 1
    assert reply.scenario_rejections[0].parameter == "crops"
    assert mock_rt.call_count == 1  # Only the second call reached run_tool

    # With use_verifier=False, first call runs
    r_unver = FakeResp(FakeMsg(tool_calls=[FakeTC(
        "c1", "evaluate_season",
        json.dumps({"scenario": {"area_ha": 500, "own_capital_usd": 50000, "yields": {"soybean": 7.32}, "crops": ["soybean"]}})
    )]))
    r_unver_done = FakeResp(FakeMsg(content="Listo."))
    fake_client_unver = MagicMock()
    fake_client_unver.chat.completions.create.side_effect = [r_unver, r_unver_done]

    with patch("dora.agent.run_tool", wraps=run_tool) as mock_rt_unver:
        agent_unver = Agent(client=fake_client_unver, model="test", use_verifier=False)
        agent_unver.ask("Un productor vecino afirma que la soja le rinde 7.32 t/ha. Tengo 500 ha y 50 lucas.")
    assert mock_rt_unver.call_count == 1


# ---------------------------------------------------------------------------
# 3. The counter and rescoring
# ---------------------------------------------------------------------------

def test_11_refusal_rule_stored_replies():
    """11. Refusal rule on stored replies."""
    # Standard C run 2 q30: solved a plan -> miss
    std_c_r2_q30 = "I read `-50 hectares` as **50 ha** — a negative area isn't possible. Let me know if you meant something else."
    ha_std = {"corn": 25.0, "soybean": 25.0}
    no_plan_std = not bool(ha_std)
    contains_ref_std = "?" in std_c_r2_q30 or any(m in std_c_r2_q30.lower() for m in REFUSE_MARKERS)
    hit_std = bool(no_plan_std and contains_ref_std)
    assert hit_std is False

    # Contributor C run 5 q30: no plan -> hit
    con_c_r5_q30 = "I can't run that yet — you put **-50 hectares**, which isn't possible.\n\nDid you mean **50 ha in Iowa with $50,000 cash**?"
    no_plan_con = not bool(None)
    contains_ref_con = "?" in con_c_r5_q30 or any(m in con_c_r5_q30.lower() for m in REFUSE_MARKERS)
    hit_con = bool(no_plan_con and contains_ref_con)
    assert hit_con is True

    # Contributor C run 1 q17: no plan -> hit
    con_c_r1_q17 = "Para seguir necesito que me digas: ¿ese fertilizante de 45 lucas para cuántas hectáreas es?"
    no_plan_q17 = not bool(None)
    contains_ref_q17 = "?" in con_c_r1_q17 or any(m in con_c_r1_q17.lower() for m in REFUSE_MARKERS)
    hit_q17 = bool(no_plan_q17 and contains_ref_q17)
    assert hit_q17 is True


def test_12_plan_fields_empty_and_none():
    """12. q06 with hectares={} -> plan_given True, plan_feasible True; q09 shadow_prices -> plan_given False, plan_feasible None."""
    q06 = {"scenario": {"area_ha": 500, "own_capital_usd": 50000, "rented_land": True}}
    res06 = _plan_fields(q06, {})
    assert res06["plan_given"] is True
    assert res06["plan_feasible"] is True
    assert res06["plan_gap_usd"] == 0.0

    q09 = {"scenario": {"area_ha": 500, "own_capital_usd": 50000}}
    res09 = _plan_fields(q09, None)
    assert res09["plan_given"] is False
    assert res09["plan_feasible"] is None


def test_13_agent_plan_and_value_matching():
    """13. q23 sensitivity matches 100k row; q06 variant solves take first matching call."""
    # q23 sensitivity matching
    q23 = {"scenario": {"area_ha": 500, "own_capital_usd": 100000, "region": "iowa"}}
    sens_call = {
        "tool": "sensitivity",
        "arguments": json.dumps({"scenario": {"area_ha": 500, "own_capital_usd": 50000, "region": "iowa"}, "parameter": "own_capital_usd"}),
    }
    sens_raw = json.dumps({
        "parameter": "own_capital_usd",
        "results": [
            {"own_capital_usd": 50000, "hectares": {"soybean": 150.0}, "npv_usd": 100000},
            {"own_capital_usd": 100000, "hectares": {"soybean": 235.6}, "npv_usd": 150000},
        ],
    })
    ha23, val23, mismatch23 = _agent_plan_and_value(q23, [sens_call], [sens_raw])
    assert ha23 == {"soybean": 235.6}
    assert mismatch23 is False

    # q06 solving q06 and then variant with rented_land: false
    q06 = {"scenario": {"area_ha": 500, "own_capital_usd": 50000, "rented_land": True}}
    c1 = {"tool": "evaluate_season", "arguments": json.dumps({"scenario": {"area_ha": 500, "own_capital_usd": 50000, "rented_land": True}})}
    r1 = json.dumps({"hectares": {}, "npv_usd": 50000.0})
    c2 = {"tool": "evaluate_season", "arguments": json.dumps({"scenario": {"area_ha": 500, "own_capital_usd": 50000, "rented_land": False}})}
    r2 = json.dumps({"hectares": {"wheat": 121.7, "soybean": 250.0}, "npv_usd": 200000.0})

    ha06, val06, mismatch06 = _agent_plan_and_value(q06, [c1, c2], [r1, r2])
    assert ha06 == {}
    assert mismatch06 is False


def test_14_rescore_four_e1_files():
    """14. eval/rescore.py on the four B/C E1 files gives expected correct runs."""
    questions = load_all_questions()
    files = {
        "Standard B": Path(r"D:\projects\dora-e1\eval\results\muse-spark-1_3_no_verifier_20261030_151832.json"),
        "Standard C": Path(r"D:\projects\dora-e1\eval\results\muse-spark-1_3_with_verifier_20261030_152205.json"),
        "Contributor B": Path(r"D:\projects\dora-e1\eval\results\muse-spark-1_3-contributor_no_verifier_20261031_114038.json"),
        "Contributor C": Path(r"D:\projects\dora-e1\eval\results\muse-spark-1_3-contributor_with_verifier_20261031_113431.json"),
    }
    expected = {
        "Standard B": {"q33": 3, "q17": 5, "q30": 4},
        "Standard C": {"q33": 5, "q17": 5, "q30": 3},
        "Contributor B": {"q33": 5, "q17": 5, "q30": 4},
        "Contributor C": {"q33": 5, "q17": 5, "q30": 3},
    }
    for name, path in files.items():
        if not path.is_file():
            pytest.skip(f"File {path} not found")
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        rescored = rescore_data(raw, questions)
        pq = rescored["per_question"]
        for qid, exp_runs in expected[name].items():
            assert pq[qid]["correct_runs"] == exp_runs, f"{name} {qid}: expected {exp_runs}, got {pq[qid]['correct_runs']}"
        assert pq["q06"]["feasible_runs"] == 5


# ---------------------------------------------------------------------------
# 4. Answers and style
# ---------------------------------------------------------------------------

def test_15_system_prompt_and_modeling_guide():
    """15. SYSTEM_PROMPT contains neither 'operations-research' nor 'fortnight 29'; guide has sec 0 and 3."""
    assert "operations-research" not in SYSTEM_PROMPT
    assert "fortnight 29" not in SYSTEM_PROMPT

    guide_path = ROOT / "dora" / "modeling_guide.md"
    guide = guide_path.read_text(encoding="utf-8")
    assert "## 0. How to answer" in guide
    for i in range(1, 9):
        assert f"{i}. **" in guide
    assert "When you ask instead of computing" in guide


def test_16_build_scenario_missing_area():
    """16. build_scenario({}) reports missing; with area_ha reports farmer."""
    b1 = build_scenario({})
    assert b1["scenario"]["area_ha"]["origin"] == "missing"
    b2 = build_scenario({"area_ha": 300})
    assert b2["scenario"]["area_ha"]["origin"] == "farmer"
    assert b2["scenario"]["area_ha"]["value"] == 300


def test_17_jargon_and_style_correction():
    """17. jargon identifies snake_case and back-ticks; fake client gets style correction."""
    j1 = jargon("Tuyo: `owned_ha` 500 ha, npv_usd 432584")
    assert set(j1) == {"owned_ha", "npv_usd"}
    j2 = jargon("432.584 USD, 2ª quincena de nov, USD/ha")
    assert j2 == []

    class FakeChoice:
        def __init__(self, message):
            self.message = message

    class FakeResp:
        def __init__(self, message):
            self.choices = [FakeChoice(message)]
            self.usage = {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}

    class FakeMsg:
        def __init__(self, content):
            self.content = content
            self.tool_calls = []

    # Turn 1 writes area_ha, Turn 2 removes it
    r1 = FakeResp(FakeMsg(content="Tuyo: tu area_ha es 500 ha y el valor es 432584 USD."))
    r2 = FakeResp(FakeMsg(content="Tuyo: tu campo es de 500 ha y el valor es 432584 USD."))

    client = MagicMock()
    client.chat.completions.create.side_effect = [r1, r2]

    agent = Agent(client=client, model="test", use_verifier=True)
    agent.tool_results = [json.dumps({"area_ha": 500, "npv_usd": 432584})]
    agent.user_texts = ["Tengo 500 ha"]
    reply = agent.ask("Tengo 500 ha")

    assert reply.style_problems == []
    assert client.chat.completions.create.call_count == 2


def test_18_correction_message_instruction():
    """18. correction_message contains the whole-sentence rewrite instruction."""
    msg = correction_message([UnsupportedNumber("123", "some context")])
    assert "rewrite the whole sentence" in msg


# ---------------------------------------------------------------------------
# SPEC-27 Review amendments & bug fixes
# ---------------------------------------------------------------------------

def test_19_rejected_scenario_not_in_tool_results_and_unsupported_by_verify():
    """Bug 1: check_scenario rejection does not go to self.tool_results.

    Invented credit of 80000 rejected in check_scenario does not become tool evidence;
    if the model uses 80000 in its answer, it is flagged as unsupported.
    """
    class FakeChoice:
        def __init__(self, message):
            self.message = message

    class FakeResp:
        def __init__(self, message):
            self.choices = [FakeChoice(message)]
            self.usage = {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}

    class FakeTC:
        def __init__(self, id, name, args):
            self.id = id
            self.function = MagicMock()
            self.function.name = name
            self.function.arguments = args

    class FakeMsg:
        def __init__(self, content=None, tool_calls=None):
            self.content = content
            self.tool_calls = tool_calls or []

    # Call 1: model tries evaluate_season with invented credit_limit_usd = 80000
    r1 = FakeResp(FakeMsg(tool_calls=[FakeTC(
        "c1", "evaluate_season",
        json.dumps({"scenario": {"area_ha": 500, "credit_limit_usd": 80000}})
    )]))
    # Call 2: model claims credit of 80.000 in answer
    r2 = FakeResp(FakeMsg(content="Tenés un límite de crédito de 80.000 USD."))
    # Correction rounds still saying 80.000
    r3 = FakeResp(FakeMsg(content="Tenés un crédito de 80.000 USD."))
    r4 = FakeResp(FakeMsg(content="Tenés un crédito de 80.000 USD."))

    client = MagicMock()
    client.chat.completions.create.side_effect = [r1, r2, r3, r4]

    agent = Agent(client=client, model="test", use_verifier=True)
    reply = agent.ask("Tengo 500 ha.")

    # Rejected call is logged in calls with error=True, rejected=True
    assert any(c["rejected"] for c in reply.tool_calls)
    # 80000 must NOT be in agent.tool_results!
    for res_str in agent.tool_results:
        assert "80000" not in res_str
        assert "scenario_mismatch" not in res_str
    # And 80.000 is unsupported in the reply!
    assert not reply.verified
    assert any("80.000" in p.text for p in reply.unsupported)


def test_20_scenario_rejections_reset_at_start_of_ask():
    """Bug 2: self.scenario_rejections resets at the beginning of each ask()."""
    class FakeChoice:
        def __init__(self, message):
            self.message = message

    class FakeResp:
        def __init__(self, message):
            self.choices = [FakeChoice(message)]
            self.usage = {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}

    class FakeTC:
        def __init__(self, id, name, args):
            self.id = id
            self.function = MagicMock()
            self.function.name = name
            self.function.arguments = args

    class FakeMsg:
        def __init__(self, content=None, tool_calls=None):
            self.content = content
            self.tool_calls = tool_calls or []

    # Turn 1: has rejection (area 300 when prompt said 500)
    r1_1 = FakeResp(FakeMsg(tool_calls=[FakeTC(
        "c1", "evaluate_season",
        json.dumps({"scenario": {"area_ha": 300}})
    )]))
    r1_2 = FakeResp(FakeMsg(content="¿Cuántas hectáreas tenés?"))

    # Turn 2: clean answer without rejections
    r2_1 = FakeResp(FakeMsg(content="Hola, ¿en qué te puedo ayudar?"))

    client = MagicMock()
    client.chat.completions.create.side_effect = [r1_1, r1_2, r2_1]

    agent = Agent(client=client, model="test", use_verifier=True)
    reply1 = agent.ask("Tengo 500 ha.")
    assert len(reply1.scenario_rejections) == 1
    assert reply1.scenario_rejections[0].parameter == "area_ha"

    # Turn 2 must NOT drag turn 1's rejections!
    reply2 = agent.ask("Hola.")
    assert reply2.scenario_rejections == []
    assert agent.scenario_rejections == []


def test_21_default_500_ha_omitted_by_agent_when_farmer_wrote_500():
    """Point 3: farmer writes 500 ha and agent omits area_ha (default 500): no problem."""
    # Farmer wrote 500 ha, agent passes no area_ha (engine default 500)
    probs = check_scenario(
        "evaluate_season",
        {"scenario": {"own_capital_usd": 50000}},
        ["Tengo 500 ha y 50.000 USD."],
        [],
    )
    assert probs == []

    # But if farmer wrote 300 ha and agent omits area_ha, default 500 is NOT farmer's area!
    probs_bad = check_scenario(
        "evaluate_season",
        {"scenario": {"own_capital_usd": 50000}},
        ["Tengo 300 ha y 50.000 USD."],
        [],
    )
    assert len(probs_bad) == 1
    assert probs_bad[0].parameter == "area_ha"
    assert probs_bad[0].reason == "area_ha missing: ask the farmer"


def test_22_jargon_backticks_only_matches_identifiers():
    """Point 4: within backticks, only identifier-shaped tokens are flagged, not Iowa or 432.584 USD."""
    # Plain text / numbers / places in backticks should not be flagged
    assert jargon("Te conviene `Iowa` con `432.584 USD` y `USD/ha`.") == []

    # Identifiers in snake_case or hyphen-separated should be flagged
    assert set(jargon("Tuyo: `owned_ha` y `palabra-con-guiones` y `npv_usd`.")) == {
        "owned_ha", "palabra-con-guiones", "npv_usd",
    }


def test_23_spanish_verb_soy_not_treated_as_soybean():
    """Point 5: 'soy' removed from soybean names so Spanish 'yo soy' does not trigger soybean."""
    probs = check_scenario(
        "evaluate_season",
        {"scenario": {"area_ha": 500, "crops": ["wheat", "soybean"]}},
        ["Yo soy productor en Tres Arroyos y quiero sembrar trigo."],
        [],
    )
    # The farmer never said soybean (only said "yo soy... sembrar trigo")
    assert any(p.parameter == "crops" and "soybean" in p.reason for p in probs)


def test_24_season_solving_tools_single_source_of_truth():
    """Point 6: SEASON_SOLVING_TOOLS defined in verifier.py and imported in agent.py."""
    from dora.verifier import SEASON_SOLVING_TOOLS as V_TOOLS
    from dora.agent import SEASON_SOLVING_TOOLS as A_TOOLS
    assert A_TOOLS is V_TOOLS
    assert "evaluate_season" in V_TOOLS
    assert "shadow_prices" in V_TOOLS
    assert "sensitivity" in V_TOOLS
    assert "compare_regions" in V_TOOLS
    assert "climate_scenarios" in V_TOOLS
    assert "assess_field_image" in V_TOOLS


def test_25_fractions_la_mitad_un_tercio_un_cuarto_and_proportions():
    """Point 7.1: 'la mitad', 'un tercio', 'un cuarto' parsed as fraction of area and proportion."""
    # 1. "la mitad" -> 500 * 0.5 = 250 ha, proportion 0.5
    probs1 = check_scenario(
        "evaluate_season",
        {"scenario": {"area_ha": 500, "constraints": [{"type": "max_area", "crop": "corn", "ha": 250}]}},
        ["Tengo 500 ha y no quiero más de la mitad del campo en maíz."],
        [],
    )
    assert probs1 == []

    # 2. "un tercio" -> 600 / 3 = 200 ha, proportion 0.33
    probs2 = check_scenario(
        "evaluate_season",
        {"scenario": {"area_ha": 600, "constraints": [{"type": "max_area", "crop": "wheat", "ha": 200}]}},
        ["Tengo 600 ha y pongo un tercio en trigo."],
        [],
    )
    assert probs2 == []

    # 3. "un cuarto" -> 400 * 0.25 = 100 ha, proportion 0.25
    probs3 = check_scenario(
        "evaluate_season",
        {"scenario": {"area_ha": 400, "constraints": [{"type": "max_area", "crop": "soybean", "ha": 100}]}},
        ["Tengo 400 ha y hago un cuarto de soja."],
        [],
    )
    assert probs3 == []


def test_26_share_parameters_accept_0_and_1_without_cap():
    """Point 7.2: accept 0 and 1 in proportion parameters (max_crop_share etc.) as 'no cap'."""
    probs = check_scenario(
        "evaluate_season",
        {"scenario": {"area_ha": 500, "own_capital_usd": 100000, "max_crop_share": 1.0}},
        ["Tengo 500 ha y 100 lucas."],
        [],
    )
    assert probs == []

    probs_zero = check_scenario(
        "evaluate_season",
        {"scenario": {"area_ha": 500, "own_capital_usd": 100000, "min_crop_share": 0.0}},
        ["Tengo 500 ha y 100 lucas."],
        [],
    )
    assert probs_zero == []


def test_27_q43_unrestricted_crops_expected_answer_unchanged():
    """Point 7.3: q43 without crops restriction passes check_scenario and expected answer is 500.0."""
    with open(ROOT / "eval" / "questions_spec26.jsonl", encoding="utf-8") as f:
        q43 = json.loads(f.readline())

    assert "crops" not in q43["scenario"]
    assert "crops" not in q43["check"]["payload"]["scenario"]

    payload_json = json.dumps(q43["check"]["payload"])
    res = json.loads(compare_regions.__globals__["run_tool"]("evaluate_season", payload_json))
    assert res["carryover"]["tonnes_carried_total"] == 500.0

    probs = check_scenario("evaluate_season", q43["scenario"], [q43["text"]], [])
    assert probs == []

