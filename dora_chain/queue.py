"""Asynchronous queue and publisher for DORA on-chain attestations (SPEC-41 section 4)."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import time
from typing import Any

from dora_chain.config import get_chain_config, get_records_dir, is_chain_configured
import dora_chain.eas as eas

logger = logging.getLogger("dora_chain.queue")

BACKOFF_SECONDS = [30, 120, 600]
DEFAULT_MAX_TX_PER_DAY = 200


def get_daily_cap() -> int:
    try:
        return int(os.environ.get("DORA_CHAIN_MAX_TX_PER_DAY", str(DEFAULT_MAX_TX_PER_DAY)))
    except ValueError:
        return DEFAULT_MAX_TX_PER_DAY


def enqueue_record(record: dict, ref_uid: str | None = None) -> dict:
    """Save record to records/<record_id>.json and append to queue.jsonl."""
    records_dir = get_records_dir()
    rec_id = record["record_id"]
    from dora.record import record_hash
    rec_hash = record_hash(record)
    kind = record.get("kind", "dora.plan.v1")

    # 1. Save full record JSON
    rec_file = records_dir / f"{rec_id}.json"
    rec_file.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

    # 2. Save initial status
    status_file = records_dir / "status" / f"{rec_id}.json"
    init_status = {
        "record_id": rec_id,
        "record_hash": rec_hash,
        "kind": kind,
        "status": "queued",
        "tx_hash": None,
        "attestation_uid": None,
        "ref_uid": ref_uid,
        "gas_used": None,
        "fee_wei": None,
        "explorer_url": None,
        "easscan_url": None,
        "attempts": 0,
        "last_attempt": None,
        "last_error": None,
        "enqueued_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    status_file.write_text(json.dumps(init_status, indent=2, ensure_ascii=False), encoding="utf-8")

    # 3. Append to queue.jsonl
    queue_file = records_dir / "queue.jsonl"
    entry = {
        "record_id": rec_id,
        "record_hash": rec_hash,
        "kind": kind,
        "ref_uid": ref_uid,
        "enqueued_at": init_status["enqueued_at"],
    }
    with queue_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, separators=(",", ":")) + "\n")

    return init_status


def get_record_status(record_id: str) -> dict:
    """Return status dict for record_id."""
    records_dir = get_records_dir()
    status_file = records_dir / "status" / f"{record_id}.json"
    if status_file.exists():
        try:
            return json.loads(status_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    rec_file = records_dir / f"{record_id}.json"
    if rec_file.exists():
        return {"record_id": record_id, "status": "queued"}

    return {"record_id": record_id, "status": "not_found"}


def _get_daily_tx_count(records_dir: Path) -> int:
    """Count successful transactions today (UTC)."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    status_dir = records_dir / "status"
    count = 0
    if not status_dir.exists():
        return 0
    for p in status_dir.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if data.get("status") == "published":
                last_att = data.get("last_attempt", "")
                if last_att and last_att.startswith(today_str):
                    count += 1
        except Exception:
            continue
    return count


class FileLock:
    def __init__(self, lock_path: Path):
        self.lock_path = lock_path
        self.acquired = False

    def acquire(self) -> bool:
        if self.lock_path.exists():
            try:
                # Check if stale or active
                content = self.lock_path.read_text().strip()
                pid = int(content) if content.isdigit() else None
                if pid:
                    import psutil  # type: ignore
                    if psutil.pid_exists(pid):
                        return False
            except Exception:
                return False
        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            self.lock_path.write_text(str(os.getpid()))
            self.acquired = True
            return True
        except Exception:
            return False

    def release(self):
        if self.acquired:
            try:
                self.lock_path.unlink(missing_ok=True)
            except Exception:
                pass
            self.acquired = False

    def __enter__(self):
        return self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


# Hook for faking chain calls in unit tests
_CHAIN_CALL_HOOK = None


def set_chain_call_hook(hook):
    global _CHAIN_CALL_HOOK
    _CHAIN_CALL_HOOK = hook


def drain_queue(max_items: int = 10) -> list[dict]:
    """Drain pending items from the queue with retry backoff and rate limit."""
    records_dir = get_records_dir()
    lock_file = records_dir / ".publisher.lock"
    lock = FileLock(lock_file)
    if not lock.acquire():
        logger.info("Publisher lock already held by another process. Skipping drain.")
        return []

    processed = []
    try:
        queue_file = records_dir / "queue.jsonl"
        if not queue_file.exists():
            return []

        entries = []
        for line in queue_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    continue

        daily_cap = get_daily_cap()
        tx_count_today = _get_daily_tx_count(records_dir)

        now = time.time()
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        for item in entries:
            rec_id = item["record_id"]
            status_file = records_dir / "status" / f"{rec_id}.json"
            if not status_file.exists():
                continue

            status = json.loads(status_file.read_text(encoding="utf-8"))
            if status.get("status") in ("published", "failed"):
                continue

            # Check daily cap
            if tx_count_today >= daily_cap:
                status["last_error"] = f"Daily cap of {daily_cap} transactions reached"
                status_file.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
                processed.append(status)
                continue

            # Check backoff timing
            attempts = status.get("attempts", 0)
            if attempts > 0:
                delay = BACKOFF_SECONDS[min(attempts - 1, len(BACKOFF_SECONDS) - 1)]
                last_time_str = status.get("last_attempt")
                if last_time_str:
                    try:
                        last_ts = datetime.fromisoformat(last_time_str.replace("Z", "+00:00")).timestamp()
                        if now - last_ts < delay:
                            continue
                    except Exception:
                        pass

            # Read record file
            rec_file = records_dir / f"{rec_id}.json"
            if not rec_file.exists():
                status["status"] = "failed"
                status["last_error"] = "Record JSON file missing on disk"
                status_file.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
                processed.append(status)
                continue

            record_json = json.loads(rec_file.read_text(encoding="utf-8"))

            status["attempts"] = attempts + 1
            status["last_attempt"] = now_iso

            # Publish to chain (or test hook)
            success = False
            tx_data = {}
            error_msg = None

            if _CHAIN_CALL_HOOK is not None:
                try:
                    res = _CHAIN_CALL_HOOK(record_json, item.get("ref_uid"))
                    success = res.get("status") == "published"
                    tx_data = res
                    if not success:
                        error_msg = res.get("last_error", "Mock chain failure")
                except Exception as e:
                    success = False
                    error_msg = str(e)
            else:
                if not is_chain_configured():
                    status["status"] = "not_configured"
                    status["last_error"] = "Chain not configured (DORA_CHAIN unset or web3 unavailable)"
                    status_file.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
                    processed.append(status)
                    continue

                try:
                    # Enforce mainnet guard
                    chain_cfg = get_chain_config()
                    # Perform actual send if private key available
                    priv_key = os.environ.get("DORA_CHAIN_PRIVATE_KEY", "").strip()
                    if not priv_key:
                        raise ValueError("DORA_CHAIN_PRIVATE_KEY is not configured")

                    # Live web3 execution
                    import web3
                    from web3 import Web3
                    from eth_account import Account

                    w3 = Web3(Web3.HTTPProvider(chain_cfg.rpc_url))
                    acct = Account.from_key(priv_key)
                    eas_contract = w3.eth.contract(address=Web3.to_checksum_address(chain_cfg.eas_address), abi=eas.EAS_ABI)

                    kind = record_json.get("kind")
                    if kind == "dora.plan.v1":
                        schema_uid = os.environ.get("DORA_EAS_PLAN_SCHEMA", "")
                        data_bytes = eas.encode_plan_data(record_json)
                        ref_uid_bytes = b"\x00" * 32
                    else:
                        schema_uid = os.environ.get("DORA_EAS_OUTCOME_SCHEMA", "")
                        data_bytes = eas.encode_outcome_data(record_json)
                        ref_uid_bytes = bytes.fromhex(item.get("ref_uid", "").removeprefix("0x").rjust(64, "0"))

                    req = {
                        "schema": bytes.fromhex(schema_uid.removeprefix("0x")),
                        "data": {
                            "recipient": "0x0000000000000000000000000000000000000000",
                            "expirationTime": 0,
                            "revocable": False,
                            "refUID": ref_uid_bytes,
                            "data": data_bytes,
                            "value": 0,
                        },
                    }

                    tx = eas_contract.functions.attest(req).build_transaction({
                        "from": acct.address,
                        "nonce": w3.eth.get_transaction_count(acct.address),
                        "chainId": chain_cfg.chain_id,
                    })
                    signed = acct.sign_transaction(tx)
                    tx_hash_bytes = w3.eth.send_raw_transaction(signed.raw_transaction)
                    receipt = w3.eth.wait_for_transaction_receipt(tx_hash_bytes, timeout=120)

                    # Extract attestation UID from receipt logs
                    att_uid = receipt.logs[0]["topics"][1].hex() if receipt.logs else ""

                    tx_data = {
                        "status": "published",
                        "tx_hash": receipt.transactionHash.hex(),
                        "attestation_uid": att_uid,
                        "gas_used": receipt.gasUsed,
                        "fee_wei": receipt.gasUsed * receipt.effectiveGasPrice,
                        "explorer_url": f"{chain_cfg.explorer_url}/tx/{receipt.transactionHash.hex()}",
                        "easscan_url": f"{chain_cfg.easscan_url}/attestation/view/{att_uid}",
                    }
                    success = True
                except Exception as e:
                    success = False
                    error_msg = str(e)

            if success:
                status.update({
                    "status": "published",
                    "tx_hash": tx_data.get("tx_hash"),
                    "attestation_uid": tx_data.get("attestation_uid"),
                    "gas_used": tx_data.get("gas_used"),
                    "fee_wei": tx_data.get("fee_wei"),
                    "explorer_url": tx_data.get("explorer_url"),
                    "easscan_url": tx_data.get("easscan_url"),
                    "last_error": None,
                })
                tx_count_today += 1
            else:
                status["last_error"] = error_msg
                if status["attempts"] >= 3:
                    status["status"] = "failed"
                else:
                    status["status"] = "queued"

            status_file.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
            processed.append(status)

            if len(processed) >= max_items:
                break

    finally:
        lock.release()

    return processed
