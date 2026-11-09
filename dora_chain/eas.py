"""EAS (Ethereum Attestation Service) encoding and contract interactions (SPEC-41 section 3)."""
from __future__ import annotations

import logging
import os
from typing import Any

from dora_chain.config import get_chain_config, is_chain_configured

logger = logging.getLogger("dora_chain.eas")

INT32_MIN = -2147483648

# Schema signatures
SCHEMA_PLAN_STR = "bytes32 recordHash, string engineVersion, bytes32 engineFingerprint, string region, uint16 season"
SCHEMA_OUTCOME_STR = "bytes32 recordHash, bytes32 planRecordHash, int32 yieldErrorBps, int32 priceErrorBps, int32 marginErrorBps, uint16 hectaresMatchBps, uint8 followedPlan"

TYPES_PLAN = ["bytes32", "string", "bytes32", "string", "uint16"]
TYPES_OUTCOME = ["bytes32", "bytes32", "int32", "int32", "int32", "uint16", "uint8"]

FOLLOWED_PLAN_MAP = {
    "unknown": 0,
    "no": 1,
    "partly": 2,
    "yes": 3,
}
FOLLOWED_PLAN_REV_MAP = {v: k for k, v in FOLLOWED_PLAN_MAP.items()}

# Minimal ABIs
EAS_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "bytes32", "name": "schema", "type": "bytes32"},
                    {
                        "components": [
                            {"internalType": "address", "name": "recipient", "type": "address"},
                            {"internalType": "uint64", "name": "expirationTime", "type": "uint64"},
                            {"internalType": "bool", "name": "revocable", "type": "bool"},
                            {"internalType": "bytes32", "name": "refUID", "type": "bytes32"},
                            {"internalType": "bytes", "name": "data", "type": "bytes"},
                            {"internalType": "uint256", "name": "value", "type": "uint256"},
                        ],
                        "internalType": "struct AttestationRequestData",
                        "name": "data",
                        "type": "tuple",
                    },
                ],
                "internalType": "struct AttestationRequest",
                "name": "request",
                "type": "tuple",
            }
        ],
        "name": "attest",
        "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
        "stateMutability": "payable",
        "type": "function",
    }
]

SCHEMA_REGISTRY_ABI = [
    {
        "inputs": [
            {"internalType": "string", "name": "schema", "type": "string"},
            {"internalType": "address", "name": "resolver", "type": "address"},
            {"internalType": "bool", "name": "revocable", "type": "bool"},
        ],
        "name": "register",
        "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]


def _to_bytes32(hex_str: str) -> bytes:
    h = hex_str.lower().removeprefix("0x")
    if len(h) < 64:
        h = h.rjust(64, "0")
    elif len(h) > 64:
        h = h[:64]
    return bytes.fromhex(h)


def encode_plan_data(plan_record: dict) -> bytes:
    """ABI-encode record for dora.plan.v1."""
    import eth_abi
    from dora.record import record_hash

    r_hash = _to_bytes32(record_hash(plan_record))
    v_str = str(plan_record.get("engine_version", ""))
    fp_bytes = _to_bytes32(plan_record.get("engine_fingerprint", ""))
    region = str(plan_record.get("scenario", {}).get("region", ""))
    season = int(plan_record.get("assumptions", {}).get("season", 2026))

    vals = [r_hash, v_str, fp_bytes, region, season]
    return eth_abi.encode(TYPES_PLAN, vals)


def decode_plan_data(data: bytes) -> dict:
    """Decode ABI-encoded data for dora.plan.v1."""
    import eth_abi

    r_hash, v_str, fp_bytes, region, season = eth_abi.decode(TYPES_PLAN, data)
    return {
        "recordHash": "0x" + r_hash.hex(),
        "engineVersion": v_str,
        "engineFingerprint": "0x" + fp_bytes.hex(),
        "region": region,
        "season": season,
    }


def encode_outcome_data(outcome_record: dict) -> bytes:
    """ABI-encode record for dora.outcome.v1."""
    import eth_abi
    from dora.record import record_hash

    r_hash = _to_bytes32(record_hash(outcome_record))
    plan_r_hash = _to_bytes32(outcome_record.get("plan_record_hash", ""))

    errors = outcome_record.get("errors", {})
    agg = errors.get("aggregate", {})

    y_err = agg.get("yield_error_pct")
    y_bps = int(round(y_err * 100)) if y_err is not None else INT32_MIN

    p_err = agg.get("price_error_pct")
    p_bps = int(round(p_err * 100)) if p_err is not None else INT32_MIN

    m_err = agg.get("margin_error_pct")
    m_bps = int(round(m_err * 100)) if m_err is not None else INT32_MIN

    h_match = agg.get("hectares_match_pct")
    h_bps = int(round((h_match or 0.0) * 100))
    h_bps = max(0, min(10000, h_bps))

    followed_raw = errors.get("followed_plan", "unknown")
    followed_int = FOLLOWED_PLAN_MAP.get(followed_raw, 0)

    vals = [r_hash, plan_r_hash, y_bps, p_bps, m_bps, h_bps, followed_int]
    return eth_abi.encode(TYPES_OUTCOME, vals)


def decode_outcome_data(data: bytes) -> dict:
    """Decode ABI-encoded data for dora.outcome.v1."""
    import eth_abi

    r_hash, plan_r_hash, y_bps, p_bps, m_bps, h_bps, followed_int = eth_abi.decode(TYPES_OUTCOME, data)
    return {
        "recordHash": "0x" + r_hash.hex(),
        "planRecordHash": "0x" + plan_r_hash.hex(),
        "yieldErrorBps": y_bps,
        "priceErrorBps": p_bps,
        "marginErrorBps": m_bps,
        "hectaresMatchBps": h_bps,
        "followedPlan": followed_int,
    }


def get_operator_address() -> str | None:
    """Get public operator address from DORA_CHAIN_PRIVATE_KEY without exposing key."""
    priv = os.environ.get("DORA_CHAIN_PRIVATE_KEY", "").strip()
    if not priv:
        return None
    try:
        from eth_account import Account
        acct = Account.from_key(priv)
        return acct.address
    except Exception:
        return None


_GRAPHQL_HOOK = None


def set_graphql_hook(hook):
    """Set hook for mocking GraphQL responses in tests."""
    global _GRAPHQL_HOOK
    _GRAPHQL_HOOK = hook


def find_attestation(record_hash: str | None = None, uid: str | None = None) -> dict | None:
    """Find attestation from EAS GraphQL by record_hash or uid."""
    if _GRAPHQL_HOOK is not None:
        return _GRAPHQL_HOOK(record_hash=record_hash, uid=uid)

    try:
        chain_cfg = get_chain_config()
    except Exception:
        return None

    import json
    import urllib.request

    if uid:
        query = """
        query GetAttestation($id: String!) {
            attestation(where: { id: $id }) {
                id
                attester
                recipient
                revoked
                time
                schemaId
                decodedDataJson
                data
            }
        }
        """
        variables = {"id": uid}
    elif record_hash:
        query = """
        query FindAttestations {
            attestations(take: 50, orderBy: [{ time: desc }]) {
                id
                attester
                recipient
                revoked
                time
                schemaId
                decodedDataJson
                data
            }
        }
        """
        variables = {}
    else:
        return None

    try:
        payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
        req = urllib.request.Request(
            chain_cfg.graphql_url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "dora-verifier/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if uid:
                return data.get("data", {}).get("attestation")
            else:
                att_list = data.get("data", {}).get("attestations", [])
                target_hex = record_hash.lower().removeprefix("0x")
                for a in att_list:
                    d = str(a.get("data", "")).lower()
                    if target_hex in d:
                        return a
                return None
    except Exception as e:
        logger.warning(f"Error querying EAS GraphQL: {e}")
        return None


def verify_record_attestation(record: dict) -> dict:
    """Verify record on chain via EAS GraphQL (SPEC-41 section 5)."""
    from datetime import datetime, timezone
    from dora.record import record_hash

    rec_h = record_hash(record)
    uid = record.get("attestation_uid") or record.get("uid")

    attestation = find_attestation(record_hash=rec_h, uid=uid)
    if not attestation:
        return {
            "hash_matches": False,
            "on_chain": False,
            "attester_is_dora": False,
            "attested_at": None,
            "easscan_url": None,
        }

    # Verify hash
    data_hex = str(attestation.get("data", "")).lower().removeprefix("0x")
    rec_h_clean = rec_h.lower().removeprefix("0x")
    decoded = str(attestation.get("decodedDataJson", "")).lower()
    hash_matches = data_hex.startswith(rec_h_clean) or (rec_h_clean in data_hex) or (rec_h_clean in decoded)

    # Verify attester
    expected_dora = (
        os.environ.get("DORA_OPERATOR_ADDRESS", "").strip()
        or get_operator_address()
    )
    attester = attestation.get("attester", "")
    if expected_dora:
        attester_is_dora = (attester.lower() == expected_dora.lower())
    else:
        attester_is_dora = True

    # Attested at
    time_val = attestation.get("time")
    if isinstance(time_val, (int, float)):
        attested_at = datetime.fromtimestamp(time_val, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        attested_at = str(time_val) if time_val else None

    # EASScan URL
    try:
        chain_cfg = get_chain_config()
        base_easscan = chain_cfg.easscan_url
    except Exception:
        base_easscan = "https://base-sepolia.easscan.org"

    att_id = attestation.get("id") or attestation.get("uid") or ""
    easscan_url = f"{base_easscan}/attestation/view/{att_id}" if att_id else None

    return {
        "hash_matches": hash_matches,
        "on_chain": True,
        "attester_is_dora": attester_is_dora,
        "attested_at": attested_at,
        "easscan_url": easscan_url,
    }
