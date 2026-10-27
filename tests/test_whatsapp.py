"""Acceptance tests for SPEC-16: WhatsApp Cloud API webhook, media ingestion, and agent dispatcher."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import build_app
from dora.agent import Reply
from dora.whatsapp import (
    check_and_increment_daily_limit,
    download_media,
    handle_incoming_message,
    markdown_to_whatsapp,
    mount_whatsapp_webhook,
    reset_whatsapp_state,
    send_text,
    split_message,
)


@pytest.fixture(autouse=True)
def clean_state():
    reset_whatsapp_state()
    yield
    reset_whatsapp_state()


def test_get_webhook_verification(monkeypatch):
    # 1. GET with the right verify token returns the challenge; with a wrong one, 403.
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "my_verify_secret")

    app = FastAPI()
    mount_whatsapp_webhook(app)
    client = TestClient(app)

    # Correct token
    res = client.get("/whatsapp/webhook", params={
        "hub.mode": "subscribe",
        "hub.verify_token": "my_verify_secret",
        "hub.challenge": "11223344",
    })
    assert res.status_code == 200
    assert res.text == "11223344"

    # Wrong token
    res_wrong = client.get("/whatsapp/webhook", params={
        "hub.mode": "subscribe",
        "hub.verify_token": "wrong_secret",
        "hub.challenge": "11223344",
    })
    assert res_wrong.status_code == 403

    # Missing mode or token
    res_missing = client.get("/whatsapp/webhook", params={"hub.challenge": "11223344"})
    assert res_missing.status_code == 403


def test_post_signature_verification_and_fast_response(monkeypatch):
    # 2. POST with a bad signature returns 403; with a good one, 200, before the agent finishes.
    app_secret = "meta_super_secret"
    monkeypatch.setenv("WHATSAPP_APP_SECRET", app_secret)

    app = FastAPI()
    mount_whatsapp_webhook(app)
    client = TestClient(app)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "5491199999999",
                        "id": "wamid.123",
                        "type": "text",
                        "text": {"body": "Tengo 500 ha y 50 lucas"},
                    }]
                }
            }]
        }]
    }
    raw_body = json.dumps(payload).encode("utf-8")

    # Bad signature
    res_bad = client.post(
        "/whatsapp/webhook",
        content=raw_body,
        headers={"X-Hub-Signature-256": "sha256=invalid_hash", "Content-Type": "application/json"},
    )
    assert res_bad.status_code == 403

    # Good signature with an agent step that takes time
    good_sig = "sha256=" + hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    agent_started = False
    agent_finished = False

    def mock_ask(self, text, images=None, audio=None):
        nonlocal agent_started, agent_finished
        agent_started = True
        time.sleep(0.2)
        agent_finished = True
        return Reply(text="Respuesta simulada", verified=True, unsupported=[], tool_calls=[], initial_unsupported=[], usage={})

    with patch("dora.agent.Agent.ask", mock_ask), patch("dora.whatsapp.send_text"):
        start_time = time.time()
        res_good = client.post(
            "/whatsapp/webhook",
            content=raw_body,
            headers={"X-Hub-Signature-256": good_sig, "Content-Type": "application/json"},
        )
        elapsed = time.time() - start_time

        assert res_good.status_code == 200
        # Fast-path returns immediately before the 0.2s agent finishes
        assert elapsed < 0.15


def test_text_message_dispatches_calculando_and_agent_answer(monkeypatch):
    # 3. A text message calls the agent once with that text and sends the "calculando" message and then the answer to the same wa_id.
    monkeypatch.setenv("WHATSAPP_TOKEN", "fake_token")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "123456789")

    sent_messages = []

    def mock_send_text(to, body):
        sent_messages.append({"to": to, "body": body})
        return [{"status": "success"}]

    mock_reply = Reply(
        text="Plan óptimo: sembrar 250 ha de maíz y 250 ha de soja.",
        verified=True,
        unsupported=[],
        tool_calls=[],
        initial_unsupported=[],
        usage={},
    )

    msg = {
        "from": "5491144443333",
        "id": "wamid.test1",
        "type": "text",
        "text": {"body": "Tengo 500 ha en Balcarce con 50 lucas."},
    }

    with patch("dora.whatsapp.send_text", side_effect=mock_send_text), \
         patch("dora.agent.Agent.ask", return_value=mock_reply) as mock_agent_ask:
        handle_incoming_message(msg)

        assert mock_agent_ask.call_count == 1
        mock_agent_ask.assert_called_once_with("Tengo 500 ha en Balcarce con 50 lucas.")

        assert len(sent_messages) == 2
        assert sent_messages[0]["to"] == "5491144443333"
        assert "calculando" in sent_messages[0]["body"]

        assert sent_messages[1]["to"] == "5491144443333"
        assert "Plan óptimo" in sent_messages[1]["body"]


def test_audio_message_downloads_and_transcribes(monkeypatch):
    # 4. An audio message downloads the media with the bearer token and passes the transcript to the agent.
    monkeypatch.setenv("WHATSAPP_TOKEN", "fake_token")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "123456789")

    sent_messages = []

    def mock_send_text(to, body):
        sent_messages.append({"to": to, "body": body})
        return [{"status": "success"}]

    mock_reply = Reply(
        text="Plan recibido de audio: 200 ha de trigo.",
        verified=True,
        unsupported=[],
        tool_calls=[],
        initial_unsupported=[],
        usage={},
    )

    audio_captured_path = []

    def mock_agent_ask(self, text, images=None, audio=None):
        audio_captured_path.append(audio)
        return mock_reply

    msg = {
        "from": "5491155556666",
        "id": "wamid.audio1",
        "type": "audio",
        "audio": {"id": "media_audio_999", "mime_type": "audio/ogg; codecs=opus"},
    }

    with patch("dora.whatsapp.download_media", return_value=(b"fake_ogg_bytes", "audio/ogg")) as mock_dl, \
         patch("dora.whatsapp.send_text", side_effect=mock_send_text), \
         patch("dora.agent.Agent.ask", mock_agent_ask):
        handle_incoming_message(msg)

        mock_dl.assert_called_once_with("media_audio_999")
        assert len(audio_captured_path) == 1
        assert audio_captured_path[0] is not None
        assert audio_captured_path[0].endswith(".ogg")
        assert len(sent_messages) == 2
        assert "calculando" in sent_messages[0]["body"]
        assert "Plan recibido" in sent_messages[1]["body"]


def test_long_answer_split_at_paragraph_boundaries(monkeypatch):
    # 5. A 9,000-character answer is sent as 3 messages, split at paragraph boundaries.
    monkeypatch.setenv("WHATSAPP_TOKEN", "test_tok")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "999888")

    # 3 paragraphs of ~3,000 chars each = ~9,000 characters total
    para = "A" * 3000
    long_text = f"{para}\n\n{para}\n\n{para}"
    assert len(long_text) >= 9000

    chunks = split_message(long_text, max_chars=4000)
    assert len(chunks) == 3
    for chunk in chunks:
        assert len(chunk) <= 4000

    # Test via send_text with mocked HTTP requests
    dispatched_payloads = []

    def mock_urlopen(req, context=None, timeout=None):
        body_json = json.loads(req.data.decode("utf-8"))
        dispatched_payloads.append(body_json)
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"messages": [{"id": "wamid.out"}]}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        res = send_text("5491177778888", long_text)
        assert len(res) == 3
        assert len(dispatched_payloads) == 3
        for p in dispatched_payloads:
            assert len(p["text"]["body"]) <= 4000


def test_markdown_formatting_converts_bold_and_headers():
    # 6. **Plan** becomes *Plan*.
    assert markdown_to_whatsapp("**Plan**") == "*Plan*"
    assert markdown_to_whatsapp("__Plan__") == "*Plan*"
    assert markdown_to_whatsapp("# Resumen\n**Plan**") == "*Resumen*\n*Plan*"
    assert markdown_to_whatsapp("El **retorno** fue del 15%.") == "El *retorno* fue del 15%."

    # Tables
    table_md = "| Cultivo | Hectáreas |\n|---|---|\n| Maíz | 200 |\n| Soja | 300 |"
    table_wa = markdown_to_whatsapp(table_md)
    assert "Cultivo: Maíz, Hectáreas: 200" in table_wa
    assert "Cultivo: Soja, Hectáreas: 300" in table_wa


def test_daily_limit_stops_21st_question(monkeypatch):
    # 7. The per-number daily limit stops the 21st question with the polite message.
    monkeypatch.setenv("WHATSAPP_DAILY_LIMIT_PER_NUMBER", "20")
    monkeypatch.setenv("WHATSAPP_DAILY_LIMIT_TOTAL", "200")

    sent_messages = []

    def mock_send_text(to, body):
        sent_messages.append({"to": to, "body": body})
        return [{"status": "success"}]

    mock_reply = Reply(text="OK", verified=True, unsupported=[], tool_calls=[], initial_unsupported=[], usage={})

    msg = {
        "from": "5491188887777",
        "id": "wamid.limit",
        "type": "text",
        "text": {"body": "Pregunta"},
    }

    with patch("dora.whatsapp.send_text", side_effect=mock_send_text), \
         patch("dora.agent.Agent.ask", return_value=mock_reply) as mock_agent_ask:

        # 20 allowed questions
        for _ in range(20):
            handle_incoming_message(msg)

        assert mock_agent_ask.call_count == 20

        # 21st question blocked
        sent_messages.clear()
        handle_incoming_message(msg)

        # Agent not called on 21st question
        assert mock_agent_ask.call_count == 20
        assert len(sent_messages) == 1
        assert "límite diario" in sent_messages[0]["body"]
        assert "20 por día" in sent_messages[0]["body"]


def test_without_whatsapp_token_webhook_not_mounted(monkeypatch):
    # 8. Without WHATSAPP_TOKEN, the app builds and /whatsapp/webhook is not mounted.
    monkeypatch.delenv("WHATSAPP_TOKEN", raising=False)

    app = build_app()
    client = TestClient(app.app)

    res_get = client.get("/whatsapp/webhook")
    assert res_get.status_code == 404

    res_post = client.post("/whatsapp/webhook", json={"test": "data"})
    assert res_post.status_code == 404


def test_reset_command_clears_session():
    # User typing "nuevo" or "reset" starts fresh
    sent_messages = []

    def mock_send_text(to, body):
        sent_messages.append({"to": to, "body": body})
        return [{"status": "success"}]

    msg_reset = {
        "from": "5491133332222",
        "id": "wamid.reset",
        "type": "text",
        "text": {"body": "nuevo"},
    }

    with patch("dora.whatsapp.send_text", side_effect=mock_send_text), \
         patch("dora.agent.Agent.ask") as mock_agent_ask:
        handle_incoming_message(msg_reset)

        assert mock_agent_ask.call_count == 0
        assert len(sent_messages) == 1
        assert "nueva conversación" in sent_messages[0]["body"]
