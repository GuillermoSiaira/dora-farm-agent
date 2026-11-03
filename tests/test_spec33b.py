"""Acceptance tests for SPEC-33b: immediate chat feedback, answer timing log, and clean invoice table.

Offline tests: no network calls, no model APIs.
"""
import json
import os
from unittest.mock import MagicMock
import pytest

from app import (
    PENDING_MSG_ES,
    PENDING_MSG_EN,
    show_pending,
    respond,
    build_app,
)
from dora.agent import Agent, Reply
from dora.verifier import correction_message, farmer_lang


class FakeAgent:
    """Mock agent for fast offline testing."""
    def __init__(self, reply_text="Respuesta simulada", verified=True, tool_calls=None, tool_results=None, requests=1):
        self.user_texts = []
        self.reply_text = reply_text
        self.verified = verified
        self.tool_calls = tool_calls or []
        self.tool_results = tool_results or []
        self.usage = {"requests": requests}

    def ask(self, text, images=None, audio=None, screen_scenario=None):
        self.user_texts.append(text)
        return Reply(
            text=self.reply_text,
            verified=self.verified,
            tool_calls=self.tool_calls,
            usage=dict(self.usage),
        )


def test_1_show_pending():
    """1. show_pending with text returns history plus user message and pending line, in each language;

    with nothing to send, history unchanged.
    """
    initial_history = [{"role": "assistant", "content": "Hola, soy DORA"}]

    # In Spanish
    res_es = show_pending("Tengo 500 ha en Balcarce", None, None, initial_history, lang="es")
    assert len(res_es) == 3
    assert res_es[0] == initial_history[0]
    assert res_es[1] == {"role": "user", "content": "Tengo 500 ha en Balcarce"}
    assert res_es[2] == {"role": "assistant", "content": PENDING_MSG_ES}

    # In English
    res_en = show_pending("I have 500 ha in Balcarce", None, None, initial_history, lang="en")
    assert len(res_en) == 3
    assert res_en[1] == {"role": "user", "content": "I have 500 ha in Balcarce"}
    assert res_en[2] == {"role": "assistant", "content": PENDING_MSG_EN}

    # With nothing to send: empty string, None, None -> history unchanged
    res_empty1 = show_pending("", None, None, initial_history, lang="es")
    assert res_empty1 == initial_history

    res_empty2 = show_pending("   ", None, None, initial_history, lang="en")
    assert res_empty2 == initial_history

    res_empty3 = show_pending(None, None, None, initial_history, lang="es")
    assert res_empty3 == initial_history

    # With audio note
    res_audio = show_pending(None, None, "test.wav", initial_history, lang="es")
    assert len(res_audio) == 3
    assert "🎤 nota de voz" in res_audio[1]["content"]

    # With image attached
    res_img = show_pending("Mira esto", ["foto.png"], None, initial_history, lang="es")
    assert len(res_img) == 3
    assert "foto.png" in res_img[1]["content"]


def test_2_respond_clears_pending():
    """2. respond called with a history ending in the pending pair removes it

    and ends with exactly one user message and one reply (fake agent).
    """
    pending_history = [
        {"role": "assistant", "content": "Hola"},
        {"role": "user", "content": "Tengo 500 ha en Balcarce"},
        {"role": "assistant", "content": PENDING_MSG_ES},
    ]

    agent = FakeAgent(reply_text="Plan óptimo para Balcarce", verified=True)
    txt_out, files_out, audio_out, final_history, ret_agent = respond(
        user_text="Tengo 500 ha en Balcarce",
        files=None,
        audio=None,
        history=pending_history,
        agent_instance=agent,
        lang="es",
        screen_scenario=None,
    )

    # final_history must have:
    # 0: initial assistant "Hola"
    # 1: user "Tengo 500 ha en Balcarce"
    # 2: assistant reply (with verified badge and text)
    # The pending pair was stripped before appending the real reply.
    assert len(final_history) == 3
    assert final_history[0]["content"] == "Hola"
    assert final_history[1]["role"] == "user"
    assert final_history[1]["content"] == "Tengo 500 ha en Balcarce"
    assert final_history[2]["role"] == "assistant"
    assert "Plan óptimo para Balcarce" in final_history[2]["content"]
    assert PENDING_MSG_ES not in final_history[2]["content"]


def test_3_log_line_printed(capsys):
    """3. The log line is printed with provider, seconds, rounds and verified (capture stdout, fake agent)."""
    agent = FakeAgent(
        reply_text="Simulación de rotación",
        verified=True,
        tool_calls=[
            {"tool": "build_scenario", "arguments": "{}"},
            {"tool": "evaluate_season", "arguments": "{}"},
        ],
        requests=3,
    )

    respond(
        user_text="Hola DORA",
        files=None,
        audio=None,
        history=[],
        agent_instance=agent,
        lang="es",
        screen_scenario=None,
        provider="meta",
    )

    captured = capsys.readouterr()
    log_line = None
    for line in captured.out.splitlines():
        if line.startswith("[chat]"):
            log_line = line
            break

    assert log_line is not None, f"Expected [chat] log line in stdout, got:\n{captured.out}"
    assert "provider=meta" in log_line
    assert "seconds=" in log_line
    assert "rounds=3" in log_line
    assert "tools=build_scenario,evaluate_season" in log_line
    assert "verified=True" in log_line
    assert "images=0" in log_line
    assert "audio=False" in log_line


def test_4_reconciliation_table_no_unknown_rows():
    """4. The reconciliation table with an unknown crop or None reference shows no ✅ row

    and shows the 'Falta saber…' line.
    """
    # Tool result with unknown crop and None default_usd_ha
    sample_doc_res = {
        "completeness": 0.5,
        "proposals": [
            {
                "crop": "unknown",
                "item": "fertilizer",
                "proposed_usd_ha": 26.0,
                "default_usd_ha": None,
                "deviation_pct": 0.0,
            }
        ],
    }

    agent_es = FakeAgent(
        reply_text="Recibí la factura.",
        verified=True,
        tool_calls=[{"tool": "record_document", "arguments": "{}"}],
        tool_results=[json.dumps(sample_doc_res)],
    )

    _, _, _, history_es, _ = respond(
        user_text="Factura",
        files=None,
        audio=None,
        history=[],
        agent_instance=agent_es,
        lang="es",
        screen_scenario=None,
    )

    bot_reply_es = history_es[-1]["content"]
    assert "### 📑 Conciliación de Documento del Productor:" in bot_reply_es
    assert "Falta saber para qué cultivo y cuántas hectáreas cubre la factura para compararla con la zona." in bot_reply_es
    assert "✅ |" not in bot_reply_es
    assert "| unknown |" not in bot_reply_es

    # English check
    agent_en = FakeAgent(
        reply_text="Received invoice.",
        verified=True,
        tool_calls=[{"tool": "record_document", "arguments": "{}"}],
        tool_results=[json.dumps(sample_doc_res)],
    )

    _, _, _, history_en, _ = respond(
        user_text="Invoice",
        files=None,
        audio=None,
        history=[],
        agent_instance=agent_en,
        lang="en",
        screen_scenario=None,
    )

    bot_reply_en = history_en[-1]["content"]
    assert "### 📑 Farmer's document check:" in bot_reply_en
    assert "To compare it with the zone I need the crop and the hectares the invoice covers." in bot_reply_en
    assert "✅ |" not in bot_reply_en
    assert "| unknown |" not in bot_reply_en


def test_6_correction_message_closing_line():
    """6. correction_message([], ['say which crop each number is'], 'es') ends with Spanish closing line;

    with 'en', the English one.
    """
    msg_es = correction_message([], ["say which crop each number is"], "es")
    expected_es = "Reescribí la respuesta completa para el productor, en castellano, como si fuera la primera: no menciones esta corrección ni digas 'mismo plan'."
    assert msg_es.endswith(expected_es)
    assert "say which crop each number is" in msg_es

    msg_en = correction_message([], ["say which crop each number is"], "en")
    expected_en = "Rewrite the whole answer for the farmer, in English, as if it were the first one: do not mention this correction or say 'same plan'."
    assert msg_en.endswith(expected_en)
    assert "say which crop each number is" in msg_en


def test_7_farmer_lang():
    """7. farmer_lang('planifiquemos la proxima campaña gruesa en campo propio') is 'es';

    farmer_lang('What should I sow with my 500 ha?') is 'en'; farmer_lang('hola') is 'es'.
    """
    assert farmer_lang("planifiquemos la proxima campaña gruesa en campo propio") == "es"
    assert farmer_lang("What should I sow with my 500 ha?") == "en"
    assert farmer_lang("hola") == "es"


def test_8_agent_correction_preserves_spanish_language():
    """8. Agent with a fake client whose first answer triggers unnamed_series (three decimal numbers separated by ' / ')

    and whose second answer is fine: the correction message the fake client receives contains the Spanish
    closing line when the farmer wrote in Spanish.
    """
    class MockChatCompletions:
        def __init__(self):
            self.call_count = 0
            self.received_messages = []

        def create(self, model, messages, tools=None):
            self.call_count += 1
            self.received_messages.append(list(messages))
            choice = MagicMock()
            msg = MagicMock()
            msg.tool_calls = None
            if self.call_count == 1:
                # Triggers unnamed_series: 3 numbers with decimals separated by " / "
                msg.content = "Plan sugerido: 120.5 / 250.0 / 80.0 ha para la campaña."
            else:
                msg.content = "Podemos planificar la campaña gruesa en el sudeste bonaerense."
            choice.message = msg
            resp = MagicMock()
            resp.choices = [choice]
            resp.usage = {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20, "requests": 1}
            return resp

    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MockChatCompletions()

    agent = Agent(client=mock_client, model="test-model")
    farmer_text = "planifiquemos la proxima campaña gruesa en campo propio"
    reply = agent.ask(farmer_text, screen_scenario=None)

    assert mock_client.chat.completions.call_count == 2
    # Second call receives the correction message
    second_call_messages = mock_client.chat.completions.received_messages[1]
    correction_user_msg = second_call_messages[-1]
    assert correction_user_msg["role"] == "user"
    expected_spanish_closing = "Reescribí la respuesta completa para el productor, en castellano, como si fuera la primera: no menciones esta corrección ni digas 'mismo plan'."
    assert expected_spanish_closing in correction_user_msg["content"]
    assert "say which crop each number is" in correction_user_msg["content"]
    assert "mismo plan" not in reply.text
