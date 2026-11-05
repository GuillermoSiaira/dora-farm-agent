# SPEC-40: DORA as an MCP server (other agents call the engine, every number comes with its check)

**Status:** ready (5/11). Implement on branch `spec-40-mcp-server`, created from `main` (6dc9fd6 or later) in **`D:\projects\dora-main`** (not in `D:\projects\dora-hackathon`: another session works there on `spec-37-scenario-clarity`). Do not merge and do not deploy to mainnet anything; the Modal deploy of section 6 is allowed once the local tests pass. Commit on the branch with messages starting `SPEC-40 implementation:`; write the handoff and Claude reviews.

Touch only: a new package `mcp_server/` (`__init__.py`, `__main__.py`, `server.py`, `provenance.py`, `auth.py`), a new `dora/version.py`, `requirements.txt` (one line), a new `infra/modal/serve_mcp.py`, a new `tests/test_spec40.py`, `README.md` (one short section) and the handoff. **No change to `dora/engine.py`, `dora/tools.py`, `dora/verifier.py`, `dora/plan_check.py`, `app.py`.** If something there is missing, stop and say it in the handoff.

**Why.** After the hackathon (Guillermo, 5/11) every project must pass a filter: an agent can use it (MCP/API), it has something hard to copy, and it leaves a verifiable record. DORA's hard-to-copy part is the fortnightly LP engine plus the verifier that blocks numbers the engine did not produce (E1: 38 % → 97 %). Today that only reaches people through the Gradio chat. The farmer's own agent, the accountant's agent or any assistant should be able to call the engine directly and get numbers that carry proof of where they came from. The MCP server is a thin layer: it **reuses** `dora.tools`, `dora.plan_check` and `dora.verifier`; it contains no economics.

## 1. Engine version (`dora/version.py`, new)
```python
ENGINE_VERSION = "0.40.0"           # bump by hand when the model changes
def engine_fingerprint() -> str:    # sha256 hex of the bytes, in sorted path order, of:
    # dora/engine.py, dora/scenario.py, dora/tools.py, dora/plan_check.py and every file under dora/data/
```
Read files in binary, normalise `\r\n` → `\n` before hashing (Windows and Linux must give the same fingerprint). Cache the result per process. SPEC-41 uses both values.

## 2. Provenance on every answer (`mcp_server/provenance.py`)
Every tool in section 3 returns `{"result": <the dora.tools output, unchanged>, "provenance": {...}}`:
```python
"provenance": {
  "engine_version": ENGINE_VERSION,
  "engine_fingerprint": engine_fingerprint(),
  "tool": "solve_plan",
  "scenario_hash": sha256(canonical(scenario_as_validated)),   # see below
  "result_hash":   sha256(canonical(result)),
  "solver": "HiGHS (scipy.optimize.linprog)",
  "checks": [ {"name": ..., "passed": bool, "detail": ...}, ... ],   # per tool, section 3
  "issued_at": "2026-11-05T14:03:00Z",
  "signature": hmac_sha256(DORA_MCP_SIGNING_KEY, scenario_hash + result_hash + issued_at),
}
```
- `canonical(obj)`: `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)` after rounding every float to 6 significant digits (one helper, used by both hashes; SPEC-41 reuses it). Write it so that the same scenario gives the same hash on two runs (test 2).
- `scenario_as_validated`: the dict the caller sent, after `build_scenario` filled defaults (so two callers who differ only in defaults get the same hash). If `build_scenario` returns an error, there is no hash.
- `DORA_MCP_SIGNING_KEY`: env var. If missing (local stdio), generate a random one per process and add `"signature_scope": "process"` so the caller knows it only checks within that session.
- The signature lets `check_text` (section 3.7) trust results the caller hands back without keeping state on the server.

## 3. Tools (`mcp_server/server.py`)
Use the `mcp` SDK 2.x (`from mcp.server import MCPServer`, the same import `D:\projects\sig-agent\mcp_server\server.py` uses). Register a **curated** list, not the whole `TOOLS` dict (`record_document`, `assess_field_image`, `field_from_map`, `refresh_prices` and `next_question` need images, network or the chat context; they stay out). Each tool calls the existing function and wraps it with `provenance`. Tool descriptions in English, short, and say that all money is in USD of the plan's start.

| MCP tool | Calls | Extra `checks` |
|---|---|---|
| `build_scenario(scenario, lang="es")` | `tools.build_scenario` | `validated`: no `error` key; list the warnings it returned |
| `update_scenario(scenario, changes, lang="es")` | deep-merge `changes` into `scenario` (dicts merge, lists replace), then `tools.build_scenario` | same as above, plus `changed_keys` in `detail` |
| `solve_plan(scenario, lang="es", farmer_said=None, record=False)` | `tools.evaluate_season` | `plan_is_optimal` (3.3), `scenario_inputs` (3.4) |
| `shadow_prices(scenario, lang="es")` | `tools.shadow_prices` | `plan_is_optimal` |
| `break_even_prices(scenario, crops=None, verify=True, lang="es")` | `tools.break_even_prices` | one check per crop from its `verified` field (None → `passed: null`) |
| `compare_rent_out(scenario, lang="es")` | `tools.evaluate_season` with `tenure_comparison` on; return only `land_tenure`, `tenure_comparison`, `npv_usd`, `hectares`, `rent_out_ha` | `tenure_consistent` (3.5) |
| `evaluate_plan(scenario, hectares)` | `plan_check.evaluate_plan` | `feasible` from its output |
| `sensitivity(scenario, parameter, values, lang="es")` | `tools.sensitivity` | none |
| `check_text(text, results, farmer_said=None)` | `verifier.verify` | 3.7 |

3.3 **`plan_is_optimal`**: take `result["hectares"]` and run `plan_check.evaluate_plan(scenario, hectares)`; passed if `feasible` and `abs(gap_usd) <= max(1.0, 1e-4 * abs(npv_optimal_usd))`. This re-solves with the areas fixed: it catches a reported plan that does not match the optimum the engine found (rounding, double crops, rent-out). If it fails on a scenario where the chat agent never showed a problem, do not "fix" the threshold: report the case in the handoff.

3.4 **`scenario_inputs`** (only when `farmer_said` is a non-empty list of strings): `verifier.check_scenario("evaluate_season", {"scenario": scenario}, farmer_said, [])`. Each `ScenarioProblem` goes to `detail` (`field`, `value`, `message`). `passed` = no problems. This is the same rule the chat uses to stop the model from inventing a farm size or a capital the farmer never said. Without `farmer_said`, the check is `{"passed": null, "detail": "farmer_said not given: inputs not checked against what the farmer said"}`.

3.5 **`tenure_consistent`**: if `tenure_comparison` is present, passed if `best` agrees with the sign of `farm_only_npv_usd - rent_all_npv_usd` (when `allow_rent_out` is false) and `break_even_rent_usd_ha` re-computed from the two NPVs with the formula in `tools.py` matches within 0.01. If `tenure_comparison_error` is present, passed false with that message. If the farm is not owned, return the tool's output with `checks: []` and a `note`: "Rent comparison applies to owned land."

3.6 **Errors.** A `ScenarioError` or `TypeError` becomes `{"error": "...", "provenance": {..., "checks": []}}` with no hashes, never an MCP exception (the caller's agent must be able to read and fix it). Any other exception: log it with the stack, return `{"error": "internal error", "id": <uuid>}`.

3.7 **`check_text(text, results, farmer_said=None)`**: the caller's agent wrote an answer for a person and wants DORA's verifier to say which numbers in it are not supported. `results` is a list of objects as returned by the tools above (`{"result":..., "provenance":...}`). For each one, recompute `result_hash` and the signature; drop the ones that do not match and list them in `rejected_results` (index and reason). Then `verifier.verify(text, [r["result"] for r in kept], farmer_said or [])`. Return:
```python
{"supported": bool, "unsupported": [{"text": "1.250 ha", "context": "...sembrá 1.250 ha de soja..."}],
 "rejected_results": [...], "jargon": verifier.jargon(text), "unnamed_series": verifier.unnamed_series(text),
 "correction_message": verifier.correction_message(problems, style, lang=verifier.farmer_lang(text)) or None}
```
`correction_message` is the same text the chat agent receives; the caller can feed it to its own model. This tool is the point of the server: DORA does not only compute, it also checks what another agent says about the computation.

3.8 **`record=True` in `solve_plan`**: only a placeholder now: return `"record": {"status": "not_configured"}`. SPEC-41 fills it. Keep the parameter so the tool schema does not change later.

3.9 **Resources** (read-only): `dora://modeling-guide` (the text of `dora/modeling_guide.md`) and `dora://regions` (region ids, names and the crops of each, from `scenario.REGIONS`). Server `instructions`: two sentences: what DORA is, and "Call `check_text` on any answer you write with DORA's numbers before showing it to a person."

## 4. Transport
- **Local (stdio):** `python -m mcp_server` (default transport stdio). Document in README how to add it to Claude Desktop / Claude Code (`{"command": "python", "args": ["-m", "mcp_server"], "cwd": "<repo>"}`).
- **Remote (streamable HTTP):** `MCP_TRANSPORT=streamable-http python -m mcp_server` serves `/mcp` on `PORT` (default 8000) with `stateless_http=True, json_response=True` (the same choice `D:\projects\euyin-agent\mcp_server\server.py` made: no session state, any container can answer). Also a `GET /health` custom route returning `{"ok": true, "engine_version": ..., "engine_fingerprint": ...}` without auth.

## 5. Authentication (`mcp_server/auth.py`)
- stdio: no auth (the process belongs to the user who started it).
- HTTP: `Authorization: Bearer <key>` required on `/mcp`. Keys are configured in env `DORA_MCP_KEYS` as a comma list of `name:sha256hex(key)`; the server never stores a plain key. Wrong or missing key → HTTP 401 with JSON `{"error": "missing or invalid API key"}`. Implement as a small ASGI middleware around `streamable_http_app()` (or the SDK's `token_verifier` if it is simpler; tests 9–10 decide). Log the key **name** per call, never the key.
- Rate limit: 60 calls per minute per key name, in memory (one container, as in `serve_app.py`). Over the limit → 429.
- A helper `python -m mcp_server.auth new <name>` prints a new random key once and the `name:hash` line to paste into the Modal secret.

## 6. Modal deploy (`infra/modal/serve_mcp.py`, new)
Copy the image setup of `infra/modal/serve_app.py` (same ignore list, plus `site/`, `observatory/`, `assets/`). App name `dora-mcp`, `@modal.asgi_app()` returning the authenticated Starlette app, `max_containers=1`, `scaledown_window=300`, `timeout=120`, secret `dora-mcp` with `DORA_MCP_KEYS` and `DORA_MCP_SIGNING_KEY`. No LLM keys: the server never calls a model. Docstring with the two commands (`modal secret create dora-mcp ...`, `modal deploy infra/modal/serve_mcp.py`). Deploy once, call `/health` and one `solve_plan` with Guillermo's case from a client (section Handoff), paste the outputs.

## 7. Dependencies
Add `mcp>=2.0,<3` to `requirements.txt`. Nothing else (no web3 here; that is SPEC-41 and stays optional).

## Tests (`tests/test_spec40.py`, no network, no LLM; call the tools in-process through the server object, plus one stdio round-trip)
1. **Tool list.** The server lists exactly the 9 tools of section 3 and the 2 resources; no other `dora.tools` function is exposed.
2. **Hash is stable.** `solve_plan` twice on Southeast Buenos Aires 500 ha owned, 50,000 USD gives the same `scenario_hash` and `result_hash`; the same scenario with a default made explicit (e.g. `deposit_rate_annual` set to its default) gives the same `scenario_hash`; changing `area_ha` changes it.
3. **Same numbers as the chat.** `solve_plan(...)["result"]` equals `tools.evaluate_season(...)` for 3 scenarios (SE BA 500 ha; Pampas core 2,000 ha owned 500,000 USD; a rented 300 ha case).
4. **`plan_is_optimal`** passes on those 3 scenarios; with a monkeypatched `evaluate_season` that returns hectares moved 100 ha from soy to corn, it fails.
5. **`scenario_inputs`.** `farmer_said=["tengo 500 ha en el sudeste"]` and a scenario with `own_capital_usd: 80000` → the check fails and names `own_capital_usd`; with `farmer_said=["tengo 500 ha en el sudeste y 80 mil dólares"]` it passes; with no `farmer_said` it is `passed: null`.
6. **`compare_rent_out`** on SE BA 500 ha owned returns `tenure_comparison` with `tenure_consistent` passed; on a rented-only farm returns the note and no check.
7. **`break_even_prices`** on SE BA 500 ha: one check per crop not in the plan, `passed` equal to the tool's `verified`.
8. **`check_text`.** (a) A text quoting the NPV and the soy hectares from a `solve_plan` result → `supported: true`. (b) The same text with one invented number ("ganás 999.999 USD") → `supported: false`, that number in `unsupported`, `correction_message` not empty. (c) The same result with one hectare value edited by the caller → it lands in `rejected_results` and the text that quotes it becomes unsupported.
9. **Auth.** With `DORA_MCP_KEYS` set, an HTTP `POST /mcp` (Starlette `TestClient`) without a key → 401; with a wrong key → 401; with the right key → `tools/list` works. `/health` works without a key.
10. **Rate limit.** 61 calls in a minute with one key → the last one gets 429 (monkeypatch the clock or the limit).
11. **Errors.** `solve_plan({"area_ha": -5})` returns `{"error": ...}` and does not raise.
12. **stdio round-trip.** Start `python -m mcp_server` as a subprocess with the SDK's stdio client, `initialize`, `tools/list`, one `solve_plan`; the result has `provenance.engine_version`.
13. **Fingerprint.** `engine_fingerprint()` is the same when computed twice and changes if a byte of a copied data file changes (use `tmp_path` and a patched root).

Then the full suite (`python -m pytest -q`); restore the price files before handing off:
```
git checkout -- dora/data/price_curves/ dora/data/basis_*.json
```

## Handoff (`docs/handoff/spec-40-mcp-server.md`)
- The 9 tools with one real call each on Guillermo's case (Pampas core, 2,000 ha owned, 500,000 USD) and their `checks`; `check_text` on one honest and one invented answer.
- Time per call (stdio, local) for `solve_plan`, `break_even_prices(verify=True)` and `compare_rent_out`.
- Claude Code or Claude Desktop calling the local server: the config used and a screenshot or transcript of one call.
- The Modal URL, `/health` output, one authenticated `solve_plan` from outside (curl or the SDK client), one call without a key (401).
- Test output. Do not mark anything as passed unless its output proves it. List any case where `plan_is_optimal` failed.
