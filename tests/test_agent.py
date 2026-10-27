"""The agent loop, with a scripted model instead of a real API (no credits spent)."""
import json
from types import SimpleNamespace as NS

from dora.agent import Agent
from dora.tools import run_tool

SCENARIO = {"scenario": {"area_ha": 500, "own_capital_usd": 50000}}


def tool_call(name, args, i=1):
    return NS(id=f"call_{i}", function=NS(name=name, arguments=json.dumps(args)))


class ScriptedModel:
    """Returns the scripted messages in order; each is a text or a list of tool calls."""

    def __init__(self, script):
        self.script = list(script)
        self.seen = []
        self.chat = NS(completions=NS(create=self.create))

    def create(self, model, messages, tools):
        self.seen.append(list(messages))
        step = self.script.pop(0)
        msg = NS(content=None, tool_calls=step) if isinstance(step, list) else NS(content=step, tool_calls=None)
        return NS(choices=[NS(message=msg)])


def npv_text():
    npv = json.loads(run_tool("evaluate_season", SCENARIO))["npv_usd"]
    return f"El valor presente de la campaña es de USD {npv:,.0f}.".replace(",", ".")


def test_tool_call_then_verified_answer():
    model = ScriptedModel([[tool_call("evaluate_season", SCENARIO)], npv_text()])
    reply = Agent(client=model, model="test").ask("Tengo 500 ha y 50000 dólares")
    assert reply.verified and reply.tool_calls[0]["tool"] == "evaluate_season"
    assert model.seen[1][-1]["role"] == "tool"


def test_invented_number_triggers_a_correction():
    model = ScriptedModel([[tool_call("evaluate_season", SCENARIO)],
                           "El valor presente es de USD 123.456.",
                           npv_text()])
    reply = Agent(client=model, model="test").ask("Tengo 500 ha y 50000 dólares")
    assert reply.verified
    correction = model.seen[2][-1]
    assert correction["role"] == "user" and "123.456" in correction["content"]


def test_answer_still_wrong_after_corrections_is_flagged():
    model = ScriptedModel([[tool_call("evaluate_season", SCENARIO)]] + ["Ganás USD 999.999."] * 3)
    reply = Agent(client=model, model="test").ask("Tengo 500 ha y 50000 dólares")
    assert not reply.verified and reply.unsupported[0].text == "999.999"


def test_tool_errors_go_back_to_the_model():
    bad = {"scenario": {"area_ha": -1}}
    model = ScriptedModel([[tool_call("evaluate_season", bad)], [tool_call("evaluate_season", SCENARIO, 2)],
                           npv_text()])
    reply = Agent(client=model, model="test").ask("Tengo 500 ha")
    assert [c["error"] for c in reply.tool_calls] == [True, False]
    assert "out of range" in model.seen[1][-1]["content"]
