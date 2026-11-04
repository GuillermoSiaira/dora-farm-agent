"""Acceptance tests for SPEC-08: Photo and voice input."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dora.agent import Agent
from dora.engine import optimize
from dora.media import build_user_content, encode_image, transcribe
from dora.scenario import Scenario
from dora.tools import build_scenario, record_document, run_tool


# 1. Building a user message with two images produces two image_url parts with
#    valid base64 data URLs and the text part.
def test_user_message_with_two_images(tmp_path):
    img1 = tmp_path / "invoice1.jpg"
    img2 = tmp_path / "receipt2.png"

    sample_bytes_1 = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"fake-jpeg-content"
    sample_bytes_2 = b"\x89PNG\r\n\x1a\n" + b"fake-png-content"

    img1.write_bytes(sample_bytes_1)
    img2.write_bytes(sample_bytes_2)

    text = "Aquí adjunto la factura de fertilizante y el remito de semilla."
    parts = build_user_content(text, [img1, img2])

    assert isinstance(parts, list)
    assert len(parts) == 3

    # Part 0 is text
    assert parts[0]["type"] == "text"
    assert parts[0]["text"] == text

    # Parts 1 and 2 are image_url
    assert parts[1]["type"] == "image_url"
    url1 = parts[1]["image_url"]["url"]
    assert url1.startswith("data:image/jpeg;base64,")
    b64_1 = url1.split(",", 1)[1]
    assert base64.b64decode(b64_1) == sample_bytes_1

    assert parts[2]["type"] == "image_url"
    url2 = parts[2]["image_url"]["url"]
    assert url2.startswith("data:image/png;base64,")
    b64_2 = url2.split(",", 1)[1]
    assert base64.b64decode(b64_2) == sample_bytes_2


# 2. record_document with a fertilizer invoice of 21,000 USD and no hectares
#    returns "missing: hectares" and replaces nothing.
def test_record_document_missing_hectares():
    items = [{"concept": "fertilizer", "amount": 21000.0, "currency": "USD"}]
    res = record_document(kind="invoice", items=items, scenario=None)

    assert "missing: hectares" in res["missing"]
    assert len(res["replaces"]) == 0
    assert len(res["proposals"]) == 0

    # Also test via run_tool
    raw = run_tool("record_document", json.dumps({"kind": "invoice", "items": items}))
    parsed = json.loads(raw)
    assert "missing: hectares" in parsed["missing"]
    assert len(parsed["replaces"]) == 0


# 3. The same invoice with area_ha: 100 in the scenario proposes fertilizer = 210 USD/ha.
#    If the regional default is 214.2, there is no deviation flag. With 642,600 USD (3×),
#    the deviation is flagged.
def test_record_document_hectares_and_deviation():
    # Case A: 21,000 USD on 100 ha -> 210 USD/ha (close to default 214.2)
    items_normal = [{"concept": "fertilizer", "crop": "wheat", "amount": 21000.0, "currency": "USD"}]
    res_normal = record_document(kind="invoice", items=items_normal, scenario={"area_ha": 100.0})

    assert len(res_normal["proposals"]) == 1
    prop = res_normal["proposals"][0]
    assert prop["item"] == "fertilizer"
    assert prop["proposed_usd_ha"] == 210.0
    assert prop["default_usd_ha"] == 214.2
    assert prop["deviation_flag"] is False
    assert len(res_normal["replaces"]) == 1
    assert "210" in res_normal["replaces"][0]

    # Case B: 642,600 USD on 100 ha -> 6,426 USD/ha (3x / huge deviation)
    items_huge = [{"concept": "fertilizer", "crop": "wheat", "amount": 642600.0, "currency": "USD"}]
    res_huge = record_document(kind="invoice", items=items_huge, scenario={"area_ha": 100.0})

    assert len(res_huge["proposals"]) == 1
    prop_huge = res_huge["proposals"][0]
    assert prop_huge["item"] == "fertilizer"
    assert prop_huge["proposed_usd_ha"] == 6426.0
    assert prop_huge["deviation_flag"] is True
    assert "flag" in prop_huge or "warning" in prop_huge


# 4. An ARS invoice is converted with a mocked BCRA rate, and the rate and date
#    appear in the output.
def test_record_document_ars_conversion():
    mock_rate = 1420.0
    mock_date = "2026-06-01"

    items_ars = [{
        "concept": "fertilizer",
        "crop": "wheat",
        "amount": 29820000.0,  # 29,820,000 ARS / 1,420 = 21,000 USD
        "currency": "ARS",
        "date": mock_date,
    }]

    with patch("dora.feeds.BcraFxFeed.fetch_rate_and_date", return_value=(mock_rate, mock_date)):
        res = record_document(kind="invoice", items=items_ars, scenario={"area_ha": 100.0})

    assert res.get("rate") == mock_rate or res.get("bcra_rate") == mock_rate
    assert res.get("date") == mock_date or res.get("bcra_date") == mock_date
    assert "fx_conversion" in res
    assert res["fx_conversion"]["rate"] == mock_rate
    assert res["fx_conversion"]["date"] == mock_date
    assert res["fx_conversion"]["amount_usd"] == 21000.0

    # The proposal converted to 210 USD/ha
    assert len(res["proposals"]) == 1
    assert res["proposals"][0]["proposed_usd_ha"] == 210.0


# 5. costs_override changes payments_per_ha only for the overridden items,
#    and NPV moves in the expected direction (a higher cost gives a lower NPV).
def test_costs_override_payments_and_npv():
    sc_base = Scenario()
    res_base = optimize(sc_base)

    base_wheat_pmt = sc_base.payments_per_ha("wheat")
    base_corn_pmt = sc_base.payments_per_ha("corn")

    # Increase fertilizer cost for wheat from 214.2 to 300.0 USD/ha
    sc_ov = Scenario(costs_override={"wheat": {"fertilizer": 300.0}})
    ov_wheat_pmt = sc_ov.payments_per_ha("wheat")
    ov_corn_pmt = sc_ov.payments_per_ha("corn")
    res_ov = optimize(sc_ov)

    # 1. Corn payments must be completely unchanged
    assert ov_corn_pmt == base_corn_pmt

    # 2. Wheat payments must be higher only in fertilizer periods
    assert ov_wheat_pmt != base_wheat_pmt
    assert sum(ov_wheat_pmt.values()) > sum(base_wheat_pmt.values())

    # 3. Higher cost strictly reduces or maintains NPV
    assert res_ov.npv < res_base.npv

    # 4. build_scenario shows origin "farmer document"
    sc_dict = build_scenario({"costs_override": {"wheat": {"fertilizer": 300.0}}})["scenario"]
    assert "costs_override" in sc_dict
    assert sc_dict["costs_override"]["origin"] == "farmer document"
    assert sc_dict["costs_override"]["value"] == {"wheat": {"fertilizer": 300.0}}


# 6. transcribe without a backend returns the clear message.
#    With a mocked backend, the transcript reaches the agent as user text.
def test_transcribe_without_and_with_backend(tmp_path):
    audio_file = tmp_path / "voice_note.m4a"
    audio_file.write_bytes(b"dummy-audio-bytes")

    # A: Without a backend configured
    with patch.dict(os.environ, {}, clear=True):
        msg = transcribe(audio_file)
        assert msg == "voice notes need a transcription model"

    # B: With mocked backend, transcript reaches agent as user text
    mock_transcript = "Sembré 120 ha de trigo y tengo 40 mil dólares de capital."

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices = [
        MagicMock(message=MagicMock(content="Entendido, 120 ha de trigo y 40.000 USD.", tool_calls=None))
    ]
    mock_resp.usage = MagicMock(prompt_tokens=10, completion_tokens=10, total_tokens=20)
    mock_client.chat.completions.create.return_value = mock_resp

    with patch("dora.media.transcribe", return_value=mock_transcript):
        agent = Agent(client=mock_client, model="test-model", use_verifier=False)
        reply = agent.ask(text="Adjunto audio:", audio=str(audio_file))

        # Check transcript is included in user_texts and messages
        assert any(mock_transcript in ut for ut in agent.user_texts)
        last_user_msg = [m for m in agent.messages if m["role"] == "user"][-1]
        assert mock_transcript in last_user_msg["content"]
        assert reply.text == "Entendido, 120 ha de trigo y 40.000 USD."


# Meta's speech-to-text (E3): WAV mono 16-bit at 24 kHz, sent as multipart to /asr/transcribe.
def test_transcribe_meta_format(tmp_path):
    import io
    import wave

    import numpy as np
    from scipy.io import wavfile

    src = tmp_path / "nota.wav"
    t = np.arange(22050) / 22050
    tone = (0.3 * np.sin(2 * np.pi * 440 * t) * 32767).astype("int16")
    wavfile.write(str(src), 22050, np.stack([tone, tone], axis=1))   # 1 s, stereo, 22.05 kHz

    from dora.media import to_asr_wav
    with wave.open(io.BytesIO(to_asr_wav(src))) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 24000)
        assert abs(w.getnframes() - 24000) <= 1

    sent = {}

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"transcript": "Tengo 500 hectáreas.", "turns": []}).encode()

    def fake_urlopen(req, timeout=None, context=None):
        sent["url"], sent["body"] = req.full_url, req.data
        return Resp()

    env = {"DORA_TRANSCRIBE_MODEL": "muse-voice-transcribe-1.0", "DORA_API_BASE": "https://api.meta.ai/v1", "DORA_API_KEY": "x"}
    with patch.dict(os.environ, env), patch("urllib.request.urlopen", fake_urlopen):
        assert transcribe(src) == "Tengo 500 hectáreas."
    assert sent["url"] == "https://api.meta.ai/v1/asr/transcribe"
    assert b'name="request"' in sent["body"] and b'"model": "muse-voice-transcribe-1.0"' in sent["body"]
    assert b'name="audio"' in sent["body"] and b"RIFF" in sent["body"]
