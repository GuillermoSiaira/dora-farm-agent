"""Public DORA MCP server on Modal (SPEC-40 section 6 / SPEC-41 section 4 / SPEC-43 section 4).

Serves /mcp and /health over HTTP with Bearer token authentication,
runs a scheduled background worker to drain the on-chain attestation queue,
and mounts durable Modal Volume 'dora-data' to overlay freshly refreshed data.
"""
import json
import os
from pathlib import Path
import sys

import modal

image = modal.Image.debian_slim(python_version="3.12")
if modal.is_local():
    ROOT = Path(__file__).resolve().parents[2]
    image = (
        image.pip_install_from_requirements(str(ROOT / "requirements.txt"))
        .pip_install_from_requirements(str(ROOT / "requirements-chain.txt"))
        .add_local_dir(
            str(ROOT),
            "/app",
            ignore=[
                ".git",
                ".venv",
                ".claude",
                "**/__pycache__",
                "eval/results",
                ".env",
                "site",
                "observatory",
                "assets",
                "records",
            ],
        )
    )

app = modal.App("dora-mcp", image=image)
records_volume = modal.Volume.from_name("dora-records", create_if_missing=True)
data_volume = modal.Volume.from_name("dora-data", create_if_missing=True)

function_secrets = [modal.Secret.from_name("dora-mcp")]
if os.environ.get("DORA_MODAL_INCLUDE_CHAIN_SECRET") == "1":
    function_secrets.append(modal.Secret.from_name("dora-chain"))


@app.function(
    volumes={"/records": records_volume, "/data": data_volume},
    env={"DORA_RECORDS_DIR": "/records"},
    secrets=function_secrets,
    timeout=120,
    scaledown_window=300,
    max_containers=1,
)
@modal.asgi_app()
def mcp_app():
    if "/app" not in sys.path:
        sys.path.insert(0, "/app")

    # Reload data volume and apply fresh overlay before importing dora
    data_volume.reload()
    from dora.refresh_job import apply_data_overlay
    apply_data_overlay(Path("/data"), Path("/app"))

    from mcp_server.server import create_http_app
    from dora.version import ENGINE_VERSION, engine_fingerprint
    from starlette.responses import JSONResponse

    base_app = create_http_app()

    class HealthOverlayMiddleware:
        def __init__(self, app_inst):
            self.app_inst = app_inst

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http" and scope.get("path") == "/health":
                ref_file = Path("/data/last_refresh.json")
                data_refreshed = None
                if ref_file.exists():
                    try:
                        content = json.loads(ref_file.read_text(encoding="utf-8"))
                        data_refreshed = content.get("date")
                    except Exception:
                        pass

                resp = JSONResponse(
                    {
                        "ok": True,
                        "engine_version": ENGINE_VERSION,
                        "engine_fingerprint": engine_fingerprint(),
                        "data_refreshed": data_refreshed,
                    }
                )
                await resp(scope, receive, send)
                return

            await self.app_inst(scope, receive, send)

    return HealthOverlayMiddleware(base_app)


@app.function(
    schedule=modal.Cron("*/10 * * * *"),
    volumes={"/records": records_volume},
    env={"DORA_RECORDS_DIR": "/records"},
    secrets=function_secrets,
    timeout=300,
)
def drain_publisher():
    """Scheduled task draining the on-chain attestation queue every 10 minutes."""
    if "/app" not in sys.path:
        sys.path.insert(0, "/app")

    # Reload volume to ensure latest committed state from other containers
    records_volume.reload()

    from dora_chain.queue import drain_queue
    processed = drain_queue()

    # Commit changes so other containers / future invocations see updated status
    if processed:
        records_volume.commit()

    return f"Processed {len(processed)} items."
