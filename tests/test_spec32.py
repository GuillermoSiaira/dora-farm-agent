import os
from pathlib import Path
from unittest.mock import patch
import gradio as gr
import pytest

import app
from app import (
    CARD1_PROMPT_EN,
    CARD1_PROMPT_ES,
    CARD2_PROMPT_EN,
    CARD2_PROMPT_ES,
    SAMPLE_INVOICE_PATH,
    build_app,
    on_start_card1,
    on_start_card2,
    on_start_card3,
    on_start_scenario_link,
)


class FakeReply:
    def __init__(self, text="Fake agent reply", verified=True):
        self.text = text
        self.verified = verified
        self.unsupported = []
        self.tool_calls = []


class FakeAgent:
    def __init__(self, reply_text="Fake agent reply"):
        self.reply_text = reply_text
        self.user_texts = []
        self.tool_results = []
        self.asked_calls = []

    def ask(self, text, images=None, audio=None, screen_scenario=None):
        self.user_texts.append(text)
        self.asked_calls.append({
            "text": text,
            "images": images,
            "audio": audio,
            "screen_scenario": screen_scenario,
        })
        return FakeReply(self.reply_text)


# 1. The first TabItem in the Blocks is tab_start, tabs is created with selected="tab_start";
# the order of the tab ids is start, chat, scenario, regions, compare. (When has_chat is false: start, scenario, regions, compare.)
def test_1_tab_order_and_initial_selection():
    # With chat (API key present)
    with patch.dict(os.environ, {"DORA_API_KEY": "fake-key"}, clear=True):
        demo_with_chat = build_app()
        assert getattr(demo_with_chat, "has_chat", True)

        tab_items_with_chat = [b for b in demo_with_chat.blocks.values() if isinstance(b, gr.TabItem)]
        assert len(tab_items_with_chat) == 5
        assert tab_items_with_chat[0].elem_id == "tab_start"

        tab_ids_with_chat = [t.elem_id for t in tab_items_with_chat]
        assert tab_ids_with_chat == ["tab_start", "tab_chat", "tab_scenario", "tab_regions", "tab_compare"]

        tabs_component = [b for b in demo_with_chat.blocks.values() if isinstance(b, gr.Tabs)][0]
        assert getattr(tabs_component, "selected", None) == "tab_start"

    # Without chat (API key absent)
    with patch.dict(os.environ, {}, clear=True):
        demo_no_chat = build_app(api_key="")
        assert not getattr(demo_no_chat, "has_chat", False)

        tab_items_no_chat = [b for b in demo_no_chat.blocks.values() if isinstance(b, gr.TabItem)]
        assert len(tab_items_no_chat) == 4
        assert tab_items_no_chat[0].elem_id == "tab_start"

        tab_ids_no_chat = [t.elem_id for t in tab_items_no_chat]
        assert tab_ids_no_chat == ["tab_start", "tab_scenario", "tab_regions", "tab_compare"]

        tabs_component_no_chat = [b for b in demo_no_chat.blocks.values() if isinstance(b, gr.Tabs)][0]
        assert getattr(tabs_component_no_chat, "selected", None) == "tab_start"


# 2. The Start tab's texts switch language: with "English" selected its title and the three card titles are in English; with "Español", in Spanish.
def test_2_start_tab_language_switch():
    with patch.dict(os.environ, {"DORA_API_KEY": "fake-key"}, clear=True):
        demo = build_app()
        assert hasattr(demo, "lang_change_fn")

        # Switch to English
        res_en = demo.lang_change_fn("English")
        values_en = [item["value"] for item in res_en if isinstance(item, dict) and "value" in item]

        title_en_found = any("DORA plans your crop season" in str(v) for v in values_en)
        c1_en_found = any("Plan your season" in str(v) for v in values_en)
        c2_en_found = any("Send an invoice" in str(v) for v in values_en)
        c3_en_found = any("Compare regions" in str(v) for v in values_en)

        assert title_en_found, "Start tab English title not found in lang_change outputs"
        assert c1_en_found, "Card 1 English title not found in lang_change outputs"
        assert c2_en_found, "Card 2 English title not found in lang_change outputs"
        assert c3_en_found, "Card 3 English title not found in lang_change outputs"

        # Switch to Español
        res_es = demo.lang_change_fn("Español")
        values_es = [item["value"] for item in res_es if isinstance(item, dict) and "value" in item]

        title_es_found = any("DORA planifica tu campaña agrícola" in str(v) for v in values_es)
        c1_es_found = any("Planificá tu campaña" in str(v) for v in values_es)
        c2_es_found = any("Mandale una factura" in str(v) for v in values_es)
        c3_es_found = any("Compará regiones" in str(v) for v in values_es)

        assert title_es_found, "Start tab Spanish title not found in lang_change outputs"
        assert c1_es_found, "Card 1 Spanish title not found in lang_change outputs"
        assert c2_es_found, "Card 2 Spanish title not found in lang_change outputs"
        assert c3_es_found, "Card 3 Spanish title not found in lang_change outputs"


# 3. The card 1 handler, with a fake agent whose ask returns a fixed reply, puts the Balcarce example text as the user message and the fake reply in the history, in the selected language.
def test_3_card1_handler_sends_example_message():
    # Spanish
    agent_es = FakeAgent(reply_text="Plan sugerido para Balcarce")
    msg_out, files_out, audio_out, history_es, state_es = on_start_card1([], agent_es, lang="es")
    assert len(history_es) == 2
    assert history_es[0]["role"] == "user"
    assert history_es[0]["content"] == CARD1_PROMPT_ES
    assert history_es[1]["role"] == "assistant"
    assert "Plan sugerido para Balcarce" in history_es[1]["content"]
    assert len(agent_es.asked_calls) == 1
    assert agent_es.asked_calls[0]["text"] == CARD1_PROMPT_ES

    # English
    agent_en = FakeAgent(reply_text="Suggested plan for Balcarce")
    msg_out, files_out, audio_out, history_en, state_en = on_start_card1([], agent_en, lang="en")
    assert len(history_en) == 2
    assert history_en[0]["role"] == "user"
    assert history_en[0]["content"] == CARD1_PROMPT_EN
    assert history_en[1]["role"] == "assistant"
    assert "Suggested plan for Balcarce" in history_en[1]["content"]
    assert len(agent_en.asked_calls) == 1
    assert agent_en.asked_calls[0]["text"] == CARD1_PROMPT_EN


# 4. The card 2 handler sends assets/examples/factura-ejemplo.png (the file exists) together with the example text.
def test_4_card2_handler_sends_invoice_image():
    # Ensure sample invoice exists
    invoice_path = Path(SAMPLE_INVOICE_PATH)
    assert invoice_path.is_file(), f"Sample invoice file {SAMPLE_INVOICE_PATH} does not exist"

    # Spanish
    agent_es = FakeAgent(reply_text="Costos actualizados con la factura")
    msg_out, files_out, audio_out, history_es, state_es = on_start_card2([], agent_es, lang="es")
    assert len(history_es) == 2
    assert history_es[0]["role"] == "user"
    assert CARD2_PROMPT_ES in history_es[0]["content"]
    assert "factura-ejemplo.png" in history_es[0]["content"]
    assert history_es[1]["role"] == "assistant"
    assert "Costos actualizados con la factura" in history_es[1]["content"]
    assert len(agent_es.asked_calls) == 1
    assert agent_es.asked_calls[0]["text"] == CARD2_PROMPT_ES
    assert agent_es.asked_calls[0]["images"] == [SAMPLE_INVOICE_PATH]

    # English
    agent_en = FakeAgent(reply_text="Costs recalculated with invoice")
    msg_out, files_out, audio_out, history_en, state_en = on_start_card2([], agent_en, lang="en")
    assert len(history_en) == 2
    assert history_en[0]["role"] == "user"
    assert CARD2_PROMPT_EN in history_en[0]["content"]
    assert "factura-ejemplo.png" in history_en[0]["content"]
    assert history_en[1]["role"] == "assistant"
    assert "Costs recalculated with invoice" in history_en[1]["content"]
    assert len(agent_en.asked_calls) == 1
    assert agent_en.asked_calls[0]["text"] == CARD2_PROMPT_EN
    assert agent_en.asked_calls[0]["images"] == [SAMPLE_INVOICE_PATH]


# 5. The card 3 and "Escenario" handlers return gr.update(selected="tab_regions") and gr.update(selected="tab_scenario").
def test_5_card3_and_scenario_link_handlers():
    res3 = on_start_card3()
    assert isinstance(res3, dict)
    assert res3.get("selected") == "tab_regions"

    res_sc = on_start_scenario_link()
    assert isinstance(res_sc, dict)
    assert res_sc.get("selected") == "tab_scenario"

