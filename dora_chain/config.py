"""Configuration for DORA blockchain integration (EAS on Base / Arbitrum, SPEC-41)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[1]


class ChainInfo(NamedTuple):
    name: str
    chain_id: int
    rpc_url: str
    eas_address: str
    schema_registry: str
    explorer_url: str
    easscan_url: str
    graphql_url: str
    identity_registry: str


CHAINS: dict[str, ChainInfo] = {
    "base-sepolia": ChainInfo(
        name="base-sepolia",
        chain_id=84532,
        rpc_url="https://sepolia.base.org",
        eas_address="0x4200000000000000000000000000000000000021",
        schema_registry="0x4200000000000000000000000000000000000020",
        explorer_url="https://sepolia.basescan.org",
        easscan_url="https://base-sepolia.easscan.org",
        graphql_url="https://base-sepolia.easscan.org/graphql",
        identity_registry="0x8004A818BFB912233c491871b3d84c89A494BD9e",
    ),
    "base": ChainInfo(
        name="base",
        chain_id=8453,
        rpc_url="https://mainnet.base.org",
        eas_address="0x4200000000000000000000000000000000000021",
        schema_registry="0x4200000000000000000000000000000000000020",
        explorer_url="https://basescan.org",
        easscan_url="https://base.easscan.org",
        graphql_url="https://base.easscan.org/graphql",
        identity_registry="0x8004A169FB4a3325136EB29fA0ceB6D2e539a432",
    ),
    "arbitrum-sepolia": ChainInfo(
        name="arbitrum-sepolia",
        chain_id=421614,
        rpc_url="https://sepolia-rollup.arbitrum.io/rpc",
        eas_address="0xaEF4103A04090071165F78D45D83A0C0782c2B2a",
        schema_registry="0x55DE6307ec767d60B2599723B9B97F739eb3b1c6",
        explorer_url="https://sepolia.arbiscan.io",
        easscan_url="https://arbitrum-sepolia.easscan.org",
        graphql_url="https://arbitrum-sepolia.easscan.org/graphql",
        identity_registry="",
    ),
}


def get_records_dir() -> Path:
    """Return local records directory."""
    raw = os.environ.get("DORA_RECORDS_DIR")
    if raw:
        p = Path(raw)
    else:
        p = REPO_ROOT / "records"
    p.mkdir(parents=True, exist_ok=True)
    (p / "status").mkdir(parents=True, exist_ok=True)
    return p


def get_chain_name() -> str | None:
    """Return DORA_CHAIN env var value or None if not set."""
    val = os.environ.get("DORA_CHAIN", "").strip().lower()
    return val if val else None


def get_chain_config() -> ChainInfo:
    """Return ChainInfo for current DORA_CHAIN, enforcing mainnet guard."""
    chain_name = get_chain_name()
    if not chain_name:
        raise ValueError("DORA_CHAIN is not set.")
    if chain_name not in CHAINS:
        raise ValueError(f"Unknown DORA_CHAIN '{chain_name}'. Soportadas: {', '.join(CHAINS.keys())}")

    if chain_name == "base":
        if os.environ.get("DORA_CHAIN_ALLOW_MAINNET") != "1":
            raise PermissionError(
                "DORA_CHAIN=base (mainnet) requires DORA_CHAIN_ALLOW_MAINNET=1. Refusing to operate on mainnet."
            )

    info = CHAINS[chain_name]
    custom_rpc = os.environ.get("DORA_CHAIN_RPC_URL", "").strip()
    if custom_rpc:
        info = info._replace(rpc_url=custom_rpc)
    return info


def is_chain_configured() -> bool:
    """Return True if web3 is available and DORA_CHAIN is set."""
    if not get_chain_name():
        return False
    try:
        import web3
        return True
    except (ImportError, Exception):
        return False

