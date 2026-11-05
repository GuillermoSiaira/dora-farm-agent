"""Tests for SPEC-40: DORA as an MCP server."""
from __future__ import annotations

import asyncio
import copy
import json
import os
from pathlib import Path
import shutil
import sys

import pytest
from starlette.testclient import TestClient

from dora.scenario import ScenarioError
import dora.tools as tools
from dora.version import ENGINE_VERSION, _FINGERPRINT_CACHE, engine_fingerprint
import mcp_server.auth as auth
from mcp_server.provenance import canonical, sha256_canonical
import mcp_server.server as srv
from mcp_server.server import create_http_app, mcp
import subprocess

@pytest.fixture(autouse=True)
def no_live_feeds(monkeypatch):
    """Ensure tests are strictly offline and never refresh price curves or touch dora/data."""
    monkeypatch.setenv("DORA_OFFLINE", "1")
    import dora.feeds as feeds
    monkeypatch.setattr(feeds, "refresh", lambda *args, **kwargs: {"status": "fresh"})



def test_1_tool_list():
    """1. The server lists exactly the 9 tools of section 3 and the 2 resources; no other dora.tools function is exposed."""
    async def _run():
        tl = await mcp.list_tools()
        tool_names = sorted([t.name for t in tl])
        expected_tools = sorted([
            "build_scenario",
            "update_scenario",
            "solve_plan",
            "shadow_prices",
            "break_even_prices",
            "compare_rent_out",
            "evaluate_plan",
            "sensitivity",
            "check_text",
            "record_status",
            "record_outcome",
            "verify_record",
        ])
        assert tool_names == expected_tools

        rl = await mcp.list_resources()
        resource_uris = sorted([str(r.uri) for r in rl])
        expected_resources = sorted(["dora://modeling-guide", "dora://regions"])
        assert resource_uris == expected_resources

    asyncio.run(_run())


def test_2_hash_is_stable():
    """2. solve_plan twice on SE BA 500 ha owned, 50,000 USD gives the same scenario_hash and result_hash;
    the same scenario with a default made explicit gives the same scenario_hash; changing area_ha changes it.
    """
    sc1 = {"region": "southeast_buenos_aires", "owned_ha": 500, "own_capital_usd": 50000}
    r1 = srv.solve_plan(sc1)
    r2 = srv.solve_plan(sc1)

    assert r1["provenance"]["scenario_hash"] == r2["provenance"]["scenario_hash"]
    assert r1["provenance"]["result_hash"] == r2["provenance"]["result_hash"]

    sc_default = {"region": "southeast_buenos_aires", "owned_ha": 500, "own_capital_usd": 50000, "deposit_rate_annual": 0.04}
    r_default = srv.solve_plan(sc_default)
    assert r_default["provenance"]["scenario_hash"] == r1["provenance"]["scenario_hash"]

    sc_changed = {"region": "southeast_buenos_aires", "owned_ha": 600, "own_capital_usd": 50000}
    r_changed = srv.solve_plan(sc_changed)
    assert r_changed["provenance"]["scenario_hash"] != r1["provenance"]["scenario_hash"]


def test_3_same_numbers_as_chat():
    """3. solve_plan(...)["result"] equals tools.evaluate_season(...) for 3 scenarios."""
    scenarios = [
        {"region": "southeast_buenos_aires", "owned_ha": 500, "own_capital_usd": 50000},
        {"region": "pampas_core", "owned_ha": 2000, "own_capital_usd": 500000},
        {"region": "southeast_buenos_aires", "rented_land": True, "area_ha": 300, "own_capital_usd": 30000},
    ]
    for sc in scenarios:
        res_mcp = srv.solve_plan(sc, lang="es")["result"]
        res_chat = tools.evaluate_season(sc, lang="es")
        assert res_mcp == res_chat


def test_4_plan_is_optimal():
    """4. plan_is_optimal passes on the 3 scenarios; with a monkeypatched evaluate_season
    that returns hectares moved 100 ha from soy to corn, it fails.
    """
    scenarios = [
        {"region": "southeast_buenos_aires", "owned_ha": 500, "own_capital_usd": 50000},
        {"region": "pampas_core", "owned_ha": 2000, "own_capital_usd": 500000},
        {"region": "southeast_buenos_aires", "rented_land": True, "area_ha": 300, "own_capital_usd": 30000},
    ]
    for sc in scenarios:
        res = srv.solve_plan(sc)
        chk = next(c for c in res["provenance"]["checks"] if c["name"] == "plan_is_optimal")
        assert chk["passed"] is True

    orig_eval = tools.evaluate_season
    def fake_eval(sc, lang="en"):
        out = orig_eval(sc, lang=lang)
        ha = dict(out["hectares"])
        if "soybean" in ha:
            ha["soybean"] = max(0.0, ha["soybean"] - 100.0)
            ha["corn"] = ha.get("corn", 0.0) + 100.0
        out["hectares"] = ha
        return out

    tools.evaluate_season = fake_eval
    try:
        res_bad = srv.solve_plan(scenarios[0])
        chk_bad = next(c for c in res_bad["provenance"]["checks"] if c["name"] == "plan_is_optimal")
        assert chk_bad["passed"] is False
    finally:
        tools.evaluate_season = orig_eval


def test_5_scenario_inputs():
    """5. farmer_said=["tengo 500 ha en el sudeste"] and a scenario with own_capital_usd: 80000 ->
    the check fails and names own_capital_usd; with farmer_said=["tengo 500 ha en el sudeste y 80 mil dólares"]
    it passes; with no farmer_said it is passed: null.
    """
    sc = {"region": "southeast_buenos_aires", "area_ha": 500, "own_capital_usd": 80000}

    # Fails
    r1 = srv.solve_plan(sc, farmer_said=["tengo 500 ha en el sudeste"])
    chk1 = next(c for c in r1["provenance"]["checks"] if c["name"] == "scenario_inputs")
    assert chk1["passed"] is False
    assert any(d["field"] == "own_capital_usd" for d in chk1["detail"])

    # Passes
    r2 = srv.solve_plan(sc, farmer_said=["tengo 500 ha en el sudeste y 80 mil dólares"])
    chk2 = next(c for c in r2["provenance"]["checks"] if c["name"] == "scenario_inputs")
    assert chk2["passed"] is True
    assert chk2["detail"] == []

    # None
    r3 = srv.solve_plan(sc, farmer_said=None)
    chk3 = next(c for c in r3["provenance"]["checks"] if c["name"] == "scenario_inputs")
    assert chk3["passed"] is None


def test_6_compare_rent_out():
    """6. compare_rent_out on SE BA 500 ha owned returns tenure_comparison with tenure_consistent passed;
    on a rented-only farm returns the note and no check.
    """
    sc_owned = {"region": "southeast_buenos_aires", "owned_ha": 500, "own_capital_usd": 50000}
    out_owned = srv.compare_rent_out(sc_owned, lang="es")
    assert "tenure_comparison" in out_owned["result"]
    chk_owned = next(c for c in out_owned["provenance"]["checks"] if c["name"] == "tenure_consistent")
    assert chk_owned["passed"] is True

    sc_rented = {"region": "southeast_buenos_aires", "rented_land": True, "area_ha": 300, "own_capital_usd": 30000}
    out_rented = srv.compare_rent_out(sc_rented, lang="es")
    assert out_rented["result"].get("note") == "Rent comparison applies to owned land."
    assert out_rented["provenance"]["checks"] == []


def test_7_break_even_prices():
    """7. break_even_prices on SE BA 500 ha: one check per crop not in the plan, passed equal to the tool's verified."""
    sc = {"region": "southeast_buenos_aires", "owned_ha": 500, "own_capital_usd": 50000}
    out = srv.break_even_prices(sc, verify=True, lang="es")
    crops_not_in_plan = out["result"]["crops"]
    checks = out["provenance"]["checks"]
    assert len(checks) == len(crops_not_in_plan)
    for c, chk in zip(crops_not_in_plan, checks):
        assert chk["name"] == f"break_even_{c['crop']}"
        assert chk["passed"] == c["verified"]


def test_8_check_text():
    """8. check_text:
    (a) A text quoting the NPV and the soy hectares from a solve_plan result -> supported: true.
    (b) The same text with one invented number ("ganás 999.999 USD") -> supported: false, that number in unsupported, correction_message not empty.
    (c) The same result with one hectare value edited by the caller -> it lands in rejected_results and the text that quotes it becomes unsupported.
    """
    sc = {"region": "southeast_buenos_aires", "owned_ha": 500, "own_capital_usd": 50000}
    solve_out = srv.solve_plan(sc, lang="es")
    res = solve_out["result"]
    npv = res["npv_usd"]
    soy_ha = res["hectares"]["soybean"]

    # 8a: honest text
    text_honest = f"El plan da un VAN de {npv} USD y siembra {soy_ha} ha de soja."
    out_a = srv.check_text(text_honest, [solve_out])
    assert out_a["supported"] is True
    assert len(out_a["unsupported"]) == 0

    # 8b: invented number
    text_invented = f"El plan da un VAN de {npv} USD, siembra {soy_ha} ha de soja y ganás 999.999 USD."
    out_b = srv.check_text(text_invented, [solve_out])
    assert out_b["supported"] is False
    assert any("999.999" in u["text"] for u in out_b["unsupported"])
    assert out_b["correction_message"] is not None and len(out_b["correction_message"]) > 0

    # 8c: tampered result
    tampered = copy.deepcopy(solve_out)
    tampered["result"]["hectares"]["soybean"] = 999.0
    out_c = srv.check_text(text_honest, [tampered])
    assert len(out_c["rejected_results"]) > 0
    assert out_c["rejected_results"][0]["reason"] == "result_hash mismatch"
    assert out_c["supported"] is False

    # 8d: tampered check in provenance -> signature mismatch
    tampered_check = copy.deepcopy(solve_out)
    if tampered_check["provenance"]["checks"]:
        tampered_check["provenance"]["checks"][0]["passed"] = not tampered_check["provenance"]["checks"][0]["passed"]
    else:
        tampered_check["provenance"]["checks"].append({"name": "edited_check", "passed": True})
    out_d = srv.check_text(text_honest, [tampered_check])
    assert len(out_d["rejected_results"]) > 0
    assert out_d["rejected_results"][0]["reason"] == "signature mismatch"
    assert out_d["supported"] is False


def test_9_auth(monkeypatch):
    """9. With DORA_MCP_KEYS set, an HTTP POST /mcp (Starlette TestClient) without a key -> 401;
    with a wrong key -> 401; with the right key -> tools/list works. /health works without a key.
    """
    raw_key, config_line = auth.generate_new_key("testuser")
    monkeypatch.setenv("DORA_MCP_KEYS", config_line)

    app = create_http_app()
    with TestClient(app) as client:
        # /health works without auth
        h = client.get("/health")
        assert h.status_code == 200
        assert h.json()["ok"] is True
        assert h.json()["engine_version"] == ENGINE_VERSION

        # /mcp without key -> 401
        r_none = client.post("/mcp")
        assert r_none.status_code == 401
        assert r_none.json() == {"error": "missing or invalid API key"}

        # /mcp with wrong key -> 401
        r_wrong = client.post("/mcp", headers={"Authorization": "Bearer bad_key"})
        assert r_wrong.status_code == 401
        assert r_wrong.json() == {"error": "missing or invalid API key"}

        # /mcp with right key -> tools/list works
        r_good = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert r_good.status_code == 200
        tools_list = r_good.json()["result"]["tools"]
        assert len(tools_list) == 12


def test_10_rate_limit(monkeypatch):
    """10. 61 calls in a minute with one key -> the last one gets 429."""
    raw_key, config_line = auth.generate_new_key("testuser")
    monkeypatch.setenv("DORA_MCP_KEYS", config_line)
    auth.reset_rate_limits()

    app = create_http_app()
    with TestClient(app) as client:
        for i in range(60):
            r = client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": i, "method": "tools/list"},
                headers={"Authorization": f"Bearer {raw_key}"},
            )
            assert r.status_code == 200

        # 61st call -> 429
        r_61 = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 60, "method": "tools/list"},
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert r_61.status_code == 429
        assert r_61.json() == {"error": "rate limit exceeded"}


def test_11_errors():
    """11. solve_plan({"area_ha": -5}) returns {"error": ...} and does not raise."""
    out = srv.solve_plan({"area_ha": -5})
    assert "error" in out
    assert "provenance" in out
    assert out["provenance"]["checks"] == []
    assert out["provenance"]["scenario_hash"] is None
    assert out["provenance"]["result_hash"] is None


def test_12_stdio_round_trip():
    """12. Start python -m mcp_server as a subprocess with the SDK's stdio client,
    initialize, tools/list, one solve_plan; the result has provenance.engine_version.
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def _run():
        root = str(srv.REPO_ROOT)
        env = dict(os.environ)
        env["PYTHONPATH"] = root
        env["DORA_OFFLINE"] = "1"
        params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server"], env=env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tl = await session.list_tools()
                assert len(tl.tools) == 12

                call_res = await session.call_tool(
                    "solve_plan",
                    {"scenario": {"region": "southeast_buenos_aires", "owned_ha": 500, "own_capital_usd": 50000}},
                )
                data = json.loads(call_res.content[0].text)
                assert "provenance" in data
                assert data["provenance"]["engine_version"] == ENGINE_VERSION

    asyncio.run(_run())


def test_13_fingerprint(tmp_path):
    """13. engine_fingerprint() is the same when computed twice and changes
    if a byte of a copied data file changes (use tmp_path and a patched root).
    """
    repo = srv.REPO_ROOT
    shutil.copytree(repo / "dora", tmp_path / "dora")

    fp1 = engine_fingerprint(tmp_path)
    fp2 = engine_fingerprint(tmp_path)
    assert fp1 == fp2

    data_files = list((tmp_path / "dora" / "data").rglob("*.json"))
    assert len(data_files) > 0
    target = data_files[0]
    b = target.read_bytes()
    target.write_bytes(b + b" ")

    _FINGERPRINT_CACHE.pop(str(tmp_path.resolve()), None)
    fp3 = engine_fingerprint(tmp_path)
    assert fp1 != fp3


def test_14_no_dora_data_trace():
    """Verify that running SPEC-40 tests left dora/data/ unchanged."""
    res = subprocess.run(["git", "status", "--porcelain", "dora/data"], capture_output=True, text=True, check=True)
    assert res.stdout.strip() == "", f"dora/data was modified: {res.stdout}"
