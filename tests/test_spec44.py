"""Tests for SPEC-44: DORA as a public Claude connector."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import subprocess

import pytest
from starlette.testclient import TestClient

import mcp_server.auth as auth
from mcp_server.server import create_http_app


@pytest.fixture(autouse=True)
def setup_env(tmp_path, monkeypatch):
    """Ensure tests run strictly offline, with isolated records dir and clean rate limits."""
    rec_dir = tmp_path / "records"
    rec_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DORA_RECORDS_DIR", str(rec_dir))
    monkeypatch.setenv("DORA_OFFLINE", "1")
    monkeypatch.setenv("DORA_DISABLE_BACKGROUND_PUBLISHER", "1")
    import dora.feeds as feeds

    monkeypatch.setattr(feeds, "refresh", lambda *args, **kwargs: {"status": "fresh"})
    auth.reset_rate_limits()


def test_1_public_no_header_succeeds(monkeypatch):
    """1. DORA_MCP_PUBLIC=1, no header: initialize and tools/list succeed."""
    monkeypatch.setenv("DORA_MCP_PUBLIC", "1")
    app = create_http_app()
    with TestClient(app) as client:
        r_init = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            },
        )
        assert r_init.status_code == 200
        assert "result" in r_init.json()

        r_tools = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        )
        assert r_tools.status_code == 200
        tools = r_tools.json()["result"]["tools"]
        assert len(tools) >= 14


def test_2_wrong_key_gives_401(monkeypatch):
    """2. DORA_MCP_PUBLIC=1, wrong key: 401."""
    monkeypatch.setenv("DORA_MCP_PUBLIC", "1")
    app = create_http_app()
    with TestClient(app) as client:
        r = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Authorization": "Bearer bad_token_12345"},
        )
        assert r.status_code == 401
        assert r.json() == {"error": "missing or invalid API key"}


def test_3_public_disabled_gives_401(monkeypatch):
    """3. DORA_MCP_PUBLIC=0, no header: 401 (SPEC-40 behaviour)."""
    monkeypatch.setenv("DORA_MCP_PUBLIC", "0")
    app = create_http_app()
    with TestClient(app) as client:
        r = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
        assert r.status_code == 401
        assert r.json() == {"error": "missing or invalid API key"}


def test_4_anonymous_per_ip_limit(monkeypatch):
    """4. Anonymous per-IP limit: the 21st call within a minute from the same X-Forwarded-For returns 429;
    a different IP still passes.
    """
    monkeypatch.setenv("DORA_MCP_PUBLIC", "1")
    app = create_http_app()
    with TestClient(app) as client:
        headers_ip1 = {"X-Forwarded-For": "198.51.100.1"}
        for i in range(20):
            r = client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": i, "method": "tools/list"},
                headers=headers_ip1,
            )
            assert r.status_code == 200, f"Call {i+1} failed"

        # 21st call from same IP -> 429
        r_21 = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 20, "method": "tools/list"},
            headers=headers_ip1,
        )
        assert r_21.status_code == 429
        assert "rate limit exceeded: anonymous use is limited; ask for a key at" in r_21.json()["error"]

        # Different IP -> passes
        headers_ip2 = {"X-Forwarded-For": "198.51.100.2"}
        r_other = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 21, "method": "tools/list"},
            headers=headers_ip2,
        )
        assert r_other.status_code == 200


def test_5_global_anonymous_daily_cap(monkeypatch):
    """5. Global anonymous daily cap: set the cap to 5 by monkeypatching, and the 6th anonymous call
    returns 429 even from a new IP. Keyed calls still pass.
    """
    monkeypatch.setenv("DORA_MCP_PUBLIC", "1")
    monkeypatch.setattr(auth, "ANONYMOUS_DAILY_CAP", 5)

    raw_key, config_line = auth.generate_new_key("testuser")
    monkeypatch.setenv("DORA_MCP_KEYS", config_line)

    app = create_http_app()
    with TestClient(app) as client:
        for i in range(5):
            r = client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": i, "method": "tools/list"},
                headers={"X-Forwarded-For": f"198.51.100.{i+10}"},
            )
            assert r.status_code == 200

        # 6th anonymous call from a brand new IP -> 429
        r_6 = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 6, "method": "tools/list"},
            headers={"X-Forwarded-For": "198.51.100.99"},
        )
        assert r_6.status_code == 429
        assert "rate limit exceeded: anonymous use is limited; ask for a key at" in r_6.json()["error"]

        # Keyed call still passes
        r_keyed = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 7, "method": "tools/list"},
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert r_keyed.status_code == 200


def test_6_solve_plan_record_key_required(tmp_path, monkeypatch):
    """6. Anonymous solve_plan(record=True): returns the error and leaves the queue empty (DORA_RECORDS_DIR in tmp_path).
    The same call with a valid key queues one record.
    """
    rec_dir = tmp_path / "records"
    monkeypatch.setenv("DORA_RECORDS_DIR", str(rec_dir))
    monkeypatch.setenv("DORA_MCP_PUBLIC", "1")
    monkeypatch.setenv("DORA_CHAIN", "base-sepolia")

    raw_key, config_line = auth.generate_new_key("testuser")
    monkeypatch.setenv("DORA_MCP_KEYS", config_line)

    app = create_http_app()
    scenario = {
        "region": "southeast_buenos_aires",
        "area_ha": 500,
        "owned_ha": 500,
        "own_capital_usd": 50000,
    }

    queue_file = rec_dir / "queue.jsonl"
    assert not queue_file.exists() or len(queue_file.read_text().splitlines()) == 0

    with TestClient(app) as client:
        # Anonymous call with record=True
        r_anon = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "solve_plan",
                    "arguments": {"scenario": scenario, "record": True},
                },
            },
        )
        assert r_anon.status_code == 200
        res_data = r_anon.json()["result"]
        content_text = res_data["content"][0]["text"]
        content_json = json.loads(content_text)
        assert content_json["error"] == "recording on-chain needs an API key"
        assert content_json["provenance"]["scenario_hash"] is None
        assert content_json["provenance"]["result_hash"] is None
        assert content_json["provenance"]["signature"] is None

        # Anonymous call with record_outcome
        r_outcome_anon = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {
                    "name": "record_outcome",
                    "arguments": {
                        "plan_record": {"record_id": "test"},
                        "actual": {"hectares": {"soybean": 500.0}},
                    },
                },
            },
        )
        assert r_outcome_anon.status_code == 200
        out_json = json.loads(r_outcome_anon.json()["result"]["content"][0]["text"])
        assert out_json["error"] == "recording on-chain needs an API key"
        assert out_json["status"] == "refused"

        # Queue remains empty
        assert not queue_file.exists() or len(queue_file.read_text().splitlines()) == 0

        # Same call with a valid key
        r_keyed = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "solve_plan",
                    "arguments": {"scenario": scenario, "record": True},
                },
            },
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert r_keyed.status_code == 200
        keyed_data = r_keyed.json()["result"]
        keyed_json = json.loads(keyed_data["content"][0]["text"])
        assert "error" not in keyed_json
        assert "record" in keyed_json
        assert keyed_json["record"]["status"] == "queued"

        # One record in queue
        assert queue_file.exists()
        lines = queue_file.read_text().splitlines()
        assert len(lines) == 1


def test_7_anonymous_record_status_and_verify(monkeypatch):
    """7. Anonymous record_status and verify_record work."""
    monkeypatch.setenv("DORA_MCP_PUBLIC", "1")
    app = create_http_app()
    with TestClient(app) as client:
        # record_status
        r_status = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "record_status",
                    "arguments": {"record_id": "nonexistent-rec-id"},
                },
            },
        )
        assert r_status.status_code == 200
        st_json = json.loads(r_status.json()["result"]["content"][0]["text"])
        assert st_json.get("status") == "not_found"

        # verify_record
        dummy_record = {
            "kind": "dora.plan.v1",
            "record_id": "rec-123",
            "engine_version": "0.40.0",
            "salt": "abc",
        }
        r_verify = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "verify_record",
                    "arguments": {"record": dummy_record},
                },
            },
        )
        assert r_verify.status_code == 200
        v_json = json.loads(r_verify.json()["result"]["content"][0]["text"])
        assert "hash_matches" in v_json


def test_8_key_never_appears_in_logs(monkeypatch, caplog):
    """8. The key never appears in captured logs (caplog), for either a valid or an invalid key."""
    caplog.set_level(logging.DEBUG)

    raw_key, config_line = auth.generate_new_key("secretuser")
    monkeypatch.setenv("DORA_MCP_KEYS", config_line)
    monkeypatch.setenv("DORA_MCP_PUBLIC", "1")

    secret_token_valid = raw_key
    secret_token_invalid = "dora_super_secret_invalid_key_xyz_123"

    app = create_http_app()
    with TestClient(app) as client:
        client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Authorization": f"Bearer {secret_token_valid}"},
        )
        client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers={"Authorization": f"Bearer {secret_token_invalid}"},
        )

    assert secret_token_valid not in caplog.text
    assert secret_token_invalid not in caplog.text


def test_9_clean_dora_data():
    """9. After the suite, git status --porcelain dora/data observatory is empty."""
    proc = subprocess.run(
        ["git", "status", "--porcelain", "dora/data", "observatory"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stdout.strip() == ""
