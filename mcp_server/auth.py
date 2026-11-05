"""Authentication and rate limiting for DORA MCP HTTP transport (SPEC-40 section 5)."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import logging
import os
import secrets
import sys
import time
from typing import Any

from starlette.responses import JSONResponse

logger = logging.getLogger("mcp_server.auth")

RATE_LIMIT: int = 60
_get_time = time.time
_call_history: dict[str, list[float]] = defaultdict(list)


def reset_rate_limits() -> None:
    """Reset the in-memory call history (useful for testing)."""
    _call_history.clear()


def get_configured_keys() -> dict[str, str]:
    """Parse DORA_MCP_KEYS env var into dict of sha256_hex -> key_name."""
    raw = os.environ.get("DORA_MCP_KEYS", "").strip()
    if not raw:
        return {}
    keys_map = {}
    for item in raw.split(","):
        item = item.strip()
        if not item or ":" not in item:
            continue
        name, khash = item.split(":", 1)
        keys_map[khash.strip().lower()] = name.strip()
    return keys_map


def verify_key(key: str) -> str | None:
    """Verify raw API key against DORA_MCP_KEYS.
    Returns key name if valid, None otherwise.
    """
    if not key:
        return None
    khash = hashlib.sha256(key.strip().encode("utf-8")).hexdigest().lower()
    keys_map = get_configured_keys()
    return keys_map.get(khash)


def check_rate_limit(key_name: str) -> bool:
    """Check sliding 60-second window rate limit for key_name.
    Returns True if allowed, False if 429 rate limit exceeded.
    """
    now = _get_time()
    history = _call_history[key_name]
    valid = [t for t in history if now - t < 60.0]
    if len(valid) >= RATE_LIMIT:
        _call_history[key_name] = valid
        return False
    valid.append(now)
    _call_history[key_name] = valid
    return True


class AuthMiddleware:
    """ASGI middleware enforcing Bearer token auth and rate limiting on non-health routes."""

    def __init__(self, app: Any):
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any):
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path == "/health":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        auth_raw = headers.get(b"authorization", b"").decode("utf-8", errors="replace").strip()
        if not auth_raw.startswith("Bearer "):
            resp = JSONResponse({"error": "missing or invalid API key"}, status_code=401)
            await resp(scope, receive, send)
            return

        token = auth_raw[7:].strip()
        key_name = verify_key(token)
        if not key_name:
            resp = JSONResponse({"error": "missing or invalid API key"}, status_code=401)
            await resp(scope, receive, send)
            return

        if not check_rate_limit(key_name):
            resp = JSONResponse({"error": "rate limit exceeded"}, status_code=429)
            await resp(scope, receive, send)
            return

        logger.info(f"[mcp] request from key '{key_name}'")
        await self.app(scope, receive, send)


def generate_new_key(name: str) -> tuple[str, str]:
    """Generate a new random API key and return (raw_key, name:sha256_hex)."""
    raw_key = f"dora_{secrets.token_urlsafe(32)}"
    khash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest().lower()
    return raw_key, f"{name}:{khash}"


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "new":
        name = sys.argv[2]
        raw_key, config_line = generate_new_key(name)
        print(f"Key (save this, shown only once):\n{raw_key}\n")
        print(f"Config line for DORA_MCP_KEYS:\n{config_line}")
    else:
        print("Usage: python -m mcp_server.auth new <name>")
        sys.exit(1)


if __name__ == "__main__":
    main()
