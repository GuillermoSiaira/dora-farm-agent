"""CLI commands for DORA on-chain operations (SPEC-41)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from dora_chain.config import REPO_ROOT, get_chain_config, get_records_dir, is_chain_configured
import dora_chain.eas as eas
from dora_chain.erc8004 import register_agent
from dora_chain.queue import drain_queue
from dora_chain.reputation import compute_reputation_summary


def cmd_new_key():
    from eth_account import Account

    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        existing = env_path.read_text(encoding="utf-8")
        for line in existing.splitlines():
            line = line.strip()
            if line.startswith("DORA_CHAIN_PRIVATE_KEY=") and len(line.split("=", 1)[1].strip()) > 0:
                print("Error: DORA_CHAIN_PRIVATE_KEY is already set in .env. Refusing to overwrite existing key.")
                return

    acct = Account.create()
    key_hex = acct.key.hex()
    if not key_hex.startswith("0x"):
        key_hex = "0x" + key_hex

    if env_path.exists():
        with env_path.open("a", encoding="utf-8") as f:
            f.write(f"\nDORA_CHAIN_PRIVATE_KEY={key_hex}\n")
    else:
        env_path.write_text(f"DORA_CHAIN_PRIVATE_KEY={key_hex}\n", encoding="utf-8")

    print("=== DORA Base Sepolia Operator Wallet ===")
    print(f"Operator Address: {acct.address}")
    print("\nKey saved to .env as DORA_CHAIN_PRIVATE_KEY (gitignored).")
    print("Ask Guillermo to fund this address from a Base Sepolia faucet.")


def cmd_register_schemas():
    if not is_chain_configured():
        print("Chain not configured (DORA_CHAIN unset or web3 not installed).")
        print("\nSchema definitions:")
        print(f"dora.plan.v1    : {eas.SCHEMA_PLAN_STR}")
        print(f"dora.outcome.v1 : {eas.SCHEMA_OUTCOME_STR}")
        return

    chain_cfg = get_chain_config()
    priv = os.environ.get("DORA_CHAIN_PRIVATE_KEY", "").strip()
    if not priv:
        print("DORA_CHAIN_PRIVATE_KEY not set. Cannot register schemas on chain.")
        print(f"dora.plan.v1    : {eas.SCHEMA_PLAN_STR}")
        print(f"dora.outcome.v1 : {eas.SCHEMA_OUTCOME_STR}")
        return

    from web3 import Web3
    from eth_account import Account

    w3 = Web3(Web3.HTTPProvider(chain_cfg.rpc_url))
    acct = Account.from_key(priv)
    reg_contract = w3.eth.contract(
        address=Web3.to_checksum_address(chain_cfg.schema_registry),
        abi=eas.SCHEMA_REGISTRY_ABI,
    )

    print(f"Registering schemas on {chain_cfg.name} via {acct.address}...")
    for name, schema_str in [("dora.plan.v1", eas.SCHEMA_PLAN_STR), ("dora.outcome.v1", eas.SCHEMA_OUTCOME_STR)]:
        tx = reg_contract.functions.register(
            schema_str,
            "0x0000000000000000000000000000000000000000",
            False,
        ).build_transaction({
            "from": acct.address,
            "nonce": w3.eth.get_transaction_count(acct.address),
            "chainId": chain_cfg.chain_id,
        })
        signed = acct.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        uid = receipt.logs[0]["topics"][1].hex() if receipt.logs else "unknown"
        print(f"Schema {name} registered! UID: {uid} (tx: {receipt.transactionHash.hex()})")


def cmd_publish():
    print("Draining pending items from queue...")
    res = drain_queue()
    print(f"Processed {len(res)} items.")
    for item in res:
        print(f"- {item.get('record_id')}: status={item.get('status')} err={item.get('last_error')}")


def cmd_reputation(output_path: str | Path | None = None):
    print("Computing reputation...")
    records_dir = get_records_dir()
    plans = []
    outcomes = []
    for p in records_dir.glob("*.json"):
        if p.name.startswith("."):
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if data.get("kind") == "dora.plan.v1":
                plans.append(data)
            elif data.get("kind") == "dora.outcome.v1":
                outcomes.append(data)
        except Exception:
            continue
    summary = compute_reputation_summary(plans, outcomes)

    target = Path(output_path) if output_path else (REPO_ROOT / "site" / "reputation.json")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Reputation written to {target}")
    except Exception as e:
        print(f"Could not write {target}: {e}")

    print(json.dumps(summary, indent=2))


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m dora_chain <new-key|register-schemas|publish|reputation [path]|register-agent>")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "new-key":
        cmd_new_key()
    elif cmd == "register-schemas":
        cmd_register_schemas()
    elif cmd == "publish":
        cmd_publish()
    elif cmd == "reputation":
        out_p = sys.argv[2] if len(sys.argv) > 2 else None
        cmd_reputation(out_p)
    elif cmd == "register-agent":
        agent_uri = sys.argv[2] if len(sys.argv) > 2 else "https://dora-agent.vercel.app/.well-known/agent-registration.json"
        res = register_agent(agent_uri)
        print(f"Registered agent: {res}")
    else:
        print(f"Unknown command {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
