"""Acceptance tests for SPEC-33: Muse Spark Open and warm app.

Offline tests: no network calls, no model APIs.
"""
import os
import pytest
from unittest.mock import MagicMock

import app
from app import (
    build_app,
    make_client,
    model_for,
    on_model_choice_change,
    respond,
)
from dora.agent import Reply


def test_1_model_choice_presence(monkeypatch):
    """1. With BASETEN_API_KEY unset, no component with elem_id='model_choice'.

    With it set (monkeypatch), it exists and its default is the Meta option.
    """
    monkeypatch.setenv("DORA_API_KEY", "test-dora-key")

    # Unset BASETEN_API_KEY
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    demo_without = build_app()
    assert getattr(demo_without, "model_choice", None) is None
    choice_blocks_without = [
        b for b in demo_without.blocks.values()
        if getattr(b, "elem_id", None) == "model_choice"
    ]
    assert len(choice_blocks_without) == 0

    # Set BASETEN_API_KEY
    monkeypatch.setenv("BASETEN_API_KEY", "mock-baseten-key")
    demo_with = build_app()
    assert getattr(demo_with, "model_choice", None) is not None
    choice_blocks_with = [
        b for b in demo_with.blocks.values()
        if getattr(b, "elem_id", None) == "model_choice"
    ]
    assert len(choice_blocks_with) == 1
    assert choice_blocks_with[0].value == "Muse Spark 1.3 (Meta API)"


def test_2_respond_baseten_provider(monkeypatch):
    """2. respond(..., provider='baseten') with no agent builds the Agent with Baseten model and client base_url."""
    monkeypatch.setenv("BASETEN_API_KEY", "test-baseten-key")
    monkeypatch.delenv("BASETEN_API_BASE", raising=False)
    monkeypatch.delenv("BASETEN_MODEL", raising=False)

    created_agents = []

    class MockAgent:
        def __init__(self, client=None, model=None, use_verifier=True):
            self.client = client
            self.model = model
            self.user_texts = []
            created_agents.append(self)

        def ask(self, text, images=None, audio=None, screen_scenario=None):
            return Reply(text="Mocked Baseten response", verified=True)

    monkeypatch.setattr("dora.agent.Agent", MockAgent)

    msg, files, audio, history, agent = respond(
        user_text="Tengo 500 ha en Balcarce",
        files=None,
        audio=None,
        history=[],
        agent_instance=None,
        lang="es",
        screen_scenario=None,
        provider="baseten",
    )

    assert len(created_agents) == 1
    agent_inst = created_agents[0]
    assert agent_inst.model == "meta-models/muse-spark-open-1026"
    assert str(agent_inst.client.base_url).rstrip("/") == "https://inference.baseten.co/v1"
    assert "Mocked Baseten response" in history[-1]["content"]


def test_3_respond_meta_provider(monkeypatch):
    """3. respond(..., provider='meta') builds Agent as today (DORA_MODEL, default client)."""
    monkeypatch.setenv("DORA_API_KEY", "test-meta-key")
    monkeypatch.setenv("DORA_API_BASE", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("DORA_MODEL", "mock-meta-1.3")

    created_agents = []

    class MockAgent:
        def __init__(self, client=None, model=None, use_verifier=True):
            self.client = client
            self.model = model
            self.user_texts = []
            created_agents.append(self)

        def ask(self, text, images=None, audio=None, screen_scenario=None):
            return Reply(text="Mocked Meta response", verified=True)

    monkeypatch.setattr("dora.agent.Agent", MockAgent)

    msg, files, audio, history, agent = respond(
        user_text="Tengo 500 ha en Balcarce",
        files=None,
        audio=None,
        history=[],
        agent_instance=None,
        lang="es",
        screen_scenario=None,
        provider="meta",
    )

    assert len(created_agents) == 1
    agent_inst = created_agents[0]
    assert agent_inst.model == "mock-meta-1.3"
    assert str(agent_inst.client.base_url).rstrip("/") == "http://127.0.0.1:9/v1"
    assert "Mocked Meta response" in history[-1]["content"]


def test_4_model_choice_change():
    """4. Changing the Radio returns an empty history plus 'Ahora conversás con…' and None agent state."""
    # Spanish Open
    hist_es_open, agent_es_open = on_model_choice_change("Muse Spark Open (Baseten)", lang="es")
    assert agent_es_open is None
    assert hist_es_open == [{"role": "assistant", "content": "Ahora conversás con Muse Spark Open."}]

    # Spanish 1.3
    hist_es_13, agent_es_13 = on_model_choice_change("Muse Spark 1.3 (Meta API)", lang="es")
    assert agent_es_13 is None
    assert hist_es_13 == [{"role": "assistant", "content": "Ahora conversás con Muse Spark 1.3."}]

    # English Open
    hist_en_open, agent_en_open = on_model_choice_change("Muse Spark Open (Baseten)", lang="en")
    assert agent_en_open is None
    assert hist_en_open == [{"role": "assistant", "content": "You are now talking to Muse Spark Open."}]

    # English 1.3
    hist_en_13, agent_en_13 = on_model_choice_change("Muse Spark 1.3 (Meta API)", lang="en")
    assert agent_en_13 is None
    assert hist_en_13 == [{"role": "assistant", "content": "You are now talking to Muse Spark 1.3."}]


def test_5_photos_not_supported_baseten(monkeypatch):
    """5. If photos are not supported: with provider='baseten' and a file attached, fixed message and client never called."""
    monkeypatch.setattr(app, "BASETEN_SUPPORTS_IMAGES", False)

    mock_agent_class = MagicMock()
    monkeypatch.setattr("dora.agent.Agent", mock_agent_class)

    # Spanish
    msg, files, audio, history, agent = respond(
        user_text="Factura adjunta",
        files=["assets/examples/factura-ejemplo.png"],
        audio=None,
        history=[],
        agent_instance=None,
        lang="es",
        screen_scenario=None,
        provider="baseten",
    )

    mock_agent_class.assert_not_called()
    assert "Muse Spark Open no lee fotos en esta versión; elegí Muse Spark 1.3 para mandar facturas." in history[-1]["content"]

    # English
    msg, files, audio, history, agent = respond(
        user_text="Attached invoice",
        files=["assets/examples/factura-ejemplo.png"],
        audio=None,
        history=[],
        agent_instance=None,
        lang="en",
        screen_scenario=None,
        provider="baseten",
    )

    mock_agent_class.assert_not_called()
    assert "Muse Spark Open does not read photos in this version; choose Muse Spark 1.3 to send invoices." in history[-1]["content"]


def test_6_warm_containers(monkeypatch):
    """6. serve_app.py with DORA_WARM=1 sets min_containers=1; without it, 0."""
    pytest.importorskip("modal")   # the project venv has no Modal CLI; the deploy machine does
    from infra.modal.serve_app import warm_containers

    monkeypatch.setenv("DORA_WARM", "1")
    assert warm_containers() == 1

    monkeypatch.setenv("DORA_WARM", "0")
    assert warm_containers() == 0

    monkeypatch.delenv("DORA_WARM", raising=False)
    assert warm_containers() == 0

