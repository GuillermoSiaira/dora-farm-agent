"""E9 (model size): the generic MCP agent and the new metrics of run_eval. No network calls."""
import json
from types import SimpleNamespace as NS

from dora import tools
from eval import mcp_agent
from eval.mcp_agent import MCPAgent, openai_tools, parse_sse, tool_payload
from eval.run_eval import run_evaluation

Q_ID = "q08"   # 400 ha, 100.000 USD: how many hectares of wheat (answer from the engine)


class FakeMCP:
    """The engine's tools run locally, wrapped as the MCP server wraps them ({result, provenance})."""

    def __init__(self):
        self.calls = []

    def initialize(self):
        return "Call check_text on any answer."

    def tools(self):
        return [{"name": n, "description": n, "inputSchema": {"type": "object"}} for n in mcp_agent.ENGINE_TOOLS]

    def resource(self, uri):
        return "guide"

    def call(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "check_text":
            from dora.verifier import verify
            results = [json.dumps(r["result"]) for r in arguments["results"]]
            problems = verify(arguments["text"], results, arguments.get("farmer_said") or [])
            return {"result": {"supported": not problems, "unsupported": [{"text": p.text} for p in problems]},
                    "provenance": {}}
        if name == "solve_plan":
            try:
                return {"result": tools.evaluate_season(arguments["scenario"]), "provenance": {"sig": "x"}}
            except Exception as e:  # noqa: BLE001
                return {"error": str(e), "provenance": {}}
        return {"error": "not in this fake"}


class Scripted:
    """An OpenAI-compatible client whose answers are written in advance."""

    def __init__(self, steps):
        self.steps = list(steps)
        self.chat = NS(completions=NS(create=self.create))

    def create(self, model, messages, tools=None, **kw):
        step = self.steps.pop(0)
        if callable(step):
            step = step(messages)
        if isinstance(step, list):
            msg = NS(content=None, tool_calls=[NS(id=f"c{i}", function=NS(name=n, arguments=a))
                                               for i, (n, a) in enumerate(step)])
        else:
            msg = NS(content=step, tool_calls=None)
        return NS(choices=[NS(message=msg)], usage=NS(prompt_tokens=100, completion_tokens=10))


def _q08_scenario():
    q = next(json.loads(l) for l in open("eval/questions.jsonl", encoding="utf-8") if f'"{Q_ID}"' in l)
    return q["scenario"]


def _wheat_answer(messages):
    res = json.loads(messages[-1]["content"])["result"]
    return f"Te conviene sembrar {res['hectares']['wheat']:.0f} ha de trigo."


def test_parse_sse_and_plain_json():
    assert parse_sse('event: message\ndata: {"id": 1, "result": {}}\n') == {"id": 1, "result": {}}
    assert parse_sse('{"id": 2, "result": {"a": 1}}')["result"] == {"a": 1}


def test_tool_payload_reads_structured_content_and_text():
    assert tool_payload({"structuredContent": {"result": {"x": 1}, "provenance": {}}}) == {"result": {"x": 1}, "provenance": {}}
    assert tool_payload({"content": [{"type": "text", "text": '{"error": "bad"}'}]}) == {"error": "bad"}
    assert "error" in tool_payload({"content": [{"type": "text", "text": "not json"}]})


def test_openai_tools_keep_the_mcp_schema():
    t = openai_tools([{"name": "solve_plan", "description": "d", "inputSchema": {"type": "object", "properties": {}}}])
    assert t[0]["function"]["name"] == "solve_plan" and t[0]["function"]["parameters"]["type"] == "object"


def test_generic_agent_solves_and_is_verified():
    mcp = FakeMCP()
    setup = mcp_agent.setup(mcp)
    assert mcp_agent.NEUTRAL_PROMPT in setup["system"] and "check_text" in setup["system"]
    client = Scripted([[("solve_plan", json.dumps({"scenario": _q08_scenario()}))], _wheat_answer])
    out = MCPAgent(client, "m", mcp, setup).ask("Con 400 ha y 100.000 USD, ¿cuánto trigo?")
    assert out["tool_calls"][0]["tool"] == "evaluate_season" and out["tool_calls"][0]["mcp_tool"] == "solve_plan"
    assert out["verified"] is True and out["usage"]["requests"] == 2


def test_generic_agent_bad_json_is_an_error_call_not_a_crash():
    mcp = FakeMCP()
    client = Scripted([[("solve_plan", "{scenario: False}")], "No pude."])
    out = MCPAgent(client, "m", mcp, mcp_agent.setup(mcp)).ask("x")
    assert out["tool_calls"][0]["bad_json"] is True and out["tool_calls"][0]["error"] is True
    assert ("solve_plan", {}) not in mcp.calls


def test_run_evaluation_arm_mcp_scores_like_dora(tmp_path, monkeypatch):
    mcp = FakeMCP()
    monkeypatch.setattr(mcp_agent, "MCPClient", lambda: mcp)
    client = Scripted([[("solve_plan", json.dumps({"scenario": _q08_scenario()}))], _wheat_answer])
    res = run_evaluation(client=client, model="m", runs=1, ids=[Q_ID], arm="mcp", output_path=tmp_path / "r.json")
    rec = res["detailed_results"][0][0]
    assert res["condition"] == "mcp" and res["arm"] == "mcp"
    assert rec["answer_correctness"] and rec["correct_verified"] and rec["tool_accuracy"]
    assert res["run_metrics"][0]["tool_call_ok_rate"] == 1.0
    assert res["run_metrics"][0]["no_tool_call_rate"] == 0.0


def test_a_crash_is_a_failed_answer(tmp_path, monkeypatch):
    mcp = FakeMCP()
    monkeypatch.setattr(mcp_agent, "MCPClient", lambda: mcp)

    def boom(messages):
        raise RuntimeError("context length exceeded")
    res = run_evaluation(client=Scripted([boom]), model="m", runs=1, ids=[Q_ID], arm="mcp",
                         output_path=tmp_path / "r.json")
    rec = res["detailed_results"][0][0]
    assert rec["failed"].startswith("RuntimeError") and rec["correct_verified"] is False
    assert res["run_metrics"][0]["failed_count"] == 1


def test_key_is_not_in_results(tmp_path, monkeypatch):
    monkeypatch.setenv("DORA_MCP_API_KEY", "secret-key-123")
    mcp = FakeMCP()
    monkeypatch.setattr(mcp_agent, "MCPClient", lambda: mcp)
    client = Scripted([[("solve_plan", json.dumps({"scenario": _q08_scenario()}))], _wheat_answer])
    run_evaluation(client=client, model="m", runs=1, ids=[Q_ID], arm="mcp", output_path=tmp_path / "r.json")
    assert "secret-key-123" not in (tmp_path / "r.json").read_text(encoding="utf-8")


def test_serve_open_app_name():
    import importlib.util
    import pathlib
    import pytest
    pytest.importorskip("modal")
    spec = importlib.util.spec_from_file_location("serve_open", pathlib.Path("infra/modal/serve_open.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.app_name("Qwen/Qwen2.5-7B-Instruct") == "dora-e9-qwen2-5-7b-instruct"
    assert mod.PARSER == "hermes"


def test_strict_refusal_rejects_a_made_up_plan():
    from eval.run_eval import strict_refusal
    q = "Quiero sembrar 300 hectáreas de arroz con 50.000 dólares."
    assert strict_refusal("No puedo planificar arroz: DORA no soporta ese cultivo. ¿Querés otro?", q)
    assert not strict_refusal("Plan\n- **Arroz**: 300 ha\n- Capital: 50.000", q)
    assert not strict_refusal("No se puede arroz, pero sembrá 150 ha de soja.", q)


def test_strict_score_needs_the_engine_value_with_tools():
    from eval.run_eval import strict_score
    q = {"id": "q19", "text": "I farm 500 ha with $40,000 cash and an $80,000 credit line"}
    echo = {"answer_correctness": True, "reported_value": None, "verified": True}
    assert strict_score(q, dict(echo), {"q19": 80000.0}, with_tools=True)["correct_verified"] is False
    backed = {"answer_correctness": True, "reported_value": 80000.0, "verified": True}
    assert strict_score(q, dict(backed), {"q19": 80000.0}, with_tools=True)["correct_verified"] is True
    alone = {"answer_correctness": True, "has_unsupported_before_correction": True}
    assert strict_score(q, dict(alone), {"q19": 80000.0}, with_tools=False)["correct_verified"] is False
