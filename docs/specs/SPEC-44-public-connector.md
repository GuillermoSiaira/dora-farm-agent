# SPEC-44: DORA as a public Claude connector (no key needed to try it)

**Status:** ready (6/11), approved by Guillermo. Implement **after the SPEC-42 review fixes are committed**, on branch `spec-44-public-connector` created from `spec-42-plan-spreadsheet`, in **`D:\projects\dora-main`**. Do not merge, do not push. Commit with messages starting `SPEC-44 implementation:`; write the handoff and Claude reviews. **Do not redeploy `serve_app.py`** (the public app is under hackathon judging until 10/11). Redeploying `serve_mcp.py` is allowed for this spec.

Touch only: `mcp_server/auth.py`, `mcp_server/server.py` (the two record tools' key check), `infra/modal/serve_mcp.py` (one env var), `README.md` (a "Use DORA from Claude, Cursor or Codex" section), a new `tests/test_spec44.py` and the handoff.

**Why.** In Claude (desktop and web) a remote MCP is added from Settings → Connectors → "Add custom connector" by pasting a URL. That's how Guillermo uses the Abu Oracle MCP. That form has no field for a Bearer header, so today's DORA MCP (SPEC-40: every `/mcp` call needs `Authorization: Bearer <key>`) can't be added there. Anyone who wants to try DORA from their own agent should be able to paste one URL and go. The core is already open source (Apache-2.0), so the calculation itself is not a secret. What has to stay protected is what costs money or writes something permanent: on-chain records (SPEC-41 pays gas) and, later, heavy use.

## 1. Two tiers in `AuthMiddleware`
- **Anonymous (no `Authorization` header):** allowed on `/mcp` when `DORA_MCP_PUBLIC=1`. Rate limit **20 calls per minute per client IP**, plus a **global cap of 2,000 anonymous calls per day**. The client IP is the first address in `X-Forwarded-For` if present (Modal sets it), otherwise `scope["client"][0]`. Exceeding either limit returns 429 with `{"error": "rate limit exceeded: anonymous use is limited; ask for a key at <README link>"}`.
- **With a valid key:** unchanged from SPEC-40 (60 per minute per key, no daily cap).
- **With an invalid key:** still 401. A wrong key is not silently downgraded to anonymous.
- `DORA_MCP_PUBLIC` unset or `0`: behaviour exactly as SPEC-40 (401 without a key). Tests that already exist must keep passing unchanged.
- The tier (`"anonymous"` or the key name) goes into the request state, so tools can read it, and into the log line of each call. Never log the key.

## 2. What anonymous callers can't do
- `solve_plan(record=True)` and `record_outcome` require a key. Anonymously they return `{"error": "recording on-chain needs an API key", "provenance": ...}`, with the provenance marked as an error, and nothing is queued.
- `record_status` and `verify_record` stay open: anyone may check a record, which is the point of SPEC-41.
- Every other tool (build/update scenario, solve without record, shadow prices, break-even, rent-out, evaluate plan, sensitivity, check_text, spreadsheet export/import from SPEC-42) is open.

## 3. Deploy
In `infra/modal/serve_mcp.py`, set `DORA_MCP_PUBLIC=1` in the function env. Redeploy `serve_mcp.py` only. Live checks, with real output pasted in the handoff:
1. `curl` POST `initialize` to `/mcp` without a header returns 200.
2. The same with a wrong Bearer returns 401.
3. An anonymous `solve_plan` for `{"region": "pampas_core", "area_ha": 500, "owned_ha": 500, "own_capital_usd": 100000}` returns a plan with `plan_is_optimal: true`.
4. An anonymous `solve_plan` with `record=True` returns the "needs an API key" error.

## 4. README section "Use DORA from Claude, Cursor or Codex"
- **Claude (desktop or web):** Settings → Connectors → Add custom connector. Name `DORA`, URL `https://guillermosiaira--dora-mcp-mcp-app.us-east.modal.run/mcp`. No key needed to try it, within the anonymous limits.
- **Claude Code:** `claude mcp add --transport http dora <URL>`, plus `--header "Authorization: Bearer <key>"` if you have a key.
- **Cursor:** the `mcp.json` snippet with `url` and optional `headers`.
- One line on limits and how to ask for a key (open an issue in the repo).
- One example question, in Spanish and in English, that uses three tools: plan, shadow prices and rent-out.

## Tests (`tests/test_spec44.py`, Starlette TestClient, no network, no LLM, `DORA_OFFLINE=1`)
1. `DORA_MCP_PUBLIC=1`, no header: `initialize` and `tools/list` succeed.
2. `DORA_MCP_PUBLIC=1`, wrong key: 401.
3. `DORA_MCP_PUBLIC=0`, no header: 401 (SPEC-40 behaviour).
4. Anonymous per-IP limit: the 21st call within a minute from the same `X-Forwarded-For` returns 429; a different IP still passes.
5. Global anonymous daily cap: set the cap to 5 by monkeypatching, and the 6th anonymous call returns 429 even from a new IP. Keyed calls still pass.
6. Anonymous `solve_plan(record=True)`: returns the error and leaves the queue empty (`DORA_RECORDS_DIR` in `tmp_path`). The same call with a valid key queues one record.
7. Anonymous `record_status` and `verify_record` work.
8. The key never appears in captured logs (`caplog`), for either a valid or an invalid key.
9. After the suite, `git status --porcelain dora/data observatory` is empty.

Run the new tests, then the **full** suite, and paste its last line in the handoff (0 failed).

## Handoff (`docs/handoff/spec-44-public-connector.md`)
What changed, test output, full-suite line, live checks output, and the exact steps for Guillermo to add DORA as a custom connector in Claude. After that, the local `mcpServers.dora` entry that Claude added to his Claude Desktop config (with `mcp-remote`) can be removed, to avoid two DORA servers.
