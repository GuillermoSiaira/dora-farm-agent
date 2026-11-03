import json
from unittest.mock import MagicMock
import pytest

from dora.verifier import season_crops, check_scenario, SUMMER_CROPS, WINTER_CROPS
from dora.agent import Agent


def test_1_season_crops():
    # 1. season_crops: "la gruesa" and "campaña gruesa" give the summer list;
    # "la fina" gives ["wheat"]; "finanzas", "afinar el plan", "la final" give None;
    # "gruesa y fina" gives None; "summer crops" gives the summer list.
    assert season_crops("la gruesa") == ["corn", "soybean", "sunflower"]
    assert season_crops("campaña gruesa") == ["corn", "soybean", "sunflower"]
    assert season_crops("la fina") == ["wheat"]
    assert season_crops("finanzas") is None
    assert season_crops("afinar el plan") is None
    assert season_crops("la final") is None
    assert season_crops("gruesa y fina") is None
    assert season_crops("summer crops") == ["corn", "soybean", "sunflower"]


def test_2_check_scenario():
    # 2. check_scenario accepts crops: ["soybean","corn","sunflower"] when the farmer wrote "la gruesa",
    # and still rejects crops: ["barley"] (or whatever the current test for an unsaid crop uses).
    scenario_ok = {
        "region": "southeast_buenos_aires",
        "area_ha": 400,
        "crops": ["soybean", "corn", "sunflower"],
    }
    user_texts_gruesa = ["planifiquemos la gruesa, tengo 400 ha"]
    problems = check_scenario("evaluate_season", {"scenario": scenario_ok}, user_texts_gruesa, [])
    assert not any(p.parameter == "crops" for p in problems)

    # Rejects crops: ["barley"]
    scenario_bad = {
        "region": "southeast_buenos_aires",
        "area_ha": 400,
        "crops": ["barley"],
    }
    problems_bad = check_scenario("evaluate_season", {"scenario": scenario_bad}, user_texts_gruesa, [])
    assert any(p.parameter == "crops" for p in problems_bad)


def test_3_agent_sets_season_crops_when_omitted():
    # 3. Agent with a fake client that calls evaluate_season without crops after "planifiquemos la gruesa…":
    # the arguments that reach run_tool have the summer list.
    class MockChatCompletions:
        def __init__(self):
            self.call_count = 0

        def create(self, model, messages, tools=None):
            self.call_count += 1
            choice = MagicMock()
            msg = MagicMock()
            if self.call_count == 1:
                tc = MagicMock()
                tc.id = "call_1"
                tc.function.name = "evaluate_season"
                tc.function.arguments = json.dumps({
                    "scenario": {
                        "area_ha": 400,
                        "own_capital_usd": 60000,
                        "region": "southeast_buenos_aires",
                    }
                })
                msg.tool_calls = [tc]
                msg.content = None
            else:
                msg.tool_calls = None
                msg.content = "Plan sugerido sin trigo."
            choice.message = msg
            resp = MagicMock()
            resp.choices = [choice]
            resp.usage = {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20, "requests": 1}
            return resp

    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MockChatCompletions()

    agent = Agent(client=mock_client, model="test-model")
    reply = agent.ask("planifiquemos la gruesa en campo propio del sudeste, son 400 ha y 60000 USD")

    assert len(reply.tool_calls) == 1
    call = reply.tool_calls[0]
    assert call["tool"] == "evaluate_season"
    assert call.get("crops_from_season_word") is True
    args = json.loads(call["arguments"])
    sc = args.get("scenario", {})
    assert set(sc.get("crops", [])) == {"corn", "soybean", "sunflower"}
    assert "wheat" not in sc.get("crops", [])


def test_4_agent_explicit_crop_contradiction_not_overwritten():
    # 4. Agent with a fake client that names wheat after "la gruesa, pero sumale trigo":
    # crops is not overwritten.
    class MockChatCompletions:
        def __init__(self):
            self.call_count = 0

        def create(self, model, messages, tools=None):
            self.call_count += 1
            choice = MagicMock()
            msg = MagicMock()
            if self.call_count == 1:
                tc = MagicMock()
                tc.id = "call_1"
                tc.function.name = "evaluate_season"
                tc.function.arguments = json.dumps({
                    "scenario": {
                        "area_ha": 400,
                        "crops": ["wheat", "soybean"],
                        "region": "southeast_buenos_aires",
                    }
                })
                msg.tool_calls = [tc]
                msg.content = None
            else:
                msg.tool_calls = None
                msg.content = "Plan con trigo y soja."
            choice.message = msg
            resp = MagicMock()
            resp.choices = [choice]
            resp.usage = {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20, "requests": 1}
            return resp

    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MockChatCompletions()

    agent = Agent(client=mock_client, model="test-model")
    reply = agent.ask("la gruesa, pero sumale trigo: tengo 400 ha")

    assert len(reply.tool_calls) == 1
    call = reply.tool_calls[0]
    assert call["tool"] == "evaluate_season"
    assert not call.get("crops_from_season_word")
    args = json.loads(call["arguments"])
    sc = args.get("scenario", {})
    assert sc.get("crops") == ["wheat", "soybean"]
    assert "wheat" in sc.get("crops", [])


def test_5_build_scenario_caching(monkeypatch):
    # If build_scenario is called with exactly the same scenario as an earlier call in the same turn,
    # return the earlier result without running run_tool again.
    import dora.agent as agent_mod
    original_run_tool = agent_mod.run_tool
    run_tool_calls = []

    def tracking_run_tool(name, args, images=None):
        run_tool_calls.append((name, args))
        return original_run_tool(name, args, images=images)

    monkeypatch.setattr(agent_mod, "run_tool", tracking_run_tool)

    class MockChatCompletions:
        def __init__(self):
            self.call_count = 0

        def create(self, model, messages, tools=None):
            self.call_count += 1
            choice = MagicMock()
            msg = MagicMock()
            if self.call_count in (1, 2):
                tc = MagicMock()
                tc.id = f"call_{self.call_count}"
                tc.function.name = "build_scenario"
                tc.function.arguments = json.dumps({
                    "scenario": {
                        "area_ha": 400,
                        "region": "southeast_buenos_aires",
                    }
                })
                msg.tool_calls = [tc]
                msg.content = None
            else:
                msg.tool_calls = None
                msg.content = "Escenario listo."
            choice.message = msg
            resp = MagicMock()
            resp.choices = [choice]
            resp.usage = {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20, "requests": 1}
            return resp

    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MockChatCompletions()

    agent = Agent(client=mock_client, model="test-model")
    reply = agent.ask("400 ha en sudeste")

    # The model called build_scenario twice
    assert len(reply.tool_calls) == 2
    assert reply.tool_calls[0]["tool"] == "build_scenario"
    assert reply.tool_calls[1]["tool"] == "build_scenario"

    # But run_tool was only invoked once! The second was served from turn cache
    build_calls = [c for c in run_tool_calls if c[0] == "build_scenario"]
    assert len(build_calls) == 1


def test_6_gruesa_in_iowa_drops_sunflower():
    # Claude's review: Iowa has no sunflower, so "la gruesa" there means corn and soybean only.
    scenario = {"region": "iowa", "area_ha": 400, "crops": ["corn", "soybean"]}
    problems = check_scenario("evaluate_season", {"scenario": scenario}, ["la gruesa en Iowa, 400 ha"], [])
    assert not any(p.parameter == "crops" for p in problems)
