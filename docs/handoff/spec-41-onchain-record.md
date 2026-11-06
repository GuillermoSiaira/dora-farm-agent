# SPEC-41 Handoff: On-chain plan record & reputation (EAS on Base)

**Date:** 2026-11-05  
**Branch:** `spec-41-onchain-record` (rebased on `spec-40-mcp-server`)  
**Status:** Implementation and test suite fully verified offline (15/15 passing in `test_spec41.py`, 14/14 in `test_spec40.py`, 29/29 combined in 15.6s). Live Base Sepolia transactions are **pending funding from faucet by Guillermo**.

---

## 1. Blockchain Predeploy & Contract Checks (Base Sepolia)

All predeploys and identity registry contracts were checked directly against the Base Sepolia RPC (`https://sepolia.base.org`):

| Contract | Address | Bytecode Verified | Explorer / EASScan Link |
|---|---|---|---|
| **EAS Predeploy** | `0x4200000000000000000000000000000000000021` | Yes (2,059 bytes) | [base-sepolia.easscan.org](https://base-sepolia.easscan.org) / [Basescan EAS](https://sepolia.basescan.org/address/0x4200000000000000000000000000000000000021) |
| **Schema Registry** | `0x4200000000000000000000000000000000000020` | Yes (2,059 bytes) | [Basescan SchemaRegistry](https://sepolia.basescan.org/address/0x4200000000000000000000000000000000000020) |
| **Identity Registry (ERC-8004)** | `0x8004A818BFB912233c491871b3d84c89A494BD9e` | Yes (130 bytes proxy) | [Basescan Identity Registry](https://sepolia.basescan.org/address/0x8004A818BFB912233c491871b3d84c89A494BD9e) |

---

## 2. Wallet & Live Deployment Status (Claude Review Fix 1)

- **Old address discarded:** The previous temporary address (`0x7e3931c2…459b`) was not saved to disk and must NOT be funded.
- **New Operator Key Generated & Persisted:**
  - Public Operator Address: `0x2514F1A9D89c5271cFA685d6Ae0A430F5f915630`
  - Balance on Base Sepolia: `0.0 ETH`
  - `python -m dora_chain new-key` now automatically saves the private key to `.env` (gitignored) as `DORA_CHAIN_PRIVATE_KEY=...` and refuses to overwrite if a key is already configured.
- **Faucet Funding Pending:**
  - **Action for Guillermo:** Please fund address `0x2514F1A9D89c5271cFA685d6Ae0A430F5f915630` with a small amount of testnet ETH (0.01 to 0.05 ETH) from any Base Sepolia faucet (e.g., [faucets.chain.link](https://faucets.chain.link) or Coinbase Faucet).
  - Once funded, the following CLI commands are ready to run:
    1. Register schemas: `python -m dora_chain register-schemas`
    2. Register agent: `python -m dora_chain register-agent https://dora-agent.vercel.app/.well-known/agent-registration.json`
    3. Drain and publish pending queue: `python -m dora_chain publish`

---

## 3. Gas and Cost Analysis

Costs were measured and computed against live RPC data (`https://mainnet.base.org` and `https://sepolia.base.org`) on 2026-11-05:

- **Base Mainnet Gas Price:** 8,252,412 wei (~0.00825 gwei)
- **Base Sepolia Gas Price:** 6,000,000 wei (~0.006 gwei)
- **ETH Price benchmark:** \$3,400 USD / ETH

| Transaction Type | Estimated `gasUsed` | L2 Execution Fee (ETH) | L1 Data Fee (ETH est.) | Total Fee (ETH) | Total Cost (USD) |
|---|---|---|---|---|---|
| **Plan Attestation (`dora.plan.v1`)** | ~180,000 | 0.000001485 ETH | ~0.000000800 ETH | ~0.000002285 ETH | **~\$0.0078 USD** (< 1¢) |
| **Outcome Attestation (`dora.outcome.v1`)** | ~210,000 | 0.000001733 ETH | ~0.000000950 ETH | ~0.000002683 ETH | **~\$0.0091 USD** (< 1¢) |
| **Schema Registration (one-time)** | ~120,000 | 0.000000990 ETH | ~0.000000600 ETH | ~0.000001590 ETH | **~\$0.0054 USD** |
| **ERC-8004 Agent Registration (one-time)**| ~150,000 | 0.000001238 ETH | ~0.000000750 ETH | ~0.000001988 ETH | **~\$0.0068 USD** |

**Daily Cap:** `DORA_CHAIN_MAX_TX_PER_DAY=200` guarantees daily cost cannot exceed \$2.00 USD under normal conditions.

---

## 4. Claude's Review Fixes (5/11)

### 4.1 Wallet Persistence (Fix 1)
`dora_chain new-key` now checks `.env` first; if `DORA_CHAIN_PRIVATE_KEY` is already present, it refuses to overwrite. If missing, it writes the private key to `.env` and prints only the public address `0x2514F1A9D89c5271cFA685d6Ae0A430F5f915630`.

### 4.2 Reputation Pure Function (Fix 2)
- Removed `site/reputation.json` from git (`git rm site/reputation.json`).
- Added `site/reputation.json` to `.gitignore`.
- Made `compute_reputation_summary()` purely functional with zero file I/O.
- The CLI `python -m dora_chain reputation [path]` writes explicitly to the destination file. Unit tests run without writing to `site/`.

### 4.3 Non-blocking Async Background Publisher (Fix 3)
In `mcp_server/server.py`, `_background_drain_loop` now uses `await asyncio.to_thread(drain_queue)` and logs any exceptions. Verified by `test_14_concurrent_drain_does_not_block_http`: even when a chain attestation sleeps for 5 seconds in `drain_queue`, concurrent HTTP `/health` requests answer in under 1.0 second.

### 4.4 Modal Scheduled Drain & Volume Persistence (Fix 4)
Added scheduled task `drain_publisher` to `infra/modal/serve_mcp.py` running every 10 minutes (`modal.Cron("*/10 * * * *")`).

**Modal Volume Documentation:**
> - `volume.commit()`: *"Commit changes to a mounted volume. Must be called inside a container that mounts the Volume. If successful, the changes made are now persisted in durable storage and available to other containers accessing the volume."*
> - `volume.reload()`: *"Make latest committed state of volume available in the running container. Must be called inside a container that mounts the Volume. Any uncommitted changes to the volume, such as new or modified files, may implicitly be committed when reloading."*

`drain_publisher` reloads the volume before draining, and commits the volume if any item was processed.

### 4.5 Test Isolation & Cleanup of Records (Fix 5)
- All tests in `test_spec41.py` now run under an autouse fixture `isolate_records_dir` that points `DORA_RECORDS_DIR` to pytest's `tmp_path / "records"`.
- The two records previously in repo root `records/` came from our manual runs during initial development; they have been cleaned up.
- `records/` is in `.gitignore` and `git status --porcelain records/` is empty.

---

## 5. Test Suite Verification

```
tests\test_spec40.py ..............                                      [ 48%]
tests\test_spec41.py ...............                                     [100%]
======================= 29 passed, 1 warning in 15.62s ========================
```

`git status --porcelain dora/data` is empty after running all tests.
