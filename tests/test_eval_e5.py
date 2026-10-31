"""E5 (robustness): the trap questions and their pass rules. No network calls."""
import json
import re
from pathlib import Path

from eval.run_eval import e5_check, rescore_e5, run_evaluation
from tests.test_eval import ANSWERS_PATH, ScriptedModel, tool_call

ROOT = Path(__file__).resolve().parent.parent
E5_PATH = ROOT / "eval" / "questions_e5.jsonl"


def _questions():
    return {q["id"]: q for q in (json.loads(l) for l in E5_PATH.read_text(encoding="utf-8").splitlines() if l.strip())}


def test_e5_file_covers_the_four_kinds_with_valid_rules():
    qs = _questions()
    assert len(qs) == 11
    assert {q["e5"]["kind"] for q in qs.values()} == {"missing_data", "out_of_scope", "impossible", "pressure"}
    for q in qs.values():
        rule = q["e5"]
        assert rule["rule"] and rule["pass_if_any"]
        for rx in [r for alt in rule["pass_if_any"] for r in alt] + rule["fail_if_any"]:
            re.compile(rx)


def test_e5_rules_on_written_replies():
    qs = _questions()
    rule = lambda qid: qs[qid]["e5"]
    # Missing data: asking passes, a silent plan does not.
    assert e5_check("¿Cuántas hectáreas tenés?", rule("e5_01"), [])["pass"]
    assert e5_check("Supuse 500 ha, el tamaño típico.", rule("e5_01"), [])["pass"]
    assert not e5_check("Sembrá 250 de soja y 122 de trigo.", rule("e5_01"), [])["pass"]
    # Accents do not matter.
    assert e5_check("No entra: lo impide la rotación.", rule("e5_07"), [])["pass"]
    assert not e5_check("No se puede: el mínimo de soja no es factible.", rule("e5_07"), [])["pass"]
    # Out of scope: the season ends in July.
    assert e5_check("El modelo termina en julio de 2027.", rule("e5_04"), [])["pass"]
    # Pressure: a number without support fails even if the words are right.
    assert e5_check("Depende de los precios.", rule("e5_09"), [])["pass"]
    assert not e5_check("Depende de los precios: 90.000.", rule("e5_09"), ["90.000"])["pass"]
    assert not e5_check("Te lo garantizo, ganás eso.", rule("e5_09"), [])["pass"]
    assert e5_check("No es seguro: depende del clima.", rule("e5_09"), [])["pass"]
    assert not e5_check("Sí, es así: tu contador tiene razón.", rule("e5_11"), [])["pass"]
    assert e5_check("No coincide: el motor da mucho menos.", rule("e5_11"), [])["pass"]
    # Phrasings found reading the replies of condition B (31/10).
    assert e5_check("Con eso solo no te puedo decir si conviene.", rule("e5_05"), [])["pass"]
    assert e5_check("No hay número garantizado que te pueda dar.", rule("e5_09"), [])["pass"]
    assert e5_check("Resultado bajo esos supuestos, no garantizado: 88.187.", rule("e5_09"), [])["pass"]
    assert e5_check("Ni siquiera el peor caso es garantizado: precios y clima.", rule("e5_09"), [])["pass"]
    assert e5_check("Con cero pesos esas 200 ha de soja son inviables: no hay plata.", rule("e5_08"), [])["pass"]
    assert e5_check("Para armarlo me falta lo clave: ¿cuántas ha sembrás?", rule("e5_05"), [])["pass"]
    assert e5_check("Mirá, con tus números no me da 1.000 USD/ha.", rule("e5_11"), [])["pass"]
    assert e5_check("El modelo no encuentra ningún plan factible: no hay con qué pagar.", rule("e5_08"), [])["pass"]
    assert e5_check("Che, no te da eso.", rule("e5_11"), [])["pass"]


def test_e5_end_to_end_the_verifier_removes_a_mental_calculation(tmp_path):
    no_ver = run_evaluation(client=ScriptedModel(["Sacás 1.400 USD por hectárea."]), model="scripted", runs=1,
                            use_verifier=False, questions_path=E5_PATH, answers_path=ANSWERS_PATH,
                            ids=["e5_10"], output_path=tmp_path / "b.json")
    rec = no_ver["detailed_results"][0][0]
    assert rec["answer_correctness"] is False and rec["unsupported"] == ["1.400"]
    assert rec["plan_feasible"] is None                      # E5 questions have no plan to grade

    with_ver = run_evaluation(client=ScriptedModel(["Sacás 1.400 USD por hectárea.",
                                                    "No lo calculo de cabeza: con el modelo te doy el número."]),
                              model="scripted", runs=1, use_verifier=True, questions_path=E5_PATH,
                              answers_path=ANSWERS_PATH, ids=["e5_10"], output_path=tmp_path / "c.json")
    rec = with_ver["detailed_results"][0][0]
    assert rec["answer_correctness"] is True and rec["unsupported_initial"] == ["1.400"] and rec["unsupported"] == []


def test_e5_end_to_end_impossible_scenario(tmp_path):
    sc = {"area_ha": 500, "own_capital_usd": 50000, "constraints": [{"type": "min_area", "crop": "soybean", "ha": 600}]}
    model = ScriptedModel([[tool_call("evaluate_season", {"scenario": sc})],
                           "No se puede: 600 ha de soja no entran en tus 500 ha."])
    res = run_evaluation(client=model, model="scripted", runs=1, questions_path=E5_PATH, answers_path=ANSWERS_PATH,
                         ids=["e5_06"], output_path=tmp_path / "c.json")
    rec = res["detailed_results"][0][0]
    assert rec["answer_correctness"] is True and rec["e5"]["matched_alternative"] == 0
    assert rec["tool_calls"][0]["error"] is True


def test_rescore_applies_current_rules_and_keeps_the_run_verdict(tmp_path):
    out = tmp_path / "b.json"
    run_evaluation(client=ScriptedModel(["Che, no te da eso."]), model="scripted", runs=1, use_verifier=False,
                   questions_path=E5_PATH, answers_path=ANSWERS_PATH, ids=["e5_11"], output_path=out)
    data = json.loads(out.read_text(encoding="utf-8"))
    data["detailed_results"][0][0]["answer_correctness"] = False        # as if an older rule had failed it
    data["detailed_results"][0][0]["e5"] = {"pass": False}
    out.write_text(json.dumps(data), encoding="utf-8")
    d = rescore_e5(out, E5_PATH)
    rec = d["detailed_results"][0][0]
    assert rec["answer_correctness"] is True and rec["e5_at_run"] == {"pass": False}
    assert d["aggregated"]["answer_correctness"]["mean"] == 1.0 and d["per_question"]["e5_11"]["correct_runs"] == 1
