"""Tests for SPEC-41: On-chain plan record & reputation (EAS on Base)."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from dora.record import (
    build_outcome_record,
    build_plan_record,
    canonical,
    record_hash,
)
import mcp_server.server as srv


def test_1_hash():
    """1. record_hash is stable across two runs and two processes, changes with salt/scenario/result/version,
    canonical normalizes CRLF and LF.
    """
    sc_val = {"region": "southeast_buenos_aires", "area_ha": 1000}
    sc_sent = {"region": "southeast_buenos_aires"}
    res = {"npv_usd": 123456.78, "hectares": {"soybean": 500.0}}
    prov = {"scenario_hash": "a" * 64, "result_hash": "b" * 64, "checks": []}
    rec1 = build_plan_record(
        sc_val,
        sc_sent,
        res,
        prov,
        salt="1" * 64,
        record_id="rec-1",
        created_at="2026-11-05T00:00:00Z",
    )
    rec2 = build_plan_record(
        sc_val,
        sc_sent,
        res,
        prov,
        salt="1" * 64,
        record_id="rec-1",
        created_at="2026-11-05T00:00:00Z",
    )
    h1 = record_hash(rec1)
    h2 = record_hash(rec2)
    assert h1 == h2

    # Two processes
    code = f"""
import json
from dora.record import record_hash
rec = json.loads({json.dumps(json.dumps(rec1))})
print(record_hash(rec))
"""
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert proc.stdout.strip() == h1

    # Changes with salt
    rec_salt = copy.deepcopy(rec1)
    rec_salt["salt"] = "2" * 64
    assert record_hash(rec_salt) != h1

    # Changes with scenario
    rec_sc = copy.deepcopy(rec1)
    rec_sc["scenario"]["area_ha"] = 1200
    assert record_hash(rec_sc) != h1

    # Changes with result
    rec_res = copy.deepcopy(rec1)
    rec_res["result"]["npv_usd"] = 999999.0
    assert record_hash(rec_res) != h1

    # Changes with engine_version
    rec_v = copy.deepcopy(rec1)
    rec_v["engine_version"] = "9.9.9"
    assert record_hash(rec_v) != h1

    # CRLF and LF canonical normalisation
    d1 = {"text": "line1\r\nline2"}
    d2 = {"text": "line1\nline2"}
    assert canonical(d1) == canonical(d2)


def test_2_non_blocking(monkeypatch, tmp_path):
    """2. With a publisher that sleeps 5s, solve_plan(record=True) returns in under 1s plus solve time,
    with status: queued, and its result equals the one with record=False.
    """
    import threading

    rec_dir = tmp_path / "records"
    monkeypatch.setenv("DORA_RECORDS_DIR", str(rec_dir))
    monkeypatch.setenv("DORA_CHAIN", "base-sepolia")

    import dora_chain.queue as queue_mod

    # A background publisher that holds the lock and sleeps 5s
    lock = queue_mod.FileLock(rec_dir / ".publisher.lock")
    assert lock.acquire() is True

    def slow_publisher():
        time.sleep(5)
        lock.release()

    th = threading.Thread(target=slow_publisher, daemon=True)
    th.start()

    scenario = {"region": "southeast_buenos_aires", "owned_ha": 500, "own_capital_usd": 50000}

    # Warm up web3 import and ensure chain configured
    queue_mod.is_chain_configured()

    # Baseline solve time
    t_base0 = time.time()
    out_norec = srv.solve_plan(scenario, record=False)
    solve_time = time.time() - t_base0

    t0 = time.time()
    out_rec = srv.solve_plan(scenario, record=True)
    dur = time.time() - t0

    assert dur < solve_time + 1.0  # in under 1s plus solve time
    assert out_rec.get("record", {}).get("status") == "queued"
    assert "record_id" in out_rec["record"]
    assert "record_hash" in out_rec["record"]

    # Result equals one with record=False
    assert out_rec["result"] == out_norec["result"]


def test_3_only_verified_plans(monkeypatch, tmp_path):
    """3. A monkeypatched failing plan_is_optimal -> not_recorded with the check's name; nothing queued."""
    rec_dir = tmp_path / "records"
    monkeypatch.setenv("DORA_RECORDS_DIR", str(rec_dir))
    monkeypatch.setenv("DORA_CHAIN", "base-sepolia")

    import dora.plan_check as plan_check

    monkeypatch.setattr(
        plan_check,
        "evaluate_plan",
        lambda *args, **kwargs: {
            "feasible": False,
            "gap_usd": 50000.0,
            "violations": ["constraint violated"],
        },
    )

    scenario = {"region": "southeast_buenos_aires", "owned_ha": 500, "own_capital_usd": 50000}
    out = srv.solve_plan(scenario, record=True)
    assert out.get("record", {}).get("status") == "not_recorded"
    assert "plan_is_optimal" in out["record"].get("reason", "")

    queue_file = rec_dir / "queue.jsonl"
    assert not queue_file.exists() or len(queue_file.read_text().strip()) == 0


def test_4_not_configured(monkeypatch):
    """4. Without DORA_CHAIN (and with web3 hidden via sys.modules) -> not_configured, solve_plan still works."""
    monkeypatch.delenv("DORA_CHAIN", raising=False)
    monkeypatch.setitem(sys.modules, "web3", None)

    scenario = {"region": "southeast_buenos_aires", "owned_ha": 500, "own_capital_usd": 50000}
    out = srv.solve_plan(scenario, record=True)
    assert out.get("record") == {"status": "not_configured"}
    assert "result" in out


def test_5_abi():
    """5. The encoded data of a plan and an outcome attestation decode back to the same fields; null errors encode as int32 min."""
    import dora_chain.eas as eas

    plan_rec = {
        "engine_version": "0.40.0",
        "engine_fingerprint": "f" * 64,
        "scenario": {"region": "southeast_buenos_aires"},
        "assumptions": {"season": 2026},
        "salt": "1" * 64,
        "record_id": "test-id",
    }
    encoded_plan = eas.encode_plan_data(plan_rec)
    decoded_plan = eas.decode_plan_data(encoded_plan)
    assert decoded_plan["engineVersion"] == "0.40.0"
    assert decoded_plan["region"] == "southeast_buenos_aires"
    assert decoded_plan["season"] == 2026
    assert decoded_plan["recordHash"].startswith("0x")

    outcome_rec = {
        "plan_record_hash": "a" * 64,
        "errors": {
            "aggregate": {
                "yield_error_pct": None,
                "price_error_pct": 5.25,
                "margin_error_pct": None,
                "hectares_match_pct": 100.0,
            },
            "followed_plan": "yes",
        },
        "salt": "2" * 64,
        "record_id": "out-id",
    }
    encoded_out = eas.encode_outcome_data(outcome_rec)
    decoded_out = eas.decode_outcome_data(encoded_out)
    assert decoded_out["yieldErrorBps"] == eas.INT32_MIN
    assert decoded_out["priceErrorBps"] == 525
    assert decoded_out["marginErrorBps"] == eas.INT32_MIN
    assert decoded_out["hectaresMatchBps"] == 10000
    assert decoded_out["followedPlan"] == 3


def test_6_queue_and_retry(monkeypatch, tmp_path):
    """6. Fake chain that fails twice then succeeds -> published on attempt 3; persistent failure -> failed; file lock."""
    rec_dir = tmp_path / "records"
    monkeypatch.setenv("DORA_RECORDS_DIR", str(rec_dir))
    monkeypatch.setenv("DORA_CHAIN", "base-sepolia")

    import dora_chain.queue as queue_mod

    attempts = [0]

    def hook_fail_twice(rec, ref_uid):
        attempts[0] += 1
        if attempts[0] < 3:
            return {"status": "failed", "last_error": f"RPC timeout attempt {attempts[0]}"}
        return {
            "status": "published",
            "tx_hash": "0x1111",
            "attestation_uid": "0x2222",
            "gas_used": 150000,
            "fee_wei": 1000000,
        }

    queue_mod.set_chain_call_hook(hook_fail_twice)
    monkeypatch.setattr(queue_mod, "BACKOFF_SECONDS", [0, 0, 0])

    rec1 = {"record_id": "rec-retry", "kind": "dora.plan.v1", "salt": "123"}
    queue_mod.enqueue_record(rec1)

    queue_mod.drain_queue()
    st1 = queue_mod.get_record_status("rec-retry")
    assert st1["status"] == "queued"
    assert st1["attempts"] == 1

    queue_mod.drain_queue()
    st2 = queue_mod.get_record_status("rec-retry")
    assert st2["status"] == "queued"
    assert st2["attempts"] == 2

    queue_mod.drain_queue()
    st3 = queue_mod.get_record_status("rec-retry")
    assert st3["status"] == "published"
    assert st3["tx_hash"] == "0x1111"
    assert st3["attestation_uid"] == "0x2222"
    assert st3["attempts"] == 3

    # Persistent failure
    def hook_always_fails(rec, ref_uid):
        return {"status": "failed", "last_error": "Permanent failure"}

    queue_mod.set_chain_call_hook(hook_always_fails)
    rec_fail = {"record_id": "rec-perm-fail", "kind": "dora.plan.v1", "salt": "456"}
    queue_mod.enqueue_record(rec_fail)

    queue_mod.drain_queue()
    queue_mod.drain_queue()
    queue_mod.drain_queue()
    st_perm = queue_mod.get_record_status("rec-perm-fail")
    assert st_perm["status"] == "failed"
    assert st_perm["last_error"] == "Permanent failure"
    assert st_perm["attempts"] == 3

    # File lock prevents concurrent publishers
    lock = queue_mod.FileLock(rec_dir / ".publisher.lock")
    assert lock.acquire() is True
    assert queue_mod.drain_queue() == []
    lock.release()

    queue_mod.set_chain_call_hook(None)


def test_7_daily_cap(monkeypatch, tmp_path):
    """7. With DORA_CHAIN_MAX_TX_PER_DAY=2, third entry waits queued with cap message."""
    rec_dir = tmp_path / "records"
    monkeypatch.setenv("DORA_RECORDS_DIR", str(rec_dir))
    monkeypatch.setenv("DORA_CHAIN", "base-sepolia")
    monkeypatch.setenv("DORA_CHAIN_MAX_TX_PER_DAY", "2")

    import dora_chain.queue as queue_mod

    monkeypatch.setattr(queue_mod, "BACKOFF_SECONDS", [0, 0, 0])
    queue_mod.set_chain_call_hook(
        lambda rec, ref_uid: {"status": "published", "tx_hash": "0x99", "attestation_uid": "0x88"}
    )

    for i in range(1, 4):
        queue_mod.enqueue_record({"record_id": f"cap-{i}", "kind": "dora.plan.v1", "salt": str(i)})

    queue_mod.drain_queue(max_items=10)

    st1 = queue_mod.get_record_status("cap-1")
    st2 = queue_mod.get_record_status("cap-2")
    st3 = queue_mod.get_record_status("cap-3")

    assert st1["status"] == "published"
    assert st2["status"] == "published"
    assert st3["status"] == "queued"
    assert "Daily cap" in st3["last_error"]

    queue_mod.set_chain_call_hook(None)


def test_8_mainnet_guard(monkeypatch):
    """8. DORA_CHAIN=base without DORA_CHAIN_ALLOW_MAINNET=1 raises refusal."""
    from dora_chain.config import get_chain_config

    monkeypatch.setenv("DORA_CHAIN", "base")
    monkeypatch.delenv("DORA_CHAIN_ALLOW_MAINNET", raising=False)

    with pytest.raises(PermissionError) as exc_info:
        get_chain_config()
    assert "DORA_CHAIN_ALLOW_MAINNET=1" in str(exc_info.value)


def test_9_outcome_errors():
    """9. Exact errors from spec: soy 1,000 ha, planned yield 3.0, price 320; actual 2.7, price 336."""
    import dora_chain.eas as eas

    plan_record = {
        "record_id": "plan-123",
        "result": {
            "hectares": {"soybean": 1000.0},
            "npv_usd": 300000.0,
        },
        "planned": {
            "yield_t_ha": {"soybean": 3.0},
            "mean_sale_price_usd_t": {"soybean": 320.0},
        },
        "salt": "abc",
    }
    actual = {
        "hectares": {"soybean": 1000.0},
        "yield_t_ha": {"soybean": 2.7},
        "price_received_usd_t": {"soybean": 336.0},
    }

    outcome = build_outcome_record(plan_record, actual)
    errs = outcome["errors"]

    assert errs["yield_error_pct"] == -10.0
    assert errs["price_error_pct"] == 5.0
    assert errs["hectares_match_pct"] == 100.0
    assert errs["margin_error_pct"] is None
    assert errs["followed_plan"] == "unknown"

    encoded = eas.encode_outcome_data(outcome)
    decoded = eas.decode_outcome_data(encoded)
    assert decoded["yieldErrorBps"] == -1000
    assert decoded["priceErrorBps"] == 500
    assert decoded["marginErrorBps"] == eas.INT32_MIN
    assert decoded["hectaresMatchBps"] == 10000
    assert decoded["followedPlan"] == 0


def test_10_record_outcome_tamper(monkeypatch, tmp_path):
    """10. Tampered hectare in plan record -> refused with hash mismatch."""
    rec_dir = tmp_path / "records"
    monkeypatch.setenv("DORA_RECORDS_DIR", str(rec_dir))
    monkeypatch.setenv("DORA_CHAIN", "base-sepolia")

    scenario = {"region": "southeast_buenos_aires", "owned_ha": 500, "own_capital_usd": 50000}
    plan_out = srv.solve_plan(scenario, record=True)
    plan_rec = plan_out["record"]["record"]

    tampered_plan = copy.deepcopy(plan_rec)
    tampered_plan["result"]["hectares"]["soybean"] = 9999.0

    actual = {"hectares": {"soybean": 100.0}, "yield_t_ha": {"soybean": 3.0}}
    res = srv.record_outcome(tampered_plan, actual)
    assert res.get("status") == "refused"
    assert "hash does not match" in res.get("error", "")

    queue_file = rec_dir / "queue.jsonl"
    lines = queue_file.read_text().splitlines()
    assert len(lines) == 1


def test_11_verify_record(monkeypatch):
    """11. verify_record with faked GraphQL answers: right record -> all true; different attester -> attester_is_dora: False."""
    import dora_chain.eas as eas

    rec = {
        "kind": "dora.plan.v1",
        "record_id": "rec-v1",
        "engine_version": "0.40.0",
        "salt": "123",
    }
    rec_h = record_hash(rec)
    operator = "0x1234567890123456789012345678901234567890"
    monkeypatch.setenv("DORA_OPERATOR_ADDRESS", operator)

    mock_good = {
        "id": "0xatt1",
        "attester": operator,
        "time": 1700000000,
        "schemaId": "0xschema1",
        "data": "0x" + rec_h + "0000",
    }
    eas.set_graphql_hook(lambda record_hash=None, uid=None: mock_good)

    v1 = srv.verify_record(rec)
    assert v1["hash_matches"] is True
    assert v1["on_chain"] is True
    assert v1["attester_is_dora"] is True
    assert v1["attested_at"] is not None
    assert "easscan.org" in v1["easscan_url"]

    mock_bad = dict(mock_good, attester="0x9999999999999999999999999999999999999999")
    eas.set_graphql_hook(lambda record_hash=None, uid=None: mock_bad)

    v2 = srv.verify_record(rec)
    assert v2["hash_matches"] is True
    assert v2["on_chain"] is True
    assert v2["attester_is_dora"] is False

    eas.set_graphql_hook(None)


def test_12_reputation():
    """12. Reputation summary calculates medians, handles worst outcomes and zero outcomes."""
    from dora_chain.reputation import compute_reputation_summary

    plans = [{"id": f"p{i}", "kind": "dora.plan.v1"} for i in range(1, 4)]
    outcomes = [
        {
            "id": "o1",
            "refUID": "p1",
            "errors": {
                "aggregate": {
                    "yield_error_pct": 5.0,
                    "price_error_pct": -4.0,
                    "margin_error_pct": 6.0,
                    "hectares_match_pct": 100.0,
                },
                "followed_plan": "yes",
            },
        },
        {
            "id": "o2",
            "refUID": "p2",
            "errors": {
                "aggregate": {
                    "yield_error_pct": -40.0,
                    "price_error_pct": 15.0,
                    "margin_error_pct": -35.0,
                    "hectares_match_pct": 80.0,
                },
                "followed_plan": "partly",
            },
        },
    ]

    summary = compute_reputation_summary(plans, outcomes)
    assert summary["plans_recorded"] == 3
    assert summary["outcomes_recorded"] == 2
    metrics = summary["metrics"]
    assert metrics["yield_error"]["count"] == 2
    assert metrics["yield_error"]["median_abs_error_pct"] == 22.5
    assert metrics["yield_error"]["share_within_10pct"] == 50.0

    assert summary["outcomes"][0]["uid"] == "o2"
    assert summary["outcomes"][0]["yield_error_pct"] == -40.0
    assert summary["outcomes"][1]["uid"] == "o1"

    empty = compute_reputation_summary(plans, [])
    assert empty["outcomes_recorded"] == 0
    assert "No outcomes" in empty["message"]
    assert empty["metrics"] == {}


def test_13_no_secrets_out(monkeypatch, tmp_path):
    """13. Grep logs, status files, and outputs for private key: verified absent."""
    rec_dir = tmp_path / "records"
    monkeypatch.setenv("DORA_RECORDS_DIR", str(rec_dir))
    monkeypatch.setenv("DORA_CHAIN", "base-sepolia")

    fake_privkey = "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    monkeypatch.setenv("DORA_CHAIN_PRIVATE_KEY", fake_privkey)

    import dora_chain.queue as queue_mod

    monkeypatch.setattr(queue_mod, "BACKOFF_SECONDS", [0, 0, 0])
    queue_mod.set_chain_call_hook(
        lambda rec, ref_uid: {"status": "published", "tx_hash": "0x123", "attestation_uid": "0x456"}
    )

    rec = {"record_id": "sec-check", "kind": "dora.plan.v1", "salt": "789"}
    queue_mod.enqueue_record(rec)
    queue_mod.drain_queue()

    st = queue_mod.get_record_status("sec-check")
    status_str = json.dumps(st)
    assert fake_privkey not in status_str
    assert fake_privkey[2:] not in status_str

    for f in rec_dir.rglob("*"):
        if f.is_file():
            content = f.read_text(encoding="utf-8")
            assert fake_privkey not in content
            assert fake_privkey[2:] not in content

    queue_mod.set_chain_call_hook(None)
