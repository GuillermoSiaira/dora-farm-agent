# SPEC-41: a public, verifiable record of DORA's plans and of how they turned out (EAS on Base)

**Status:** ready (5/11). Implement **after SPEC-40 is committed** (it needs `dora/version.py`, `mcp_server/provenance.py` and the `record` parameter of `solve_plan`), on branch `spec-41-onchain-record` created from `spec-40-mcp-server`, in **`D:\projects\dora-main`**. Do not merge. **Base Sepolia only**: nothing in this spec sends a mainnet transaction; mainnet is Guillermo's call after the review (section 8). Commit with messages starting `SPEC-41 implementation:`; write the handoff and Claude reviews.

Touch only: a new `dora/record.py` (pure Python, no web3), a new package `dora_chain/` (`__init__.py`, `__main__.py`, `config.py`, `eas.py`, `queue.py`, `reputation.py`, `erc8004.py`), `mcp_server/server.py` (the `record` path and three new tools), a new `requirements-chain.txt`, `.gitignore` (one line), `infra/modal/serve_mcp.py` (a Volume and the optional secrets), a new `site/.well-known/agent-registration.json`, a new `tests/test_spec41.py`, `tests/test_spec40.py` (only test 1: the tool list grows from 9 to 12), `README.md` (one short section) and the handoff.

**Why.** DORA's claim is "every number comes from the engine". A record nobody can rewrite makes that claim checkable by a stranger: for each verified plan, DORA publishes a hash (scenario + assumptions + result + engine version) with its date; at the end of the season it publishes what happened, hits and misses included. Over seasons this is a public track record, the third leg of Guillermo's filter (5/11), and the piece a Base / Arbitrum / Avalanche grant reviewer can open on an explorer. The record is **optional** and **never blocks** the agent's answer.

## 1. Decisions (taken; the handoff may argue against them with evidence)
- **Network: Base** (Sepolia now, mainnet later). Reasons: Abu Oracle already lives on Base (ERC-8004 identity, agentId 60115 on the Identity Registry `0x8004A169FB4a3325136EB29fA0ceB6D2e539a432`, see `D:\projects\Abu-Oracle\specs_pending\CHAIN-C01.md`), so the wallet practice, the grant track (Base Builder Grants) and the explorer links are already known; EAS is a predeploy there, so there is no contract of ours to write, deploy or audit. Arbitrum also has EAS: keep the chain in config (chain id, RPC, EAS address, explorer) so a hackathon on Arbitrum is a config change, not code. Avalanche C-Chain: only if a specific grant requires it; out of scope here.
- **Mechanism: EAS attestations, not a custom contract.** EAS on Base and Base Sepolia: `EAS 0x4200000000000000000000000000000000000021`, `SchemaRegistry 0x4200000000000000000000000000000000000020` (OP-stack predeploys). **Check both addresses on `base-sepolia.easscan.org` before the first transaction and paste the check in the handoff.** Attestations are non-revocable (a record that can be withdrawn is not a track record).
- **Identity: ERC-8004**, as Abu Oracle: DORA gets its own agentId in the Identity Registry, with an agent card pointing to the SPEC-40 MCP endpoint. Every attestation is made by the same operator address, which is the agent's registered wallet, so "these are DORA's records" is checkable. On Sepolia only in this spec (section 7).
- **Who pays gas:** DORA's operator wallet (a hot wallet with a small balance, key only in env / Modal secret). The farmer pays nothing and needs no wallet. Later (out of scope): EAS delegated attestations so a farmer's own wallet can sign the outcome record while DORA pays.
- **Cost:** one attestation is one transaction of roughly 150–250k gas on an L2 plus a small L1 data fee; at usual Base fees that is a fraction of a US cent. **Do not trust this estimate: measure `gasUsed` and the total fee of each Sepolia transaction, and compute the mainnet cost with the gas price of the day (`eth_gasPrice` and the L1 fee from the receipt)**; put the table in the handoff. A daily cap `DORA_CHAIN_MAX_TX_PER_DAY` (default 200) stops a loop or abuse from draining the wallet.
- **Privacy:** nothing on chain identifies the farmer or the farm. On chain: hashes, engine version, region id and season. The full record (with the scenario) stays off chain: returned to the caller (the farmer's agent keeps its own proof) and saved in `DORA_RECORDS_DIR`. Each record has a random 32-byte salt so a small scenario cannot be guessed by hashing candidates.

## 2. The record (`dora/record.py`, no web3, no network)
```python
def build_plan_record(scenario_validated: dict, scenario_sent: dict, result: dict, provenance: dict) -> dict
def build_outcome_record(plan_record: dict, actual: dict) -> dict
def record_hash(record: dict) -> str          # sha256 hex of canonical(record), canonical() from mcp_server/provenance.py
```
Move `canonical()` from `mcp_server/provenance.py` to `dora/record.py` and import it back there (one definition; SPEC-40 tests must still pass).

**Plan record** (`kind: "dora.plan.v1"`):
```python
{
  "kind": "dora.plan.v1", "record_id": uuid4, "created_at": iso-utc,
  "engine_version": ..., "engine_fingerprint": ...,
  "scenario": scenario_validated,
  "assumptions": {
     "defaults_used": sorted keys present in scenario_validated but not in scenario_sent,
     "price_curve_source": ..., "regional_data": regional_source_label(region),
     "start_date": ..., "season": int (year the plan starts),
  },
  "result": {k: result[k] for k in ("npv_usd", "hectares", "rent_out_ha", "rent_in_ha", "buy_ha",
             "sales_t_by_month", "max_credit_usd", "tenure_comparison") if k in result},
  "planned": {   # what the outcome is compared against, per crop with hectares > 0
     "yield_t_ha": crop -> yield the plan used (hectare-weighted over sowing windows),
     "mean_sale_price_usd_t": crop -> sum_p(price_c(p) * sales[c][p]) / sum_p(sales[c][p]),
  },
  "provenance": {"scenario_hash", "result_hash", "checks"},   # from SPEC-40
  "salt": 32 random bytes hex,
}
```
`planned` needs the engine's `Result` (`sales` per crop and fortnight, yields per window), which `evaluate_season` does not return. Compute it in `mcp_server` with one extra `optimize(sc)` of the validated scenario (it takes milliseconds) and `tools._crop_price_at_p` (the price `break_even_prices` already uses, same point as the plan's price); no change to `engine.py` or `tools.py`. If the extra solve's NPV differs from `result["npv_usd"]` by more than 1 USD, do not record (`not_recorded`, "engine not deterministic") and say so in the handoff.

Plans are recorded **only if no check has `passed: false`** (`null` is fine). Otherwise `record` is `{"status": "not_recorded", "reason": "checks failed: <names>"}`. That is the meaning of "verified plan".

**Outcome record** (`kind: "dora.outcome.v1"`), at the end of the season:
```python
actual = {
  "hectares": {"soybean": 1000, ...},          # what was sown
  "yield_t_ha": {"soybean": 3.1, ...},
  "price_received_usd_t": {"soybean": 318, ...},   # average, same point as the plan's price
  "gross_margin_usd": 412000,                  # optional
  "followed_plan": "yes" | "partly" | "no",
  "notes": "drought in January",               # optional, kept off chain only
}
```
It stores `plan_record_id`, `plan_record_hash`, `actual`, and the errors DORA computes against the plan: per crop `yield_error_pct` (actual vs the yield the scenario used), `price_error_pct` (actual vs the plan's mean sale price of that crop, weighted by tonnes sold), and `margin_error_pct` if the margin is given (vs the plan's NPV converted back to end-of-season USD with the plan's own discount). Also `hectares_match_pct` = share of planned hectares that were sown as planned. **Misses are recorded exactly like hits.** If a value the error needs is missing, that error is `null`, not 0.

## 3. On chain (`dora_chain/eas.py`, web3.py, optional dependency)
`requirements-chain.txt`: `web3>=7,<8`. If `web3` is not installed or `DORA_CHAIN` is unset, every chain function returns `{"status": "not_configured"}`; nothing else in DORA changes.

Two EAS schemas, registered once (`python -m dora_chain register-schemas`, prints the UIDs to put in env):
```
dora.plan.v1    : bytes32 recordHash, string engineVersion, bytes32 engineFingerprint, string region, uint16 season
dora.outcome.v1 : bytes32 recordHash, bytes32 planRecordHash, int32 yieldErrorBps, int32 priceErrorBps, int32 marginErrorBps, uint16 hectaresMatchBps, uint8 followedPlan
```
Outcome attestations set `refUID` = the plan attestation's UID. Errors in basis points, weighted by planned hectares across crops; `null` → `type(int32).min` (document it as "unknown"). `followedPlan`: 0 unknown, 1 no, 2 partly, 3 yes. `recipient` = zero address, `expirationTime` 0, `revocable` false, `value` 0.

Config (`dora_chain/config.py`): `DORA_CHAIN` (`base-sepolia` | `base` | `arbitrum-sepolia`), `DORA_CHAIN_RPC_URL`, `DORA_CHAIN_PRIVATE_KEY`, `DORA_EAS_PLAN_SCHEMA`, `DORA_EAS_OUTCOME_SCHEMA`, `DORA_CHAIN_MAX_TX_PER_DAY`. A table per chain with chain id, EAS address, explorer and easscan URL. **`base` (mainnet) also requires `DORA_CHAIN_ALLOW_MAINNET=1`, otherwise refuse with a clear message.** Never log or return the private key; log the operator address.

## 4. Never block (`dora_chain/queue.py`)
- `solve_plan(..., record=True)` builds the plan record, saves it to `DORA_RECORDS_DIR/<record_id>.json`, appends `{record_id, record_hash, kind, enqueued_at}` to `DORA_RECORDS_DIR/queue.jsonl`, and returns at once:
  ```python
  "record": {"status": "queued", "record_id": ..., "record_hash": ..., "record": <full plan record>}
  ```
  (or `not_configured` / `not_recorded`). The solve result is identical with and without `record` (test 2).
- A publisher drains the queue: in the MCP server, one background task started in the server's lifespan, every 10 s; and a CLI `python -m dora_chain publish` for manual runs. Per entry: send the attestation, wait for the receipt, write `DORA_RECORDS_DIR/status/<record_id>.json` with `status` (`published` | `failed`), `tx_hash`, `attestation_uid`, `gas_used`, `fee_wei`, `explorer_url`, `easscan_url`, `attempts`, `last_error`. Retry with backoff (30 s, 2 min, 10 min, then `failed`). One nonce at a time (one publisher, one lock file). A chain error never reaches the tool call that queued it.
- On Modal, `DORA_RECORDS_DIR` is a `modal.Volume` mounted at `/records`.

## 5. New MCP tools (`mcp_server/server.py`)
| MCP tool | Does |
|---|---|
| `record_status(record_id)` | reads the status file; `queued` if none yet |
| `record_outcome(plan_record, actual)` | `plan_record` is the full JSON the caller kept (the server may not have it); checks `record_hash(plan_record)` against the plan attestation on chain if published (else against the local file); builds the outcome record; queues it with the plan's attestation UID as `refUID`; returns the outcome record, its errors and `status` |
| `verify_record(record)` | anyone can call it: recomputes `record_hash`, finds the attestation by UID or by hash (EAS GraphQL `https://base-sepolia.easscan.org/graphql`, read only), checks attester = DORA's operator address and schema = DORA's; returns `{"hash_matches", "on_chain", "attester_is_dora", "attested_at", "easscan_url"}` |

`verify_record` and `record_status` need no private key. `record_outcome` with `followed_plan` absent defaults to `"unknown"`, never `"yes"`.

## 6. Reputation (`dora_chain/reputation.py`, `python -m dora_chain reputation`)
Reads every DORA attestation of both schemas from EAS GraphQL (attester = operator address), pairs outcomes with plans by `refUID`, and prints and writes `site/reputation.json`:
`plans_recorded`, `outcomes_recorded`, per error the count, median of the absolute value and the share within ±10 %, `followed_plan` counts, and the list of every outcome (UIDs and errors), **including the worst ones**. No smoothing, no dropping outliers. With zero outcomes it says so; it does not invent a score.

## 7. ERC-8004 identity (`dora_chain/erc8004.py`, `site/.well-known/agent-registration.json`)
Copy the shape of `D:\projects\Abu-Oracle\next_app\public\.well-known\agent-registration.json`: name "DORA", a two-sentence description (fortnightly LP engine for grain farms; numbers checked by a verifier; plans and outcomes attested on Base), the MCP service with the SPEC-40 Modal URL and its 12 tool names, `supportedTrust: ["reputation"]`. `python -m dora_chain register-agent` calls `register()` on the **Base Sepolia** Identity Registry (`0x8004A818BFB912233c491871b3d84c89A494BD9e`, from CHAIN-C01; check it on the explorer first) with the URL of that JSON (served by the Vercel site in `site/`), and prints the agentId. Add it to the JSON's `registrations`. Mainnet registration: not in this spec.

## 8. What needs Guillermo (stop and ask in the handoff)
- A funded **Base Sepolia** key. Generate a fresh key locally (`eth_account.Account.create()`), print only the address, and ask Guillermo to fund it from a faucet (faucets have captchas: Antigravity must not try). Never reuse the Abu Oracle Safe or any key with mainnet funds. If there is no funded key, implement and test everything offline (section Tests), and leave the live part listed as pending.
- Mainnet (schemas, agent registration, first attestation): only after Claude's review and Guillermo's yes.

## 9. App and docs
`.gitignore`: `records/`. README: a short section "Verifiable record" with the two schema UIDs, the easscan links of one plan and its outcome, and `python -m dora_chain reputation`. No change to the Gradio app in this spec.

## Tests (`tests/test_spec41.py`, no network; the chain is faked behind the `eas.py` interface)
1. **Hash.** `record_hash` is stable across two runs and two processes, changes with the salt, the scenario, the result or the engine version; `canonical` gives the same bytes on `\r\n` and `\n` data (shared with SPEC-40).
2. **Non-blocking.** With a publisher that sleeps 5 s, `solve_plan(record=True)` returns in under 1 s plus solve time, with `status: queued`, and its `result` equals the one with `record=False`.
3. **Only verified plans.** A monkeypatched failing `plan_is_optimal` → `not_recorded` with the check's name; nothing queued.
4. **Not configured.** Without `DORA_CHAIN` (and with `web3` hidden via `monkeypatch.setitem(sys.modules, "web3", None)`) → `not_configured`, `solve_plan` still works, the whole SPEC-40 suite still passes.
5. **ABI.** The encoded data of a plan and an outcome attestation decode back (with `eth_abi`) to the same fields; `null` errors encode as `int32` min; `followedPlan` mapping.
6. **Queue and retry.** A fake chain that fails twice then succeeds → status `published` after 3 attempts with `tx_hash` and `attestation_uid`; one that always fails → `failed` with `last_error`; two publishers at once → the lock lets only one run.
7. **Daily cap.** With `DORA_CHAIN_MAX_TX_PER_DAY=2`, the third entry waits (status `queued`, `last_error` mentions the cap).
8. **Mainnet guard.** `DORA_CHAIN=base` without `DORA_CHAIN_ALLOW_MAINNET=1` → refuses before building any transaction.
9. **Outcome errors.** A plan with soy 1,000 ha at yield 3.0 and mean sale price 320; actual 1,000 ha, 2.7 t/ha, 336 USD/t → `yield_error_pct` −10.0, `price_error_pct` +5.0, `hectares_match_pct` 100; missing margin → `margin_error_pct` null, encoded unknown; `followed_plan` absent → `unknown`.
10. **`record_outcome` tamper.** A plan record with one hectare value edited → refused (`hash does not match`), nothing queued.
11. **`verify_record`.** With a faked GraphQL answer: the right record → all true; a record attested by another address → `attester_is_dora: false`.
12. **Reputation.** Faked attestations: 3 plans, 2 outcomes (one within 10 %, one 40 % off) → counts, medians and the 40 % one listed; zero outcomes → says there are none.
13. **No secrets out.** Run a publish with a fake key; grep the logs, status files and tool outputs for the key: absent.

Then the full suite (`python -m pytest -q`) and restore the price files:
```
git checkout -- dora/data/price_curves/ dora/data/basis_*.json
```

## Handoff (`docs/handoff/spec-41-onchain-record.md`)
- The EAS and Identity Registry address checks (explorer links).
- If a funded Sepolia key was available: the two schema UIDs; one plan attested from `solve_plan(record=True)` on Guillermo's case and one outcome for it (invented actuals, marked as such in `notes`), with tx hashes and easscan links; `verify_record` on both; `register-agent` agentId; `reputation` output.
- The cost table: per transaction `gasUsed`, L2 fee, L1 fee, total in ETH and in USD (state the ETH price and date used), and the mainnet estimate with the day's gas price.
- If there was no funded key: say so first, and list exactly what is pending.
- Test output. Do not mark anything as passed unless its output proves it.
