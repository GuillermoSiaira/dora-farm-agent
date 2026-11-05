"""Provenance generation and canonical JSON serialization (SPEC-40 / SPEC-41)."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import os
import secrets
from typing import Any

from dora.record import canonical
from dora.version import ENGINE_VERSION, engine_fingerprint

_PROCESS_SIGNING_KEY: str | None = None


def get_signing_key() -> tuple[str, bool]:
    """Return (signing_key, is_process_scoped)."""
    global _PROCESS_SIGNING_KEY
    env_key = os.environ.get("DORA_MCP_SIGNING_KEY")
    if env_key:
        return env_key, False
    if _PROCESS_SIGNING_KEY is None:
        _PROCESS_SIGNING_KEY = secrets.token_hex(32)
    return _PROCESS_SIGNING_KEY, True


def sha256_canonical(obj: Any) -> str:
    """Compute sha256 hex digest of the canonical JSON string of obj."""
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def hmac_sha256(key: str, message: str) -> str:
    """Compute HMAC-SHA256 hex digest."""
    return hmac.new(key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def build_provenance(
    tool_name: str,
    scenario_as_validated: dict | None,
    result: Any,
    checks: list[dict] | None = None,
    is_error: bool = False,
    issued_at: str | None = None,
) -> dict:
    """Build provenance dictionary according to SPEC-40 section 2 and Claude review 2."""
    if issued_at is None:
        issued_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    signing_key, is_process_scoped = get_signing_key()

    if is_error:
        prov = {
            "engine_version": ENGINE_VERSION,
            "engine_fingerprint": engine_fingerprint(),
            "tool": tool_name,
            "scenario_hash": None,
            "result_hash": None,
            "solver": "HiGHS (scipy.optimize.linprog)",
            "checks": checks or [],
            "issued_at": issued_at,
            "signature": None,
        }
        if is_process_scoped:
            prov["signature_scope"] = "process"
    else:
        scenario_hash = sha256_canonical(scenario_as_validated) if scenario_as_validated is not None else None
        result_hash = sha256_canonical(result)

        prov = {
            "engine_version": ENGINE_VERSION,
            "engine_fingerprint": engine_fingerprint(),
            "tool": tool_name,
            "scenario_hash": scenario_hash,
            "result_hash": result_hash,
            "solver": "HiGHS (scipy.optimize.linprog)",
            "checks": checks or [],
            "issued_at": issued_at,
        }
        if is_process_scoped:
            prov["signature_scope"] = "process"

        msg = canonical(prov)
        signature = hmac_sha256(signing_key, msg)
        prov["signature"] = signature

    return prov


def verify_provenance_signature(result_obj: Any, prov: dict) -> tuple[bool, str]:
    """Verify result_hash and HMAC signature covering the entire provenance.
    Returns (valid, reason).
    """
    if not isinstance(prov, dict):
        return False, "invalid provenance format"

    expected_result_hash = prov.get("result_hash")
    if not expected_result_hash:
        return False, "missing result_hash"

    calc_result_hash = sha256_canonical(result_obj)
    if calc_result_hash != expected_result_hash:
        return False, "result_hash mismatch"

    sig = prov.get("signature")
    if not sig:
        return False, "missing signature"

    prov_to_sign = {k: v for k, v in prov.items() if k != "signature"}
    msg = canonical(prov_to_sign)

    signing_key, _ = get_signing_key()
    calc_sig = hmac_sha256(signing_key, msg)
    if not hmac.compare_digest(calc_sig, sig):
        return False, "signature mismatch"

    return True, ""
