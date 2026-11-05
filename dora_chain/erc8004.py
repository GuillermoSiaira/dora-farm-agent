"""ERC-8004 Agent Registration on Base Sepolia Identity Registry (SPEC-41 section 7)."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from dora_chain.config import REPO_ROOT, get_chain_config

logger = logging.getLogger("dora_chain.erc8004")

IDENTITY_REGISTRY_ABI = [
    {
        "inputs": [{"internalType": "string", "name": "agentURI", "type": "string"}],
        "name": "register",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]


def register_agent(agent_uri: str) -> dict:
    """Register agent on ERC-8004 Identity Registry on Base Sepolia."""
    chain_cfg = get_chain_config()
    priv = os.environ.get("DORA_CHAIN_PRIVATE_KEY", "").strip()
    if not priv:
        raise ValueError("DORA_CHAIN_PRIVATE_KEY is not configured")

    import web3
    from web3 import Web3
    from eth_account import Account

    w3 = Web3(Web3.HTTPProvider(chain_cfg.rpc_url))
    acct = Account.from_key(priv)

    if not chain_cfg.identity_registry:
        raise ValueError(f"No identity registry configured for chain {chain_cfg.name}")

    reg_contract = w3.eth.contract(
        address=Web3.to_checksum_address(chain_cfg.identity_registry),
        abi=IDENTITY_REGISTRY_ABI,
    )

    tx = reg_contract.functions.register(agent_uri).build_transaction({
        "from": acct.address,
        "nonce": w3.eth.get_transaction_count(acct.address),
        "chainId": chain_cfg.chain_id,
    })
    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

    # In ERC-8004, registration returns agentId or logs Transfer
    agent_id = None
    if receipt.logs:
        agent_id = int(receipt.logs[0]["topics"][-1].hex(), 16)

    # Update site/.well-known/agent-registration.json if exists
    json_path = REPO_ROOT / "site" / ".well-known" / "agent-registration.json"
    if json_path.exists() and agent_id is not None:
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            for reg in data.get("registrations", []):
                if chain_cfg.name in reg.get("agentRegistry", ""):
                    reg["agentId"] = agent_id
            json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    return {
        "status": "registered",
        "agent_id": agent_id,
        "tx_hash": receipt.transactionHash.hex(),
        "explorer_url": f"{chain_cfg.explorer_url}/tx/{receipt.transactionHash.hex()}",
    }

