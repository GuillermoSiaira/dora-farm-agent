# SPEC-41 Handoff: On-chain plan record & reputation (EAS on Base)

**Date:** 2026-11-05  
**Branch:** `spec-41-onchain-record` (created from `spec-40-mcp-server`)  
**Status:** Implementation and test suite fully verified offline (13/13 passing in `test_spec41.py`, 13/13 in `test_spec40.py`, 469 passed overall). Live Base Sepolia transactions are **pending funding from faucet by Guillermo**.

---

## 1. Blockchain Predeploy & Contract Checks (Base Sepolia)

All predeploys and identity registry contracts were checked directly against the Base Sepolia RPC (`https://sepolia.base.org`):

| Contract | Address | Bytecode Verified | Explorer / EASScan Link |
|---|---|---|---|
| **EAS Predeploy** | `0x4200000000000000000000000000000000000021` | Yes (2,059 bytes) | [base-sepolia.easscan.org](https://base-sepolia.easscan.org) / [Basescan EAS](https://sepolia.basescan.org/address/0x4200000000000000000000000000000000000021) |
| **Schema Registry** | `0x4200000000000000000000000000000000000020` | Yes (2,059 bytes) | [Basescan SchemaRegistry](https://sepolia.basescan.org/address/0x4200000000000000000000000000000000000020) |
| **Identity Registry (ERC-8004)** | `0x8004A818BFB912233c491871b3d84c89A494BD9e` | Yes (130 bytes proxy) | [Basescan Identity Registry](https://sepolia.basescan.org/address/0x8004A818BFB912233c491871b3d84c89A494BD9e) |

---

## 2. Wallet & Live Deployment Status

- **Operator Key Generated:**
  - Public Operator Address: `0x7e3931c2f68Fb83b847Cd8759500cBdD2dC6459b`
  - Balance on Base Sepolia: `0.0 ETH`
- **Faucet Funding Pending:**
  - As required by Section 8 of SPEC-41, faucet captchas require manual interaction.
  - **Action for Guillermo:** Please fund address `0x7e3931c2f68Fb83b847Cd8759500cBdD2dC6459b` with a small amount of testnet ETH (0.01 to 0.05 ETH) from any Base Sepolia faucet (e.g., [faucets.chain.link](https://faucets.chain.link) or Coinbase Faucet).
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

**Conclusion:** At standard Base fee levels (post-Dencun EIP-4844 blobs), publishing verifiable agronomic plans and end-of-season outcomes costs under **\$0.01 USD** per attestation. The daily safety cap (`DORA_CHAIN_MAX_TX_PER_DAY=200`) limits maximum theoretical daily expenditure to less than \$2.00 USD.

---

## 4. Test Suite Execution & Output

All 13 SPEC-41 tests pass with no network dependencies:

```
tests\test_spec41.py .............                                       [100%]
======================== 13 passed, 1 warning in 4.44s ========================
```

Combined SPEC-40 + SPEC-41 verification:

```
tests\test_spec40.py .............                                       [ 50%]
tests\test_spec41.py .............                                       [100%]
======================== 26 passed, 1 warning in 8.58s ========================
```

Full repository regression suite:
- 469 passed, 1 skipped in 275s.

---

## 5. Security & Privacy Safeguards Verified

- **Zero Secrets Leakage:** Verified in `test_13_no_secrets_out` that private keys are never written to status files, log output, canonical records, or git.
- **Mainnet Refusal Guard:** Verified in `test_8_mainnet_guard` that setting `DORA_CHAIN=base` raises `PermissionError` unless `DORA_CHAIN_ALLOW_MAINNET=1` is explicitly set.
- **Farmer Privacy:** Scenario data remains strictly off-chain (`records/` directory, excluded in `.gitignore`). Only hashes (`recordHash`, `engineFingerprint`, region identifier, and season year) touch the public ledger.
- **Tamper Resistance:** Verified in `test_10_record_outcome_tamper` that altering any hectare or economic value invalidates the hash and immediately triggers refusal.
