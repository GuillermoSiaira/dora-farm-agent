"""Provenance generation and canonical JSON serialization (SPEC-40 / SPEC-41)."""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import secrets
from typing import Any

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


def _round_sig_floats(obj: Any) -> Any:
    """Recursively round every float to 6 significant digits and format objects for canonical JSON."""
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (float,)):
        if math.isnan(obj) or math.isinf(obj) or obj == 0.0:
            return obj
        return float(f"{obj:.6g}")
    if hasattr(obj, "item") and callable(obj.item):
        return _round_sig_floats(obj.item())
    if isinstance(obj, (int,)):
        return int(obj)
    if isinstance(obj, (str,)):
        return obj.replace("\r\n", "\n")
    if obj is None:
        return None
    if isinstance(obj, Path):
        return obj.as_posix()
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return _round_sig_floats(dataclasses.asdict(obj))
    if isinstance(obj, dict):
        return {str(k): _round_sig_floats(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_round_sig_floats(x) for x in obj]
    if isinstance(obj, set):
        rounded_list = [_round_sig_floats(x) for x in obj]
        return sorted(rounded_list, key=lambda x: canonical(x))
    return obj


def canonical(obj: Any) -> str:
    """Canonical JSON string: floats rounded to 6 significant digits, sorted keys, no whitespace."""
    prepared = _round_sig_floats(obj)
    return json.dumps(prepared, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


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
